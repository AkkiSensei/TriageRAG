# TriageRAG — 4-Arm Retrieval Ablation Study (FG-08 / FG-14 / HD-5)

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## 1. Held-Out Test Split Performance (n=88, Graded Relevance)

| Arm / Backend | Held-Out Test Recall@5 (95% CI) | Test MRR (95% CI) | Wrong-Protocol Rate | Hard-Neg Abstain | Latency p95 (ms) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Arm 1: Lexical BM25 (Default)** (`bm25`) | 73.21% [60.71%, 83.93%] | 0.5417 [0.4375, 0.6577] | 0.0000 | 1.0000 | 0.12 |
| **Arm 2: Char-Trigram TF-IDF Vector Retriever (CharNgramRetriever)** (`char_ngram`) | 73.21% [60.71%, 83.93%] | 0.5045 [0.4107, 0.6205] | 0.0000 | 1.0000 | 0.23 |
| **Arm 3: Hybrid Reciprocal Rank Fusion (BM25 + CharNgram)** (`hybrid_rrf`) | 73.21% [60.71%, 83.93%] | 0.5491 [0.4464, 0.6607] | 0.0000 | 1.0000 | 0.11 |
| **Arm 4: Hybrid RRF + Lexical Overlap Reranker (LexicalOverlapReranker)** (`hybrid_rrf_rerank`) | 73.21% [60.71%, 83.93%] | 0.5491 [0.4464, 0.6607] | 0.0000 | 1.0000 | 0.41 |

## 2. Programmatic Decision Rule & Outcome (`decide_backend`)

Deterministic rule (`decide_backend`) selected: **`bm25`**.

### Selection Criteria (Codified):
1. **Hard Safety Constraints:** Must achieve `wrong_protocol_rate == 0.0`, `hard_negative_abstain_recall == 1.0`, and `latency_p95_ms < 50.0 ms`.
2. **Adoption Threshold:** An alternative stage is adopted only if its test Recall@5 does not regress vs `bm25` AND its test MRR improves by at least `+0.05`.
3. **Outcome:** In accordance with this rule, `bm25` is chosen as the default production backend.

> **Component Honesty Disclosure (FG-14 / HD-5):** What was previously referred to as 'Dense' is implemented as an offline character trigram TF-IDF cosine retriever (`CharNgramRetriever`), and the reranker is a token overlap ratio estimator (`LexicalOverlapReranker`). Neither utilizes a deep neural cross-encoder or neural dense embedding model in offline baseline mode (`HD-5`).
