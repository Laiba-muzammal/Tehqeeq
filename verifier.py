"""
verifier.py

Step 3 of the Tehqeeq pipeline: verdict generation.

Takes a claim plus the evidence retrieved by searcher.py and asks an LLM to
decide a verdict based ONLY on that evidence.

Verdict categories:
    "true"        - evidence clearly supports the claim
    "false"       - evidence clearly contradicts the claim
    "misleading"  - claim is partially true but SUBSTANTIALLY exaggerated,
                    missing context, attaches a false narrative to a real
                    event/image, or falsely attributes confirmation to an
                    authority that didn't actually confirm it
    "uncertain"   - evidence is insufficient, unclear, or absent

Revision history:

  v1-v3: see git history / earlier versions. Summary: "misleading" was
      added as a first-class category (fixed Health-domain accuracy), then
      tightened to avoid flagging minor numeric variance as misleading.

  v4: added [TRUSTED SOURCE] / [UNVERIFIED SOURCE] tagging on evidence and
      instructed the model to avoid confident true/false verdicts based
      only on unverified sources.

  v5: added `_enforce_trust_guardrail`, which force-downgraded ANY
      confident true/false verdict to "uncertain" whenever no evidence
      source matched TRUSTED_DOMAINS (see searcher.py). Tested only against
      the 15 Politics rows, this looked like an improvement (33.3% ->
      53.3%+ accuracy on that subset).

      Also generalized the "minor variance is still true/false" rule
      beyond "misleading", and added functionally-equivalent-terms
      guidance ("blocked" == "banned") plus two new "misleading" examples.

  v6 (current): a full 80-row run after v5 revealed the guardrail from v5
      was too blunt when applied dataset-wide: Health accuracy dropped from
      66.7% to 25.0%, Tech from 66.7% to 26.7%, and Natural Disaster from
      50.0% to 16.7% (overall accuracy fell from 58.8% to 45.0%), even
      though Politics did improve to 60.0%. Root cause: TRUSTED_DOMAINS was
      still mostly Pakistan-politics-centric (gov.pk, geo.tv, dawn.com),
      so well-evidenced, correct verdicts in Health/Tech/Disaster claims
      were being force-downgraded simply because their (legitimate) sources
      weren't on that narrow list -- e.g. a correct "true" verdict on the
      apricot-kernel-cyanide claim, backed by solid evidence, was flipped
      to "uncertain" purely because its source domain wasn't recognized.

      Two changes address this:
        1. TRUSTED_DOMAINS (searcher.py) is now broadened across all
           categories -- health/science authorities, global news wires,
           tech companies, entertainment/awards bodies -- not just
           Pakistani politics and fact-checking sites.
        2. The guardrail itself is softened: it now only force-downgrades
           a confident true/false verdict when the model's own stated
           confidence is "medium" or "low". A "high" confidence verdict is
           left as-is, on the assumption that the model rarely claims high
           confidence without a real basis in the evidence text, even if
           that source didn't happen to match our (necessarily incomplete)
           trusted-domain list. This keeps the original goal (catching
           weakly-supported confident answers) while no longer overriding
           answers the model is genuinely sure about.

Error handling: if the API call itself fails (rate limit, network error,
malformed JSON), this returns verdict="error" with is_error=True, distinct
from a genuine "uncertain" model opinion.
"""

import os
import json
import logging
from datetime import date
from dotenv import load_dotenv
from groq import Groq

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

ALLOWED_VERDICTS = ("true", "false", "misleading", "uncertain")

# Verdicts that require at least one trusted source to stand as given;
# otherwise they are downgraded to "uncertain" by _enforce_trust_guardrail.
# "medium"/"high" confidence on true/false without trusted backing is the
# most dangerous failure mode for a fact-checker (a confidently wrong
# answer), so this is enforced in code rather than relying solely on the
# model following its instructions.
CONFIDENT_VERDICTS_REQUIRING_TRUST = {"true", "false"}

