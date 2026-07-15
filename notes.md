# Architectural Evaluation: Search Quality Analysis & Design Decisions

This document details the critical engineering decisions, evaluation metrics, and architectural outcomes derived from the **Search Quality Sanity Check** performed on the Roman Urdu Fake News dataset.

---

## 1. Objective of the Experiment
The primary goal of this sanity check was to evaluate the indexing capability of modern semantic search engines (specifically **Tavily API**) when processing raw, conversational Roman Urdu inputs vs. structured English translations. The outcome directly informs our retrieval-augmented generation (RAG) routing architecture.

---

## 2. Methodology & Test Cases
Using `search_sanity_checker.py`, comparative advanced queries were run across a curated subset of claims ($N=5$) with 2-result limitations. 

*   **Test A (Baseline):** Raw user input (Roman Urdu).
*   **Test B (Proposed):** Semantic English translation/concept extraction.

---

## 3. Key Findings & Diagnostic Anomalies

During the baseline testing, significant query-mismatch anomalies were identified:

### Case Study A: Conversational Particle Pollution
*   **Query Input (Roman Urdu):** `"Sindh Education Department ki taraf se ek notification aayi hai ke tamam public aur private schools 15 April 2026 tak band rahenge"`
*   **Observation:** The search engine prioritized common Pakistani blogs/forums containing chat particles like `"ki taraf se"`, `"aayi"` and `"rahenge"` rather than official government archives.
*   **Anomalous Return:** Diverted search results index to low-authority creative writing/blog directories (e.g., `xahani.com`).

### Case Study B: Semantic Drift & Token Misalignment
*   **Query Input (Roman Urdu):** `"Shower lete waqt apna electric geyser band na karna jaanlewa sabit ho sakta hai"`
*   **Observation:** Token collision occurred with common auxiliary verbs `"apna"` and `"karna"`.
*   **Anomalous Return:** The query drifted towards non-related consumer tech-support platforms (e.g., *Microsoft Q&A Windows 11 updates*) because of string-similarity matching on structural Roman Urdu filler tokens rather than physical safety domains.

### Case Study C: Lack of Authoritative Fact-Check Retrieval
*   **Query Input (Roman Urdu):** `"Maryam Nawaz ki beti ne sirf 13 saal mein graduate kiya"`
*   **Observation:** Direct Roman Urdu search was trapped in Echo Chambers—returning original viral Facebook posts reinforcing the **false claim itself**.
*   **English Search Conversion:** Instantly matched and retrieved authoritative debunking indexes from accredited local bodies (e.g., *Soch Fact Check* and *Geo Fact Check*).

---

## 4. Final System Architecture Decisions

Based on the quantitative and qualitative outcomes of this evaluation, we reject direct query execution of Roman Urdu at the retrieval stage. The RAG pipeline will implement a mandatory **Query Pre-Processing / Transformation Layer**:

             +──────────────────────────+
             │  User Input (Roman Urdu) │
             +─────────────┬────────────+
                           │
                           ▼
           +──────────────────────────────+
           │   LLM Query Transformation   │
           │  - Remove structural filler  │
           │  - Translate/Extract concept │
           +─────────────┬──────────────+
                           │  (Refined English Query)
                           ▼
           +──────────────────────────────+
           │      Tavily Search API       │
           │  - Highly curated extraction │
           │  - Verified domain matching  │
           +─────────────┬──────────────+
                           │  (Accurate Evidence Snippets)
                           ▼
           +──────────────────────────────+
           │   LLM Verification Pipeline  │
           │  - Evaluate search evidence  │
           │  - Generate final verdict    │
           +──────────────────────────────+

### Architectural Justification:
1.  **Reduction of Token Noise:** Stripping out grammatical filler words (*"ki taraf se"*, *"sehar me"*) drastically reduces false-positive matches in non-credible forums.
2.  **Access to Verified Fact-Checks:** Leading fact-checkers in South Asia archive their primary English metadata. Translating the search query ensures direct hitting of these verified repositories.
3.  **Accuracy and Latency Optimization:** By minimizing irrelevant search returns, we prevent context-window clutter in the generator LLM, leading to more cost-effective token utilization and higher factual precision.