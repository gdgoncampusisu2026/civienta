"""S0-10 embedding benchmark'ı (Issue #11).

Sahte test seti (s010_test_set.json) üzerinde embedding modellerini karşılaştırır:
kalite (recall@5, tuzak@5, MRR, strong > negatif), tek metin gecikmesi ve bellek.
Yalnızca sahte veriyle çalışır. Gerçek öğrenci verisi bu script'e verilmez.

Kurulum:
    pip install numpy psutil fastapi sentence-transformers onnxruntime tokenizers huggingface_hub
    pip install google-genai   # yalnızca Gemini ölçümü için

Kullanım:
    python benchmark.py                          # yerel modeller: kalite + gecikme
    python benchmark.py --models minilm-onnx     # tek model
    python benchmark.py --memory                 # bellek ve açılış süresi (her model ayrı süreçte)
    GEMINI_API_KEY=... python benchmark.py --models gemini

API anahtarı yalnızca ortam değişkeninden okunur. Koda ya da repoya yazılmaz.
"""

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TEST_SET = HERE / "s010_test_set.json"

MINILM = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
E5 = "intfloat/multilingual-e5-small"
GEMINI = "gemini-embedding-001"

LOCAL_MODELS = ["minilm", "e5", "minilm-onnx"]
ALL_MODELS = LOCAL_MODELS + ["gemini"]


# ---------------------------------------------------------------------------
# Embedding arka uçları. Her biri profil ve ilan metinleri için
# L2 normalize edilmiş vektör döndürür (kosinüs = iç çarpım).
# ---------------------------------------------------------------------------

