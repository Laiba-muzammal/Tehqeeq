# Development Notes — Tehqeeq

This file documents the debugging and design-iteration process behind Tehqeeq's verification pipeline. It exists so the reasoning behind non-obvious decisions is traceable — both for my own future reference and for anyone reviewing the code who wants to understand *why* it looks the way it does, not just what it does.

---

## Timeline Summary

| Stage | Focus | Outcome |
|---|---|---|
| Dataset build | Collected + manually labeled 80 claims across 6 categories from Soch Fact Check, Geo Fact Check, and other verified sources | Balanced verdict distribution (~41% False, ~32% True, ~15% Uncertain, ~11% Misleading initially) |
| Core pipeline | Built extractor → searcher → verifier → pipeline architecture | First full-dataset run: 62.5% accuracy on an 8-sample smoke test |
| First full 80-row run | — | 55.0% accuracy, but ~9 rows failed due to a Groq daily rate limit, artificially deflating the number (true accuracy on completed rows: ~62%) |

---

## Key Bugs Found and Fixed

### 1. Error states silently miscounted as wrong answers
**Symptom:** batch test accuracy looked worse than it actually was.

**Root cause:** when the API failed (rate limits, malformed JSON), the pipeline returned `verdict: None` instead of a distinguishable error state. The batch script's error filter checked for `verdict == "error"`, which never matched, so these rows were counted as incorrect predictions rather than excluded as untested.

**Fix:** added an explicit `is_error` flag propagated through every layer of the pipeline. Batch evaluation now excludes `is_error: True` rows from accuracy calculations instead of silently miscounting them.

### 2. "Misleading" wasn't a real verdict category
**Symptom:** Health category accuracy was 25% — the weakest of all categories.

**Root cause:** the verifier could only output true/false/uncertain. Claims that were genuinely "misleading" (a real safety risk described with exaggerated urgency, e.g. the electric geyser claim) were being force-mapped to "uncertain" at the evaluation layer, which the model had no way to actually produce.

**Fix:** added "misleading" as a first-class verdict category with explicit examples in the prompt. Health accuracy went from 25% → 66.7% in the next run.

### 3. Regression from an over-broad trust guardrail
**Symptom:** after fixing a Politics-specific issue (confidently wrong verdicts on weak evidence), a full-dataset run showed Health accuracy crash from 66.7% → 25.0%, Tech from 66.7% → 26.7%.

**Root cause:** a code-level guardrail was added that force-downgraded any confident true/false verdict to "uncertain" if no evidence source matched a curated `TRUSTED_DOMAINS` list. That list was still mostly Pakistani-politics-focused (gov.pk, geo.tv, dawn.com) and had no health/science/tech authorities on it — so *correct* verdicts in those categories were being overridden simply because their legitimate sources weren't recognized.

**Fix:** broadened `TRUSTED_DOMAINS` to cover all claim categories (health authorities, global news wires, tech companies, entertainment bodies), and softened the guardrail to only override low-confidence verdicts, not medium/high-confidence ones. Net result: 45.0% → 61.3% overall, with no category left crashed.

**Lesson:** a fix validated only on a subset of the data (15 Politics rows) does not generalize — always re-run the full evaluation set after a targeted fix, not just the rows the fix was designed for.

### 4. Temporal hallucination — stale evidence cited for recent claims
**Symptom:** a claim like "Pakistan lost a hockey match yesterday" returned evidence from a 2024 article, confidently confirmed as current.

**Root cause:** search results carried no publish-date information, so the model had no way to check evidence freshness — it could only guess from surrounding text, which it did unreliably. Additionally, the query-generation step didn't resolve relative time words ("kal"/yesterday) into an explicit date, so the search query itself was date-agnostic.

**Fix:**
- `extractor.py` now receives the actual current date and is explicitly instructed to resolve relative time expressions into explicit dates before generating the search query.
- `searcher.py` now captures each result's `published_date` (when Tavily provides one) and constrains search to a recent time window for claims using recency language.
- `verifier.py` is shown each evidence item's publish date and instructed not to use outdated evidence to confirm/deny a claim about a recent event.

