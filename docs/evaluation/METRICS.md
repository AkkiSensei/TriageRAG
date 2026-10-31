# TriageRAG Evaluation Metrics Specification

> **Research prototype. Synthetic data only. Not a medical device. Not for clinical use.**

## 1. Overview and Purpose

This document provides the authoritative mathematical definitions, denominators, boundary condition handling, and clinical safety justifications for all retrieval and abstention evaluation metrics in TriageRAG (AUB-EVL-01, T4.4, T4.6).

---

## 2. Information Retrieval Metrics

Let $Q^+$ denote the set of non-abstaining clinical evaluation cases with ground-truth relevance grades. For each query $q \in Q^+$, let $\mathcal{T}_q$ denote the set of directly actionable protocol nodes with relevance grade $\text{rel}(c) \ge 2$.

### 2.1 Recall@k
Recall at rank $k$ measures whether at least one directly actionable (grade $\ge 2$) protocol node is retrieved within the top $k$ positions:

$$\text{Recall@}k = \frac{1}{|Q^+|} \sum_{q \in Q^+} \mathbb{I}\left(\exists i \le k : c_{q, i} \in \mathcal{T}_q\right)$$

- **Denominators:** Strictly evaluated over eligible positive cases ($|Q^+|$).
- **Reported cutoffs:** $k \in \{1, 3, 5, 10\}$.
- **Boundary conditions:** If $|Q^+| = 0$, returns $0.0\%$. If the retrieved list has fewer than $k$ candidates due to candidate pool limits, evaluation considers all available positions.

### 2.2 Mean Reciprocal Rank (MRR)
Mean Reciprocal Rank evaluates how high the first directly actionable node appears in the ranked output:

$$\text{MRR} = \frac{1}{|Q^+|} \sum_{q \in Q^+} \text{RR}_q$$

Where:
$$\text{RR}_q = \begin{cases} \frac{1}{\min \{i : c_{q, i} \in \mathcal{T}_q\}}, & \text{if } \exists i : c_{q, i} \in \mathcal{T}_q \\ 0, & \text{otherwise} \end{cases}$$

### 2.3 Normalized Discounted Cumulative Gain (nDCG@k)
nDCG evaluates multi-level graded relevance (where grade 2 = directly actionable, grade 1 = supporting, grade 0 = irrelevant):

$$\text{DCG@}k = \sum_{i=1}^k \frac{2^{\text{rel}(c_{q, i})} - 1}{\log_2(i + 1)}$$

$$\text{IDCG@}k = \sum_{i=1}^{\min(k, |\mathcal{R}_q|)} \frac{2^{\text{rel}^*(i)} - 1}{\log_2(i + 1)}$$

$$\text{nDCG@}k = \begin{cases} \frac{\text{DCG@}k}{\text{IDCG@}k}, & \text{if } \text{IDCG@}k > 0 \\ 0.0, & \text{otherwise} \end{cases}$$

Where $\text{rel}^*(i)$ represents the $i$-th highest relevance grade available for case $q$.
- **Reported cutoffs:** $k \in \{5, 10\}$.

---

## 3. Honest Error and Abstention Rates (AUB-EVL-01 / AUB-ABS-02)

Previous benchmarks conflated multiple failure modes into a single metric (`wrong_protocol_rate`). T4.4 separates these into distinct, honest failure rates.

### 3.1 False Accept Rate (FAR)
The fraction of cases designed for abstention (negative controls, unsupported syndromes, out-of-scope presentations) where the retrieval system incorrectly returned substantive protocol nodes:

$$\text{FAR} = \frac{\sum_{q \in Q^-} \mathbb{I}(\neg \text{abstained}_q)}{|Q^-|}$$

- **Safety Significance:** A non-zero FAR indicates ungrounded or out-of-domain protocol recommendations. The system safety gate requires $\text{FAR} \equiv 0.0$.

### 3.2 Wrong Syndrome Rate (WSR)
The fraction of non-abstaining cases where the retrieved protocol nodes belong to a clinical syndrome different from the indicated syndrome:

$$\text{WSR} = \frac{\sum_{q \in Q^+, \neg \text{abstained}_q} \mathbb{I}(\exists c \in \text{retrieved}_q : \text{syndrome}(c) \neq \text{expected\_syndrome}(q))}{\sum_{q \in Q^+} \mathbb{I}(\neg \text{abstained}_q)}$$

- **Safety Significance:** Retrieving protocols for the wrong condition (e.g. sepsis protocol for asthma) is dangerous. The safety gate requires $\text{WSR} \equiv 0.0$.

### 3.3 Legacy Wrong Protocol Rate (WPR)
Preserved strictly for backwards compatibility:

$$\text{WPR} = \frac{\text{False Accepts} + \text{Wrong Syndrome Cases}}{|Q_{\text{all}}|}$$

### 3.4 Per-AbstainCode Precision and Recall
For each active `AbstainCode` $c \in \mathcal{C}$ (e.g. `NORMAL_VITALS_NO_SYNDROME`, `UNSUPPORTED_SYNDROME`, `OUT_OF_FORMULARY`, `EMPTY_QUERY`):

$$\text{Precision}(c) = \frac{\text{TP}_c}{\text{Predicted}_c} \quad (\text{if } \text{Predicted}_c = 0 \implies 1.0)$$

$$\text{Recall}(c) = \frac{\text{TP}_c}{\text{Support}_c} \quad (\text{if } \text{Support}_c = 0 \implies 1.0)$$

---

## 4. Expected Calibration Error (ECE)

ECE measures the alignment between retrieval confidence scores and empirical correctness:

$$\text{ECE} = \sum_{m=1}^M \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$

Where predictions are partitioned into $M=5$ equal-width confidence bins $B_1, \dots, B_M \subseteq [0, 1]$.
- **Honesty Rule:** ECE is computed strictly over real continuous confidence scores ($p = \text{normalize\_relevance\_score}(\text{score})$). No artificial or hardcoded confidence values (such as 0.95) are permitted.

---

## 5. Inter-Annotator Agreement (Cohen's $\kappa$)

For two independent raters assigning categorical grades $\{0, 1, 2\}$ across $N$ items:

$$\kappa = \frac{P_o - P_e}{1 - P_e}$$

Where:
- $P_o = \frac{1}{N} \sum_{i=1}^k C[i][i]$ is observed proportion of agreement.
- $P_e = \sum_{i=1}^k p_{A, i} \cdot p_{B, i}$ is expected proportion of chance agreement.
- If $P_e = 1.0$, $\kappa = 1.0$ if $P_o = 1.0$, else $0.0$.

---

## 6. Cluster-Robust Bootstrap Confidence Intervals

Standard i.i.d. bootstrap resampling overestimates confidence when multiple test cases share the same underlying clinical scenario template.

TriageRAG uses **template-level cluster bootstrap**:
1. Given $M$ template clusters $\{G_1, \dots, G_M\}$, sample $M$ clusters with replacement $B=1000$ times.
2. Pool all cases belonging to the sampled clusters for that iteration.
3. Compute the mean evaluation metric $\theta^{*, b}$.
4. Report the empirical 2.5th and 97.5th percentiles $[\theta^*_{0.025}, \theta^*_{0.975}]$.
