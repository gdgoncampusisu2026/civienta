"""Kelime tablosu küçültülmüş MiniLM: bellek ve kalite ölçümü (S0-10, PR #29 takibi).

paraphrase-multilingual-MiniLM-L12-v2'nin ağırlıklarının büyük kısmı 250.000 tokenlık
çok dilli kelime tablosudur. Bu script yalnızca Türkçe ve İngilizce metinlerde geçen
tokenları bırakır, modeli ONNX'e aktarır, int8'e sıkıştırır ve sonra ölçer:
  - kelime tablosu boyutu ve model dosyası boyutu
  - tokenlaştırması değişen cümle oranı (test setinde ve ayrılmış TR/EN cümlelerde)
  - test setinde kalite (benchmark.py ile aynı metrikler)
  - tepe bellek ve model yükleme süresi (temiz bir Python sürecinde)

Kelime tablosu OPUS-100 en-tr paralel cümlelerinden çıkarılır. Test seti bu derleme
dahil edilmez, böylece kalite ölçümü dürüst kalır.

Kurulum:
    pip install numpy psutil fastapi torch sentence-transformers onnx onnxscript \
        onnxruntime tokenizers huggingface_hub datasets

Kullanım (benchmark.py ve s010_test_set.json ile aynı klasörde):
    python prune_vocab.py                    # derle, aktar, ölç
    python prune_vocab.py --corpus-rows 300000   # daha küçük derlemle hızlı deneme

Üretilen model dosyaları (varsayılan: ./pruned-minilm) repoya commit'lenmez.
"""

import argparse
import collections
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from benchmark import MINILM, evaluate, load_test_set, measure_latency, normalize  # noqa: E402

SPECIAL_IDS = [0, 1, 2, 3]  # <s>, <pad>, </s>, <unk> (XLM-R)