### 5. Entity substitution hallucination
**Symptom:** input "ghoray rubber khate hain" (horses eat rubber) was translated and verified as being about **cows**, not horses.

**Root cause:** a known LLM failure mode — given an unusual claim, the model drifts toward a more commonly-discussed version it recognizes from training data (cows eating non-food items is a much more common trivia topic than horses and rubber).

**Fix:** added an explicit anti-substitution rule to the extraction prompt, with a concrete example naming this exact failure pattern, instructing the model to preserve the exact subject named in the input regardless of how much more "familiar" a different subject might seem.

### 6. Relevance was being treated as confirmation
**Symptom:** claims about unusual/absurd topics were sometimes marked "true" when the retrieved evidence was only topically related, not actually supportive.

**Root cause:** the model wasn't distinguishing "evidence mentions the same general topic" from "evidence confirms the specific claim."

**Fix:** added an explicit rule with a worked example (the "horses eat rubber" case) clarifying that topical relevance is not confirmation.

### 7. Over-reliance on "uncertain" as a safe default
**Symptom:** claims that clearly fit the "misleading" pattern (e.g. "the whole city flooded" when evidence showed only localized flooding) were being marked "uncertain" instead.

**Root cause:** as more caveats and edge-case rules accumulated in the verifier prompt across iterations, the smaller model (`llama-3.1-8b-instant`) appeared to default to "uncertain" as a way to avoid committing to a specific verdict, even when it could clearly articulate the exaggeration in its own reasoning text.

**Fix:** added an explicit instruction near the top of the prompt: "uncertain" is a last resort, not a safe default — if the model can identify *how* a claim relates to the evidence (including "it's exaggerated"), that is sufficient information to commit to true/false/misleading.

### 8. Mixed-script translation output
**Symptom:** selecting "Roman Urdu" in the UI sometimes displayed Urdu-script (Nasta'liq) text instead of Latin-script Roman Urdu.

**Root cause:** the translation model didn't reliably keep the two output fields (`roman_urdu`, `urdu_script`) in their correct script, despite prompt instructions.

**Fix:** added code-level validation — the `roman_urdu` field is checked against the Arabic Unicode range after every translation call; if Arabic-script characters are detected, that field falls back to the English text rather than displaying mislabeled content.

---

## Design Decisions Worth Noting

- **No calendar-dependent claim guessing without a tool.** Claims like "tomorrow is the first day of Ramadan" were initially returning "uncertain" correctly (no relevant news exists for a future moon-sighting announcement) — this was *not* treated as a bug to patch away, since guessing would reintroduce hallucination risk. Instead, a dedicated deterministic Hijri-calendar API (`calendar_tool.py`) was added as a supplementary evidence source specifically for this claim category, rather than asking the LLM to reason about dates from its own training knowledge.
- **Source article content is not translated, only titles.** Full snippet translation would add cost and latency with limited benefit, since the linked source remains in its original language regardless — translating the title is enough for a user to judge relevance before clicking through.
- **`is_error` is a first-class field throughout the pipeline**, not inferred from a magic string or a `None` check, specifically because an earlier version relied on `verdict == "error"` string matching that silently failed (see bug #1).

---

## Honest Self-Assessment

The overall accuracy (~61%) is respectable for a research prototype covering an unstandardized, non-English-first script, but it is not production-grade. The largest remaining source of error is **search evidence availability**, not the reasoning layer — many "uncertain" or incorrect verdicts trace back to Tavily simply not surfacing a directly relevant, dated, trustworthy source for a given claim, rather than the verifier reasoning poorly given good evidence.

Future work that would meaningfully move the accuracy number: expanding `TRUSTED_DOMAINS` further, adding a secondary trusted-domain-only search pass when the first pass returns no trusted sources, and potentially upgrading the verifier model from `llama-3.1-8b-instant` to `llama-3.3-70b-versatile` for claims requiring more careful multi-rule reasoning, at the cost of tighter rate limits.
