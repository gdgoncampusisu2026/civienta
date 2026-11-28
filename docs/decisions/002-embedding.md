# 002 - Embedding model and AI service hosting

Date: 2026-11-26 (updated 2026-11-28 after review)
Owner: Buse
Status: accepted

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

Scripts: `services/ai/eval/benchmark.py` (quality, latency and memory measurements below; the Gemini key is read from an environment variable) and `services/ai/eval/prune_vocab.py` (builds and measures the reduced-vocabulary model, see Serving footprint).

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

### Official model files

| Setup (MiniLM) | Libraries only | Peak memory | Model load | Latency per text, median / p90 | Quality on the test set |
|---|---|---|---|---|---|
| PyTorch + sentence-transformers | 656 MB | 1089 MB | ~12 s (+11 s imports) | 79 / 134 ms | reference |
| ONNX Runtime, fp32 model | 97 MB | 911 MB | 6.4 s | - | identical to reference |
| ONNX Runtime, int8 model | 97 MB | 544 to 559 MB | 1.5 to 5 s | 50 / 115 ms (one thread) | recall@5 0.850, s+a 0.850, trap@5 0.325, 58/60, MRR 0.932 |

e5-small with PyTorch peaked at 1160 MB. The ONNX setup uses the official ONNX files published in the MiniLM model repository (`onnx/model.onnx`, `onnx/model_quint8_avx2.onnx`) with `tokenizers` and mean pooling, so PyTorch is not needed at all. The fp32 ONNX run reproduced the PyTorch scores exactly, which confirms the pipeline is equivalent. Turning ONNX Runtime graph optimizations off did not change the memory use. The official int8 model still needs about 545 MB, above the 512 MB of Render Free.

### Reduced vocabulary (Turkish and English only)

Most of this model's weights are its 250,037-token multilingual embedding table. `prune_vocab.py` keeps only the tokens that occur in Turkish and English text, rebuilds the tokenizer with the same token pieces, exports the model to ONNX and quantizes it to int8. The vocabulary was built from the 1,000,000 English-Turkish sentence pairs of OPUS-100 (2,000,000 sentences). The test set was not used to build it, so the quality check below is fair.

- Vocabulary: 250,037 -> **40,940 tokens**.
- Tokenization is unchanged for 99.8% of held-out OPUS sentences and for 92.5% of the test set texts (37 of 40). The other texts are split into slightly different sub-word pieces, mostly technical or product words.
- A first run with 300,000 sentence pairs gave 34,467 tokens but changed the tokenization of 40% of the test set texts, so the full corpus is used.

| Setup (MiniLM, reduced vocabulary) | Peak memory | Model load | File size | Latency per text, median / p90 | Quality on the test set |
|---|---|---|---|---|---|
| ONNX Runtime, fp32 | 330 MB | 0.5 s | 149 MB | 49 / 99 ms | recall@5 0.850, s+a 0.867, trap@5 0.325, 57/60, MRR 0.932 (same as reference) |
| **ONNX Runtime, int8** | **175 MB** | **0.3 s** | **38 MB** | **51 / 102 ms** | recall@5 0.850, s+a 0.850, trap@5 0.275, 58/60, MRR 0.930 |

The reduced int8 model keeps the quality of the official int8 model (MRR 0.930 vs 0.932, trap@5 0.275 vs 0.325) and needs about a third of its memory, leaving about 335 MB of headroom under 512 MB for FastAPI, the Firestore client and the vectors.

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
| Vercel (Hobby), Python functions | Yes | Not verified | Fallback only. The web app is hosted there already; running the AI service there was not tested. |

## Decision

**Model: paraphrase-multilingual-MiniLM-L12-v2 with a Turkish and English vocabulary (40,940 tokens), served with ONNX Runtime as an int8 model.** Vector dimension 384. Proposed `model` field value: `paraphrase-multilingual-MiniLM-L12-v2-tr-en-int8`. The benchmark decides between the two local models (decision 1): MiniLM is ahead on four of the five quality measures. The reduced int8 build keeps the quality of the official model and needs about 175 MB instead of about 545 MB. The e5 advantage (512-token limit) can be revisited if real listings turn out much longer than 128 tokens.

**Hosting: Render Free.** It is the only option found that runs a Python service for free without a card, and the reduced int8 model fits its 512 MB limit with room to spare (175 MB measured on Colab). The service was not deployed to Render in this spike; the first Sprint 2 service PR checks peak memory and start time on Render itself. Reasons: measuring on Render needs a running FastAPI service and a place to host the reduced model files, which is the production service work this task leaves to Sprint 2; and with 175 MB against a 512 MB limit, a Render measurement is unlikely to change the decision. If it does not fit there, the fallback to try is Vercel (Hobby, no card, not verified yet).

**Start-up reads (decisions of 2026-11-28 on the review of this ADR).**

1. **Keep the service awake.** One always-on free service fits within the 750 free instance hours a month, so a full load happens only after a deploy or a restart, not after every idle period. The keep-awake method (for example a scheduled ping) must be checked against Render's rules before it is used.
2. **Store many vectors in one document.** One vector is about 3 to 4 KB in Firestore, so one document (limit 1 MB) holds a few hundred vectors. A full load of about a thousand vectors then takes a few reads instead of one read per vector. This changes the `listingVectors` / `userVectors` layout; Serhan approved the change, and `docs/data-model.md` is updated in the Sprint 2 service PR.

Read cost with these two decisions:

- Full load (after a deploy or restart): one read per vector document. Example: 1,100 vectors at about 250 per document is 5 reads, instead of 1,100 (estimate, not measured). With the S0-07 seed (10 users, 15 listings) everything fits in one document per collection.
- While the process is running, it fetches only documents with `updatedAt` newer than its last sync (decision 3).
- These reads count toward the 50,000 daily reads (decision 2).

Cold start: after a deploy or restart, Render's own start plus ours. Ours measured on Colab: under 1 s of imports and about 0.3 s of model loading for the reduced int8 model, plus the Firestore load. Render has 0.1 CPU, so these will be slower there (not measured). The model and tokenizer files are built at build time with `prune_vocab.py`, not at every start.

## Consequences

- `services/ai` uses `onnxruntime`, `tokenizers` and the reduced model files, not PyTorch or sentence-transformers at run time. PyTorch is needed only to build the reduced model.
- The vocabulary is part of the model: rebuilding it from a different corpus changes the tokenizer, so all vectors must be re-embedded. The `model` field shows which vectors are stale. The same applies to any later model change.
- `docs/data-model.md`: the vector dimension (384) and the new vector document layout are added in the Sprint 2 service PR. This decision answers the open questions there about the embedding model and where the AI service runs.
- Sprint 2 checks: peak memory and start time on Render Free, and a keep-awake method that follows Render's rules.
- Limits of this spike: the test set is small (20 x 20) and synthetic, so the scores are a preliminary comparison, not general model quality. Two labels are borderline and are kept as written: P9 -> L17 (negative: the listing says "image editing", the profile edits photos, but the roles differ) and P2 -> L4 (strong, but outside the top 5 for all three models). Skill slugs in the test set are placeholders from before S0-11; they were not used for embedding. Measurements were taken on Colab, not on the target host.
- Not done, out of scope for this task: the production service and API endpoints (Sprint 2), Firestore vector search and indexes, real student data. The optional `findNearest` emulator check was skipped because decision 3 removed the dependency on Firestore vector search.