VERDICT_SYSTEM_PROMPT = """You are a fact-checking assistant. You will be given a CLAIM and EVIDENCE (search results from the web). Each evidence item is tagged [TRUSTED SOURCE] (a known fact-checking outlet, government domain, or major news source) or [UNVERIFIED SOURCE] (social media, forums, or unrecognized sites).

IMPORTANT: "uncertain" is a LAST RESORT, not a safe default. Only use it when you genuinely cannot determine ANY of true/false/misleading from the evidence -- for example, when the evidence simply doesn\'t address the claim\'s topic at all. If you CAN identify how the claim relates to the evidence -- even if that relationship is "the claim exaggerates a real event" or "the claim uses absolute/urgent language that the evidence doesn\'t support" -- that is enough information to choose "misleading", "true", or "false". Do not retreat to "uncertain" just to avoid committing to a specific verdict when you can already explain what is wrong (or right) with the claim.

Your task: based ONLY on the evidence provided, classify the claim into exactly one of these four categories:

- "true": the evidence supports the claim's core assertion. Minor
  differences in exact figures, wording, or timeframes do NOT disqualify a
  claim from being "true" as long as the substance is confirmed -- for
  example, a claim that prices are reviewed "every 15 days" should still be
  "true" if evidence says they are reviewed "weekly", since both describe
  the same underlying practice. Similarly, treat functionally equivalent
  terms as the same fact (e.g. a website being "blocked" and a website
  being "banned" describe the same real-world outcome in a censorship
  context). A "true" verdict should ideally be backed by at least one
  [TRUSTED SOURCE].

- "false": the evidence clearly contradicts the claim's core assertion (not
  just a minor figure or wording difference -- see above). A confident
  "false" should also be backed by at least one [TRUSTED SOURCE] where
  possible.

- "misleading": the claim is partially true but SUBSTANTIALLY exaggerated,
  stripped of context that changes its meaning, or attaches a false or
  exaggerated narrative to something real. This includes:
    (a) a genuine photo or event presented with a fabricated explanation of
        what it shows or why it happened,
    (b) a claim that falsely attributes confirmation to a specific
        authority or organization that did not actually confirm it (e.g.
        "Wikipedia and BBC confirmed X" when the evidence shows neither
        source made that confirmation), or
    (c) a real, verifiable event (e.g. a person's real hospitalization,
        real photo) wrapped in a surrounding narrative or implied cause
        that the evidence does not support.
  Do NOT use "misleading" for minor numeric or timeframe discrepancies
  describing the same real event -- that is still "true" (see above).

- "uncertain": the evidence is insufficient, unclear, absent, or consists
  only of [UNVERIFIED SOURCE] results for a claim that would need
  authoritative confirmation.

Rules:
- Never use knowledge beyond what is in the provided evidence.
- Weigh [TRUSTED SOURCE] evidence more heavily than [UNVERIFIED SOURCE]
  evidence. Do not give a high-confidence verdict based only on unverified
  sources -- if that is all you have, the verdict should be "uncertain".
- Don't default to "uncertain" just because evidence isn't perfectly
  comprehensive -- if a trusted source clearly settles the claim, use it.

Respond ONLY in valid JSON, no extra text, no markdown, in this exact format:
{
  "verdict": "true" | "false" | "misleading" | "uncertain",
  "confidence": "high" | "medium" | "low",
  "reasoning": "brief explanation in 1-2 sentences"
}
"""


def _format_evidence(search_results: list[dict]) -> str:
    """
    Render search results as a labeled evidence block for the prompt.
    Includes each result\'s published date when available (see searcher.py
    v5), so the model can actually check evidence freshness instead of
    guessing from surrounding text.
    """
    if not search_results:
        return "No search results found."

    lines = []
    for r in search_results:
        tag = "[TRUSTED SOURCE]" if r.get("is_trusted") else "[UNVERIFIED SOURCE]"
        published = r.get("published_date")
        date_note = f" | Published: {published}" if published else " | Published date: unknown"
        lines.append(f"{tag}{date_note} Source: {r['title']} ({r['url']})\n{r['content']}")
    return "\n\n".join(lines)


