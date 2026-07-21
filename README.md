
# Tehqeeq — Roman Urdu Misinformation Verification Tool

Tehqeeq (تحقیق — "investigation") is a research-oriented proof-of-concept that verifies suspicious claims written in **Roman Urdu, Urdu, or English** against live web evidence, and returns a verdict — **True, False, Misleading, or Uncertain** — with supporting sources and confidence.

It was built to address a specific gap: most fact-checking tools are English-first and don't handle Roman Urdu (Urdu written in Latin script), which is how the majority of WhatsApp-forwarded misinformation actually circulates in Pakistan.

**No login. No download. No app to install.** Paste a message, get a verdict.

---

## Why This Exists

Mainstream fact-checking tools (Google's Fact Check Explorer, Snopes, PolitiFact-style checkers) are built around clean English text. Misinformation in Pakistan overwhelmingly spreads through **Roman Urdu WhatsApp forwards** — a script with no standardized spelling ("qeemat" / "qeematon" / "kimat" all mean the same thing) — which these tools were never designed to parse.

Tehqeeq closes that gap: it accepts a raw, informally-written message in Roman Urdu (or English, or Urdu script), extracts the core factual claim, searches the live web for evidence, and returns a verdict grounded only in what that evidence actually shows.

---

## Live Link
will be added soon

---

## 📸 Preview
---


## How It Works

```
User message (Roman Urdu / Urdu / English)
        │
        ▼
┌─────────────────────┐
│ 1. Claim Extraction  │  Translates + distills the core checkable claim.
│    (extractor.py)    │  Resolves relative time words ("kal") into an
│                       │  explicit date using the actual current date.
└──────────┬───────────┘
           ▼
┌─────────────────────┐
│ 2. Evidence Search    │  Live web search (Tavily). Results are tagged
│    (searcher.py)      │  [TRUSTED] / [UNVERIFIED] by domain, and date-
│                       │  filtered for claims about recent events.
└──────────┬───────────┘
           ▼
┌─────────────────────┐
│ 2b. Calendar Lookup   │  For Hijri-calendar-dependent claims (Ramadan,
│    (calendar_tool.py) │  Eid), a deterministic date-conversion API
│    [conditional]      │  supplements search, since news coverage for
│                       │  these claims often doesn't exist until the
│                       │  event is imminent.
└──────────┬───────────┘
           ▼
┌─────────────────────┐
│ 3. Verdict Generation │  LLM classifies the claim as true / false /
│    (verifier.py)      │  misleading / uncertain, using ONLY the
│                       │  retrieved evidence — never its own prior
│                       │  knowledge, to avoid hallucinated verdicts.
└──────────┬───────────┘
           ▼
┌─────────────────────┐
│ 4. Output Translation │  Verdict + reasoning + source titles are
│    (translator.py)    │  translated into Roman Urdu and Urdu script,
│                       │  so the result is usable by readers who can't
│                       │  read English or Urdu script.
└──────────┬───────────┘
           ▼
   FastAPI endpoint (main.py) → Frontend (HTML/CSS/JS)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM reasoning | Groq API (Llama 3.3 70B / Llama 3.1 8B) |
| Live web search | Tavily Search API |
| Calendar verification | Aladhan API (Hijri date conversion) |
| Backend | FastAPI |
| Frontend | HTML / CSS / vanilla JavaScript |
| Evaluation | Custom-built, manually labeled 80-example benchmark dataset |

**No model was fine-tuned or trained for this project.** Roman Urdu handling is achieved entirely through prompt engineering against pre-trained LLMs — the pipeline, evidence-grounding, and error-handling architecture is the engineering contribution, not model training.

---

## Verdict Categories

- **True** — evidence supports the claim's core assertion.
- **False** — evidence contradicts the claim.
- **Misleading** — the claim is a real event or fact, but substantially exaggerated, stripped of context, or wrapped in a false narrative (e.g. a real safety concern reframed with false urgency, or a real photo attached to a fabricated explanation).
- **Uncertain** — evidence is insufficient, absent, or conflicting. Reserved as a last resort, not a default — the system is explicitly instructed not to retreat to "uncertain" when it can identify *how* a claim relates to the evidence.

---

## Evaluation

Tested against an 80-example, manually labeled dataset spanning Health, Politics, Education, Entertainment, Tech, and Natural Disaster claims (curated from Soch Fact Check, Geo Fact Check, and other verified sources).

**Current benchmark accuracy: ~61%**, up from an initial 45% after a multi-round debugging and prompt-refinement process (see `NOTES.md` for the full iteration log).

Category-level performance is uneven — Education and Entertainment claims are verified more reliably than Politics and Tech, largely due to search evidence availability rather than model reasoning failures.

### Known limitations (documented honestly, not hidden)
- **Fresh/unconfirmed claims**: claims with no online record yet (very recent WhatsApp-only rumors) cannot be verified — there is nothing to search for.
- **Hyper-local claims**: claims that will never be covered by any indexed source are unverifiable by design.
- **Search-dependent accuracy**: verdict quality is bounded by what the search API surfaces, not just by the reasoning layer.
- **This is a research prototype**, not a production-grade, 99%-accurate fact-checker.

---

## Project structure:
```
tehqeeq/
├── backend/
│   ├── main.py                  # FastAPI backend entrypoint & endpoints
│   ├── pipeline.py              # Orchestrator for steps 1–4
│   ├── extractor.py             # Step 1: Claim extraction & translation
│   ├── searcher.py              # Step 2: Live web search & trust tagging
│   ├── calendar_tool.py         # Step 2b: Deterministic Hijri calendar lookup
│   ├── verifier.py              # Step 3: Evidence-grounded verdict generation
│   └── translator.py            # Step 4: Multilingual output translation
│
├── frontend/
│   ├── index.html               # Main UI view
│   ├── style.css                # Interface styles
│   └── script.js                # Frontend API interactions & dynamics
│
├── data/
│   ├── tehqeeq_data_clean.csv   # Cleaned 80-example labeled evaluation set
│   └── Tehqeeq Data_clean.xlsx  # Raw/Excel source dataset
│
├── tests/                       # Evaluation, sanity checks & results
│   ├── batch_test.py            # Full-dataset evaluation runner
│   ├── sanity_check.py          # Quick sanity test script
│   ├── test_main.py             # FastAPI unit/integration tests
│   ├── restart.py               # Environment reset or re-run utility
│   ├── politics_retest.json     # Targeted domain test results
│   └── test_results_full.json   # Full benchmark evaluation output
│
|── README.md 
|── main.py
|── .gitignore
├── NOTES.md                     # Development & debugging logs
├── requirements.txt             # Python project dependencies
└── .env.example                 # Template for API keys & environment variables
```
---

## Running It Locally

**1. Install dependencies**
```bash
pip install fastapi uvicorn groq tavily-python requests python-dotenv pandas openpyxl
```

**2. Set up environment variables** — create a `.env` file:
```
GROQ_API_KEY=your_groq_key
TAVILY_API_KEY=your_tavily_key
GROQ_MODEL_EXTRACT=llama-3.3-70b-versatile
GROQ_MODEL_VERIFY=llama-3.1-8b-instant
```

**3. Start the backend**
```bash
uvicorn main:app --reload
```

**4. Open the frontend** — open `frontend/index.html` directly in a browser, or serve it with any static file server.

**5. (Optional) Run the evaluation suite**
```bash
python batchtest.py
```

---

## What This Project Demonstrates

- Designing a **multi-stage, evidence-grounded LLM pipeline** (not a single prompt-and-response wrapper) with distinct extraction, retrieval, verdict, and translation stages.
- **Iterative, metrics-driven debugging**: building a labeled evaluation set, diagnosing category-specific accuracy regressions, and root-causing them (e.g. a code-level guardrail that was too aggressive and silently suppressed correct verdicts — see `NOTES.md`).
- Building **defense-in-depth safeguards** against known LLM failure modes: entity substitution, temporal hallucination (citing stale evidence for recent claims), and over-reliance on "uncertain" as an unhelpful safe default — each diagnosed from real failing test cases and fixed at the prompt and/or code level.
- **Full-stack delivery**: FastAPI backend, custom HTML/CSS/JS frontend, deployed as a working web app with no login/download friction.

---

## License

This is a personal/academic project, built as a portfolio piece. Not licensed for production or commercial misinformation-detection use.
