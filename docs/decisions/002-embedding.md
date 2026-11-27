# 002 - Embedding model and AI service hosting

Date: 2026-11-26
Owner: Buse
Status: proposed

## Context

"Recommended listings" (MVP, Sprint 2) matches student profiles to listings by embedding similarity. S0-10 (#11) has to pick the embedding model and propose where the AI service (`services/ai`, FastAPI) can run for free.

Framework decisions from 2026-11-23 (Serhan's "Sprint 0 technical decisions" and `docs/data-model.md`) that this decision follows:

1. **Data and embedding.** Real student data is embedded with a local model only (multilingual-e5-small or paraphrase-multilingual-MiniLM-L12-v2, chosen by this benchmark). The Gemini embedding API is used only in the benchmark, on the synthetic test set. Reasons: on the unpaid tier Google may use submitted content to improve its products and human reviewers may read it; the paid tier needs a billing account (card), which breaks the "no credit card" rule in `AGENTS.md`; profiles are personal data and sending them abroad can be a KVKK issue (not legal advice). The live Gemini API terms were re-checked on 2026-11-26 (page last updated 2026-04-28): they still say not to submit sensitive, confidential or personal information to the unpaid services, and that API access counts as paid only through a Cloud project with active billing.
2. **Firestore quota.** We stay on Spark (50,000 reads and 20,000 writes per day, 1 GiB storage). Reads made by the AI service count toward the same quota.
3. **Vector search.** No Firestore vector search. The AI service loads the vectors into memory and computes cosine similarity itself. Vectors are stored as a plain `number[]` in the `embedding` field of `listingVectors` and `userVectors`. After the first load, the service should fetch only documents changed since the last sync (`updatedAt`).

Constraints: free plans only, no card, no Cloud Functions, synthetic data only in this spike.

## Benchmark

### Test set

`services/ai/eval/s010_test_set.json`: 20 synthetic profiles and 20 synthetic listings, 10 Turkish and 10 English each, mixed short, medium and long texts. For every profile the matching listings were labeled by hand: 30 `strong`, 13 `acceptable` and 40 `should_not_match` (traps, each with a written reason). Unlabeled listings are neutral. Labels were fixed before the results were seen and were not changed afterwards.

Embedded text: the profile `bio`, and the listing `title + ". " + description`. Skill slugs were not used. For e5 the `query: ` / `passage: ` prefixes were added. For Gemini the `RETRIEVAL_QUERY` / `RETRIEVAL_DOCUMENT` task types were used, at 768 dimensions.

Script: `services/ai/eval/benchmark.py` (runs the quality, latency and memory measurements below; the Gemini key is read from an environment variable).

### Metrics

- **recall@5 (strong)**: share of a profile's `strong` listings that appear in its top 5. With 20 listings, a random order scores about 0.25.
- **recall@5 (strong+acceptable)**: the same, counting `acceptable` listings too.
- **trap@5**: share of a profile's `should_not_match` listings that appear in its top 5 (lower is better).
- **strong > negative**: in how many of the 60 (strong, negative) pairs the strong listing ranks above the negative one.
- **MRR**: mean of 1 / rank of the first `strong` listing.

### Results (Colab CPU)

| Metric | MiniLM | e5-small | Gemini 001 |
|---|---|---|---|
| recall@5 (strong) | 0.850 | 0.825 | **0.975** |
| recall@5 (strong+acceptable) | 0.867 | 0.846 | **0.954** |
| trap@5 (lower is better) | 0.325 | **0.275** | 0.425 |
| strong > negative (of 60) | 57 | 54 | **59** |
| MRR | 0.932 | 0.871 | **0.967** |
| Latency per text, median / p90 | 79 / 134 ms | 74 / 145 ms | 156 / 171 ms (incl. network) |
| Vector dimension | 384 | 384 | 768 |
| Model size | ~118M parameters | ~118M parameters | API |
| Max input | 128 tokens | 512 tokens | - |
| Cost | $0 (runs on our server) | $0 (runs on our server) | $0 on the unpaid tier, but excluded for real data (decision 1); paid tier needs a card |

Observations:

- Gemini is clearly the best on quality, but it is excluded for real data by decision 1. It stays in the table as a reference.
- The difference between MiniLM and e5 is small and within noise for a 20 x 20 set: one profile can move the averages. MiniLM leads on four of the five quality measures; e5 has the lower trap@5 and a longer input limit.
- MiniLM truncates at 128 tokens, which cut 4 of the 20 listings (L3, L10, L16, L18). Raising the limit to 256 changed recall@5 from 0.850 to 0.900 but lowered MRR from 0.932 to 0.906, so the effect is small and mixed. It matters more if real listings are longer.
- Shared weaknesses of both local models: the short, misspelled profile P17 ("yazilim ogrencisiyim node ogrenmek isterim") gets 0.00 recall from both; a common word such as "Python" pulls unrelated listings up; negations ("I don't write code") are not understood well; a few long, generic listings appear in many top 5 lists.
- Latency is not a concern: embeddings are computed once when a profile or listing is saved, not on every request.

## Serving footprint

The service has to fit a free host, so memory and start time were measured for each setup in a fresh Python process (Colab, CPU, FastAPI imported to include the framework). "Peak" is the resident memory after loading the model and embedding one text.

| Setup (MiniLM) | Libraries only | Peak memory | Model load | Latency per text, median / p90 | Quality on the test set |
|---|---|---|---|---|---|
| PyTorch + sentence-transformers | 656 MB | 1089 MB | ~12 s (+11 s imports) | 79 / 134 ms | reference |
| ONNX Runtime, fp32 model | 97 MB | 911 MB | 6.4 s | - | identical to reference |
| **ONNX Runtime, int8 model** | **97 MB** | **~545 MB** | **~1.5 s** | **50 / 115 ms** (one thread) | recall@5 0.850, s+a 0.850, trap@5 0.325, 58/60, MRR 0.932 |

e5-small with PyTorch peaked at 1160 MB. The ONNX setup uses the official ONNX files published in the MiniLM model repository (`onnx/model.onnx`, `onnx/model_quint8_avx2.onnx`) with `tokenizers` and mean pooling, so PyTorch is not needed at all. The fp32 ONNX run reproduced the PyTorch scores exactly, which confirms the pipeline is equivalent. The int8 model gave the same recall@5 and MRR; one acceptable listing dropped out of a top 5 and one more strong/negative pair was ranked correctly. Turning ONNX Runtime graph optimizations off did not change the memory use (544 to 548 MB at all levels).

Vectors themselves are small: 384 float32 values are 1.5 KB, so 10,000 vectors take about 15 MB of memory.

## Options

### Model

1. **paraphrase-multilingual-MiniLM-L12-v2**: slightly better than e5 on our set, official ONNX int8 files available, 384 dimensions. Con: 128-token input limit.
2. **multilingual-e5-small**: lowest trap@5, 512-token limit, 384 dimensions. Con: slightly lower recall and MRR on our set, needs query/passage prefixes, ONNX not tested in this spike.
3. **Gemini embedding API**: best quality, no hosting needed. Excluded for real data by decision 1.

### Hosting

| Option | Free without a card | Can run the service | Notes |
|---|---|---|---|
| Firebase (Spark) | Yes | No | Cloud Functions and Cloud Run need Blaze (card). |
| Google Cloud Run | No | Yes | Free quota exists, but a billing account (card) is required. |
| Hugging Face Spaces | No | Yes | The docs say Spaces that run compute (Gradio or Docker) now need a paid plan; only static Spaces are free. |
| Gemini API, Cloudflare Workers AI | - | Not a host for our model | Both send profile text to an external AI API, which decision 1 rules out for real data. Workers AI was not tested. |
| **Render, Free instance** | Yes | Yes | 512 MB RAM, 0.1 CPU, 750 free instance hours per month per workspace. Spins down after 15 minutes without traffic and takes about a minute to spin back up. The local filesystem is ephemeral, so anything cached on disk is lost on spin-down, restart or redeploy. |

## Decision

**Model: paraphrase-multilingual-MiniLM-L12-v2, served with ONNX Runtime and the int8 model.** Vector dimension 384, `model` field value `paraphrase-multilingual-MiniLM-L12-v2-int8` (proposal). The benchmark decides between the two local models (decision 1): MiniLM is ahead on four of the five quality measures, and its official int8 ONNX build keeps the same quality while cutting memory in half and load time to about 1.5 s. The e5 advantage (512-token limit) can be revisited if real listings turn out much longer than 128 tokens.

**Hosting (proposal): Render Free, with one open blocker.** Render Free is the only option found that runs a Python service for free without a card. The measured peak of about 545 MB is still above its 512 MB limit, so it does not fit yet. Proposed next step in Sprint 2, before the service is built: reduce the model's memory further and re-measure on Render itself. The most likely lever is the vocabulary: most of this model's weights are a 250,000-token multilingual embedding table, and keeping only the tokens needed for Turkish and English should shrink it (not measured yet). If it still does not fit, Serhan decides the next step; paid plans stay out under the current rules.

**Start-up reads (decision 3).**

- First start: one read per document in `userVectors` and `listingVectors`, i.e. users + listings. With the S0-07 seed (10 users, 15 listings) that is 25 reads; the benchmark set corresponds to 40. Example pilot size: 1,000 users and 100 listings would be 1,100 reads per start (estimate, not measured).
- While the process is running, it fetches only documents with `updatedAt` newer than its last sync.
- On Render Free every spin-down loses the process and its disk, so every wake-up is a full first start again. The number of reads per day is therefore users + listings multiplied by the number of wake-ups. These reads count toward the 50,000 daily reads (decision 2).

Cold start on Render Free: about a minute of platform spin-up (Render's figure) plus our own start. Our own start measured on Colab: under 1 s of imports and about 1.5 s of model loading for ONNX int8, plus the Firestore load. Render has 0.1 CPU, so these will be slower there (not measured). The model file should be downloaded at build time, not at every start.

## Consequences

- `services/ai` uses `onnxruntime`, `tokenizers` and `huggingface_hub`, not PyTorch or sentence-transformers.
- `docs/data-model.md`: when this decision is accepted, the vector dimension becomes 384 and open question 2 is answered. Open question 3 (hosting) stays open until the memory blocker is solved.
- If the model ever changes, all vectors are re-embedded; the `model` field shows which vectors are stale.
- Questions for Serhan:
  1. Is the read cost of full reloads after every Render wake-up acceptable, or should the start-up reads be reduced? Possible ways: keep the service awake (one always-on free service fits within 750 hours a month), or store several vectors per document, which would change `docs/data-model.md`.
  2. Is "reduce the model's memory and re-measure on Render" the right Sprint 2 task, and what is the fallback if it still does not fit 512 MB?
- Limits of this spike: the test set is small (20 x 20) and synthetic, so the scores are a preliminary comparison, not general model quality. Two labels are borderline and are kept as written: P9 -> L17 (negative: the listing says "image editing", the profile edits photos, but the roles differ) and P2 -> L4 (strong, but outside the top 5 for all three models). Skill slugs in the test set are placeholders from before S0-11; they were not used for embedding. Measurements were taken on Colab, not on the target host.
- Not done, out of scope for this task: the production service and API endpoints (Sprint 2), Firestore vector search and indexes, real student data. The optional `findNearest` emulator check was skipped because decision 3 removed the dependency on Firestore vector search.