class LocalOnnxBackend:
    """Yerel ONNX modeli + tokenizer.json ile embedding (benchmark.py'deki ONNX kurulumunun aynısı)."""

    def __init__(self, model_path, tokenizer_path):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self.tokenizer.enable_truncation(max_length=128)
        self.tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
        options = ort.SessionOptions()
        options.enable_cpu_mem_arena = False
        options.intra_op_num_threads = 1
        self.session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.session.get_inputs()}
        self.dim = 384

    def _embed(self, texts):
        encoded = self.tokenizer.encode_batch(texts)
        ids = np.array([e.ids for e in encoded], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.input_names:
            feed["token_type_ids"] = np.zeros_like(ids)
        tokens = self.session.run(None, feed)[0]
        m = mask[..., None].astype(np.float32)
        return normalize((tokens * m).sum(1) / m.sum(1))

    embed_queries = _embed
    embed_passages = _embed


def load_corpus(rows):
    """OPUS-100 en-tr: eğitim kısmından kelime tablosu için, doğrulama kısmından ayrılmış kontrol için."""
    from datasets import load_dataset
    train = load_dataset("Helsinki-NLP/opus-100", "en-tr", split=f"train[:{rows}]")
    valid = load_dataset("Helsinki-NLP/opus-100", "en-tr", split="validation")
    flatten = lambda ds: [t for row in ds for t in (row["translation"]["en"], row["translation"]["tr"])]
    return flatten(train), flatten(valid)


def count_tokens(tokenizer, texts, batch=2000):
    counts = collections.Counter()
    for i in range(0, len(texts), batch):
        for ids in tokenizer(texts[i:i + batch], add_special_tokens=False)["input_ids"]:
            counts.update(ids)
    return counts


def prune_tokenizer(tokenizer_json, keep):
    """Unigram kelime tablosunu yalnızca 'keep' içindeki tokenlarla yeniden kurar."""
    tj = json.loads(tokenizer_json)
    if tj["model"]["type"] != "Unigram":
        raise RuntimeError(f"Beklenmeyen tokenizer tipi: {tj['model']['type']}")
    remap = {old: new for new, old in enumerate(keep)}
    vocab = tj["model"]["vocab"]
    tj["model"]["vocab"] = [vocab[i] for i in keep]
    tj["model"]["unk_id"] = remap[tj["model"]["unk_id"]]
    # <mask> gibi kullanılmayan özel tokenlar çıkar, kalanların kimliği güncellenir
    tj["added_tokens"] = [dict(t, id=remap[t["id"]]) for t in tj["added_tokens"] if t["id"] in remap]
    return json.dumps(tj, ensure_ascii=False), remap


def changed_ratio(old_tok, new_tok, remap, texts):
    """Küçültülmüş tokenizer'ın farklı tokenlaştırdığı metinlerin oranı."""
    changed = 0
    for t in texts:
        old = [remap.get(i, -1) for i in old_tok.encode(t).ids]
        changed += old != new_tok.encode(t).ids
    return changed / len(texts)


def export_onnx(hf_model, new_tokenizer, path):
    import torch

    class Wrapper(torch.nn.Module):
        def __init__(self, model):
            super().__init__()
            self.model = model

        def forward(self, input_ids, attention_mask):
            return self.model(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state

    wrapper = Wrapper(hf_model).eval()
    # Örnek girdi küçültülmüş tokenizer ile üretilir (eski kimlikler yeni tabloya sığmaz)
    new_tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
    encoded = new_tokenizer.encode_batch(["kısa bir örnek", "a slightly longer English example sentence"])
    args = (torch.tensor([e.ids for e in encoded]), torch.tensor([e.attention_mask for e in encoded]))
    names = dict(input_names=["input_ids", "attention_mask"], output_names=["last_hidden_state"])
    try:
        torch.onnx.export(
            wrapper, args, str(path), opset_version=17, dynamo=False,
            dynamic_axes={"input_ids": {0: "batch", 1: "seq"}, "attention_mask": {0: "batch", 1: "seq"},
                          "last_hidden_state": {0: "batch", 1: "seq"}},
            **names,
        )
    except Exception as err:  # eski dışa aktarıcı yoksa yeni (dynamo) dışa aktarıcıyı dene
        print(f"Eski ONNX dışa aktarıcı çalışmadı ({err}), dynamo deneniyor")
        batch, seq = torch.export.Dim("batch"), torch.export.Dim("seq")
        torch.onnx.export(
            wrapper, args, str(path), dynamo=True, external_data=False,
            dynamic_shapes={"input_ids": {0: batch, 1: seq}, "attention_mask": {0: batch, 1: seq}},
            **names,
        )


def build(out_dir, corpus_rows, min_count):
    import torch
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from sentence_transformers import SentenceTransformer
    from tokenizers import Tokenizer

    out_dir.mkdir(parents=True, exist_ok=True)
    st = SentenceTransformer(MINILM, device="cpu")
    hf_model, hf_tokenizer = st[0].auto_model, st.tokenizer
    old_size = hf_model.embeddings.word_embeddings.weight.shape[0]

    print("TR/EN derlemi indiriliyor ve tokenlar sayılıyor...")
    train_texts, valid_texts = load_corpus(corpus_rows)
    counts = count_tokens(hf_tokenizer, train_texts)
    keep = sorted(set(SPECIAL_IDS) | {i for i, c in counts.items() if c >= min_count})
    assert keep[:4] == SPECIAL_IDS, "özel tokenlar 0-3 kimliklerinde kalmalı"
    print(f"Derlem: {len(train_texts):,} cümle | kelime tablosu {old_size:,} -> {len(keep):,} token")

    # Embedding tablosunu küçült (pad kimliği 1 olarak kalır)
    old_weights = hf_model.embeddings.word_embeddings.weight.data
    new_embedding = torch.nn.Embedding(len(keep), old_weights.shape[1], padding_idx=hf_model.config.pad_token_id)
    new_embedding.weight.data = old_weights[keep].clone()
    hf_model.embeddings.word_embeddings = new_embedding
    hf_model.config.vocab_size = len(keep)

    old_tok_json = hf_tokenizer.backend_tokenizer.to_str()
    new_tok_json, remap = prune_tokenizer(old_tok_json, keep)
    Tokenizer.from_str(new_tok_json).save(str(out_dir / "tokenizer.json"))

    old_tok, new_tok = Tokenizer.from_str(old_tok_json), Tokenizer.from_str(new_tok_json)
    ts = load_test_set()
    print(f"Tokenlaştırması değişen metin: test seti %{100 * changed_ratio(old_tok, new_tok, remap, ts['profile_texts'] + ts['listing_texts']):.1f}, "
          f"ayrılmış TR/EN cümleler %{100 * changed_ratio(old_tok, new_tok, remap, valid_texts):.1f}")

    fp32_path, int8_path = out_dir / "model.onnx", out_dir / "model_int8.onnx"
    print("ONNX'e aktarılıyor ve int8'e sıkıştırılıyor...")
    export_onnx(hf_model, Tokenizer.from_str(new_tok_json), fp32_path)
    quantize_dynamic(str(fp32_path), str(int8_path), weight_type=QuantType.QUInt8)
    for p in (fp32_path, int8_path):
        print(f"  {p.name}: {p.stat().st_size / 1e6:.0f} MB")
    return {"vocab_before": old_size, "vocab_after": len(keep)}


def run_quality(out_dir):
    ts = load_test_set()
    texts = ts["profile_texts"] + ts["listing_texts"]
    for name in ("model.onnx", "model_int8.onnx"):
        backend = LocalOnnxBackend(out_dir / name, out_dir / "tokenizer.json")
        sims = backend.embed_queries(ts["profile_texts"]) @ backend.embed_passages(ts["listing_texts"]).T
        metrics = evaluate(sims, ts)
        p50, p90 = measure_latency(backend, texts)
        print(f"=== küçültülmüş MiniLM, {name} ===")
        for key, value in metrics.items():
            print(f"  {key:<30} {value if isinstance(value, str) else f'{value:.3f}'}")
        print(f"  {'gecikme medyan / p90 (ms)':<30} {p50:.0f} / {p90:.0f}\n")


def run_memory_child(model_path, tokenizer_path):
    import psutil
    proc = psutil.Process(os.getpid())
    rss = lambda: proc.memory_info().rss / 1e6
    t0 = time.time()
    import fastapi  # noqa: F401  servis çatısının payını da ölçüme kat
    import onnxruntime  # noqa: F401
    t1 = time.time()
    after_import = rss()
    backend = LocalOnnxBackend(model_path, tokenizer_path)
    t2 = time.time()
    after_load = rss()
    backend.embed_passages(["ısınma"])
    print(f"{Path(model_path).name:<18} import {t1 - t0:5.1f} sn | model yükleme {t2 - t1:5.1f} sn | "
          f"bellek: kütüphaneler {after_import:4.0f} MB, model sonrası {after_load:4.0f} MB, "
          f"encode sonrası {rss():4.0f} MB")


def run_memory(out_dir):
    print("Karşılaştırma: küçültülmemiş resmi int8 model")
    subprocess.run([sys.executable, str(HERE / "benchmark.py"), "--memory", "--models", "minilm-onnx"], check=False)
    print("Küçültülmüş modeller")
    for name in ("model.onnx", "model_int8.onnx"):
        subprocess.run([sys.executable, __file__, "--memory-child", str(out_dir / name),
                        str(out_dir / "tokenizer.json")], check=False)


def main():
    parser = argparse.ArgumentParser(description="Kelime tablosu küçültülmüş MiniLM ölçümü")
    parser.add_argument("--out", default="pruned-minilm", help="model dosyalarının yazılacağı klasör")
    parser.add_argument("--corpus-rows", type=int, default=1_000_000, help="OPUS-100 en-tr satır sayısı (tamamı: 1.000.000)")
    parser.add_argument("--min-count", type=int, default=1, help="bir tokenın tutulması için en az geçiş sayısı")
    parser.add_argument("--skip-build", action="store_true", help="modeli yeniden üretmeden sadece ölç")
    parser.add_argument("--memory-child", nargs=2, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.memory_child:
        run_memory_child(*args.memory_child)
        return
    out_dir = Path(args.out)
    if not args.skip_build:
        build(out_dir, args.corpus_rows, args.min_count)
    print()
    run_quality(out_dir)
    run_memory(out_dir)


if __name__ == "__main__":
    main()