def _enforce_trust_guardrail(parsed: dict, search_results: list[dict]) -> dict:
    """
    Defense-in-depth check, softened after the v6 regression (see revision
    history above). Only force-downgrades a confident true/false verdict to
    "uncertain" when BOTH:
      - the verdict is "true" or "false", AND
      - the model's own stated confidence is "medium" or "low" (NOT "high")
      - AND no evidence source matched TRUSTED_DOMAINS

    A "high" confidence true/false verdict is left untouched even without a
    recognized trusted source -- forcing every untrusted-source verdict to
    "uncertain" regardless of the model's own confidence proved too blunt
    dataset-wide (see v6 note). This keeps the guardrail useful for the
    original problem case (a middling-confidence verdict resting on weak,
    unverified evidence) without overriding answers the model is genuinely
    sure about.
    """
    verdict = parsed.get("verdict")
    confidence = parsed.get("confidence")

    if verdict not in CONFIDENT_VERDICTS_REQUIRING_TRUST:
        return parsed
    if confidence == "high":
        return parsed

    has_trusted_source = any(r.get("is_trusted") for r in search_results)
    if has_trusted_source:
        return parsed

    original_reasoning = parsed.get("reasoning", "")
    return {
        "verdict": "uncertain",
        "confidence": "low",
        "reasoning": (
            f"Downgraded from '{verdict}' ({confidence} confidence) to "
            f"'uncertain': no trusted source was available to support a "
            f"non-high-confidence verdict. Original model reasoning: {original_reasoning}"
        ),
        "is_error": False,
    }


class VerdictGenerator:
    """Wraps a Groq chat completion call for evidence-based verdict generation."""

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is missing from the environment (.env).")
        self.client = Groq(api_key=api_key)
        self.model = os.getenv("GROQ_MODEL_VERIFY", "llama-3.1-8b-instant")

    def generate_verdict(self, claim: str, search_results: list[dict]) -> dict:
        """
        Generate a verdict for `claim` using `search_results` as evidence.

        Returns a dict with keys: verdict, confidence, reasoning, is_error.
        A confident true/false verdict without trusted-source backing is
        automatically downgraded to "uncertain" -- see
        _enforce_trust_guardrail.
        """
        evidence_text = _format_evidence(search_results)
        today = date.today().strftime("%B %d, %Y")
        user_prompt = (
            f"TODAY\'S DATE: {today}\n\n"
            f"CLAIM: {claim}\n\nEVIDENCE:\n{evidence_text}"
        )

        raw_output = None
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": VERDICT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
            )

            raw_output = response.choices[0].message.content.strip()
            raw_output = raw_output.replace("```json", "").replace("```", "").strip()

            parsed = json.loads(raw_output)

            if parsed.get("verdict") not in ALLOWED_VERDICTS:
                logger.error("Model returned an unexpected verdict value: %r", parsed.get("verdict"))
                return {
                    "verdict": "error",
                    "confidence": None,
                    "reasoning": f"Model returned unexpected verdict: {parsed.get('verdict')!r}",
                    "is_error": True,
                }

            parsed["is_error"] = False
            return _enforce_trust_guardrail(parsed, search_results)

        except json.JSONDecodeError as exc:
            logger.error("Failed to parse verifier output as JSON: %s | raw=%r", exc, raw_output)
            return {
                "verdict": "error",
                "confidence": None,
                "reasoning": "Parsing error occurred",
                "is_error": True,
            }
        except Exception as exc:  # noqa: BLE001
            logger.error("Verdict generation failed: %s", exc)
            return {
                "verdict": "error",
                "confidence": None,
                "reasoning": str(exc),
                "is_error": True,
            }


if __name__ == "__main__":
    generator = VerdictGenerator()
    sample_claim = "Drinking hot water can cure cancer"
    sample_evidence = [
        {
            "title": "No evidence hot water cures cancer",
            "url": "https://who.int/example",
            "content": "There is no scientific evidence that drinking hot water cures or treats cancer.",
            "is_trusted": True,
        }
    ]
    print(json.dumps(generator.generate_verdict(sample_claim, sample_evidence), indent=2, ensure_ascii=False))