def normalize(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


class SentenceTransformerBackend:
    """PyTorch ile sentence-transformers. Benchmark'ın referans kurulumu."""

    def __init__(self, name, query_prefix="", passage_prefix=""):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(name, device="cpu")
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        # Yeni sürümlerde metodun adı değişti, eski sürümlerle de çalışsın
        get_dim = getattr(self.model, "get_embedding_dimension", None) or self.model.get_sentence_embedding_dimension
        self.dim = get_dim()

    def embed_queries(self, texts):
        return self.model.encode([self.query_prefix + t for t in texts], normalize_embeddings=True)

    def embed_passages(self, texts):
        return self.model.encode([self.passage_prefix + t for t in texts], normalize_embeddings=True)


class OnnxMiniLMBackend:
    """PyTorch'suz MiniLM: ONNX Runtime + int8 model + mean pooling.

    Önerilen üretim kurulumu. Model, Hugging Face'teki resmi ONNX dosyalarından indirilir.
    """

    def __init__(self, variant="int8"):
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download, list_repo_files
        from tokenizers import Tokenizer

        if variant == "fp32":
            file = "onnx/model.onnx"
        else:
            onnx_files = [f for f in list_repo_files(MINILM) if f.startswith("onnx/") and f.endswith(".onnx")]
            preferred = ["model_quint8_avx2", "model_qint8_avx2", "model_qint8_arm64"]
            file = next((f for p in preferred for f in onnx_files if p in f), None)
            if file is None:
                raise RuntimeError(f"int8 ONNX modeli bulunamadı: {onnx_files}")
        self.file = file

        self.tokenizer = Tokenizer.from_file(hf_hub_download(MINILM, "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=128)  # sentence-transformers ile aynı sınır
        self.tokenizer.enable_padding(pad_id=1, pad_token="<pad>")  # XLM-R pad token'ı

        options = ort.SessionOptions()
        options.enable_cpu_mem_arena = False  # ek bellek havuzunu kapat
        options.intra_op_num_threads = 1
        self.session = ort.InferenceSession(
            hf_hub_download(MINILM, file), options, providers=["CPUExecutionProvider"]
        )
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
        return normalize((tokens * m).sum(1) / m.sum(1))  # mean pooling

    embed_queries = _embed
    embed_passages = _embed


class GeminiBackend:
    """Gemini embedding API. Yalnızca sahte test setiyle kullanılır (Karar 1)."""

    def __init__(self):
        from google import genai
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY ortam değişkeni tanımlı değil, Gemini atlanıyor")
        self.client = genai.Client(api_key=key)
        self.dim = 768

    def _embed(self, texts, task_type):
        from google.genai import types
        out = self.client.models.embed_content(
            model=GEMINI,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.dim),
        )
        return normalize([e.values for e in out.embeddings])

    def embed_queries(self, texts):
        return self._embed(texts, "RETRIEVAL_QUERY")

    def embed_passages(self, texts):
        return self._embed(texts, "RETRIEVAL_DOCUMENT")


def load_backend(key):
    if key == "minilm":
        return SentenceTransformerBackend(MINILM)
    if key == "e5":
        # e5 modeli sorgu ve doküman için önek ister
        return SentenceTransformerBackend(E5, query_prefix="query: ", passage_prefix="passage: ")
    if key == "minilm-onnx":
        return OnnxMiniLMBackend("int8")
    if key == "minilm-onnx-fp32":
        return OnnxMiniLMBackend("fp32")
    if key == "gemini":
        return GeminiBackend()
    raise ValueError(f"Bilinmeyen model: {key}")


# ---------------------------------------------------------------------------
# Test seti ve metrikler
# ---------------------------------------------------------------------------

def load_test_set(path=TEST_SET):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    profiles, listings = data["profiles"], data["listings"]
    return {
        "profile_ids": [p["id"] for p in profiles],
        "listing_ids": [l["id"] for l in listings],
        # Profilden yalnızca bio, ilandan başlık + açıklama embed edilir
        "profile_texts": [p["bio"] for p in profiles],
        "listing_texts": [l["title"] + ". " + l["description"] for l in listings],
        "strong": {p["id"]: set(p["strong"]) for p in profiles},
        "acceptable": {p["id"]: set(p["acceptable"]) for p in profiles},
        "negative": {p["id"]: {n["id"] for n in p["should_not_match"]} for p in profiles},
    }


def evaluate(sims, ts, k=5):
    """Benzerlik matrisinden (profil x ilan) özet metrikleri hesaplar."""
    rec_s, rec_sa, trap, rr = [], [], [], []
    wins = total = 0
    for i, pid in enumerate(ts["profile_ids"]):
        order = list(np.argsort(-sims[i]))
        pos = {ts["listing_ids"][j]: r + 1 for r, j in enumerate(order)}  # 1 = en üst
        top = {ts["listing_ids"][j] for j in order[:k]}
        s, a, n = ts["strong"][pid], ts["acceptable"][pid], ts["negative"][pid]
        rec_s.append(len(top & s) / len(s))
        rec_sa.append(len(top & (s | a)) / len(s | a))
        trap.append(len(top & n) / len(n))
        rr.append(1 / min(pos[x] for x in s))
        for x in s:
            for y in n:
                total += 1
                wins += pos[x] < pos[y]
    return {
        "recall@5 (strong)": float(np.mean(rec_s)),
        "recall@5 (strong+acceptable)": float(np.mean(rec_sa)),
        "trap@5": float(np.mean(trap)),
        "strong>negative": f"{wins}/{total}",
        "MRR": float(np.mean(rr)),
    }


def measure_latency(backend, texts, rounds=3):
    """Tek metin embedding süresi (ms): medyan ve p90."""
    backend.embed_passages(texts[:3])  # ısınma
    times = []
    for _ in range(rounds):
        for t in texts:
            t0 = time.perf_counter()
            backend.embed_passages([t])
            times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    return statistics.median(times), times[int(len(times) * 0.9)]


def run_quality(models, latency_rounds):
    ts = load_test_set()
    print(f"Test seti: {len(ts['profile_ids'])} profil, {len(ts['listing_ids'])} ilan\n")
    for key in models:
        try:
            backend = load_backend(key)
        except RuntimeError as err:
            print(f"[{key}] {err}\n")
            continue
        sims = backend.embed_queries(ts["profile_texts"]) @ backend.embed_passages(ts["listing_texts"]).T
        metrics = evaluate(sims, ts)
        # Gemini'de istek sayısını düşük tut (ücretsiz kota)
        rounds = 1 if key == "gemini" else latency_rounds
        p50, p90 = measure_latency(backend, ts["profile_texts"] + ts["listing_texts"], rounds)
        print(f"=== {key} (boyut {backend.dim}) ===")
        for name, value in metrics.items():
            print(f"  {name:<30} {value if isinstance(value, str) else f'{value:.3f}'}")
        print(f"  {'gecikme medyan / p90 (ms)':<30} {p50:.0f} / {p90:.0f}\n")


# ---------------------------------------------------------------------------
# Bellek ve açılış süresi: her model temiz bir Python sürecinde ölçülür
# ---------------------------------------------------------------------------

def run_memory_child(key):
    import psutil
    proc = psutil.Process(os.getpid())
    rss = lambda: proc.memory_info().rss / 1e6
    t0 = time.time()
    import fastapi  # noqa: F401  servis çatısının payını da ölçüme kat
    if key in ("minilm", "e5"):
        import sentence_transformers  # noqa: F401
    else:
        import onnxruntime  # noqa: F401
    t1 = time.time()
    after_import = rss()
    backend = load_backend(key)
    t2 = time.time()
    after_load = rss()
    backend.embed_passages(["ısınma"])
    peak = rss()
    print(f"{key:<18} import {t1 - t0:5.1f} sn | model yükleme {t2 - t1:5.1f} sn | "
          f"bellek: kütüphaneler {after_import:4.0f} MB, model sonrası {after_load:4.0f} MB, "
          f"encode sonrası {peak:4.0f} MB")


def run_memory(models):
    print("Not: model ilk çalıştırmada indirilir, ikinci çalıştırma önbellekten yükler.\n")
    for key in models:
        if key == "gemini":
            continue  # API, sunucuda bellek kullanmaz
        subprocess.run([sys.executable, __file__, "--memory-child", key], check=False)


def main():
    parser = argparse.ArgumentParser(description="S0-10 embedding benchmark'ı")
    parser.add_argument("--models", nargs="+", default=LOCAL_MODELS,
                        choices=ALL_MODELS + ["minilm-onnx-fp32"])
    parser.add_argument("--memory", action="store_true", help="bellek ve açılış süresini ölç")
    parser.add_argument("--latency-rounds", type=int, default=3)
    parser.add_argument("--memory-child", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.memory_child:
        run_memory_child(args.memory_child)
    elif args.memory:
        run_memory(args.models)
    else:
        run_quality(args.models, args.latency_rounds)


if __name__ == "__main__":
    main()
