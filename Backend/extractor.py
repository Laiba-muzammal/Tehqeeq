"""
extractor.py

Step 1 of the Tehqeeq pipeline: claim extraction.

Takes a raw user message (Roman Urdu, English, or a mix of both) and uses an
LLM to produce:
    - a clean English translation of the full message
    - the core factual claim (the specific, checkable assertion within it)

The core claim is what gets passed downstream to the search step, so its
quality directly determines how good the retrieved evidence is.
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

EXTRACTION_SYSTEM_PROMPT_TEMPLATE = """You are a claim extraction assistant. Today's date is {today}. You will receive a message written in Roman Urdu (Urdu written in English script), possibly mixed with English words.

Your task:
1. Translate the message to clear English.
2. Extract the core factual claim being made (the specific thing that could be true or false).
3. CRITICAL: if the message uses a relative time expression (e.g. "kal"/yesterday, "aaj"/today, "is hafte"/this week, "pichle mahine"/last month, "haliya"/recently), resolve it into an explicit date or month+year using today's date above, and include that explicit date in the core_claim. This is essential for search accuracy -- do not leave relative time words unresolved, since a search engine has no way to know what "kal" means without an anchor date.

Example: if today is July 19, 2026 and the message says "kal Islamabad mein baarish hui" (it rained in Islamabad yesterday), the core_claim should be something like "It rained in Islamabad on July 18, 2026" -- not just "It rained in Islamabad recently".

4. CRITICAL -- do not substitute entities: translate the exact subject, animal, person, place, or object named in the input. NEVER replace it with a different but "more familiar" or "more commonly discussed" entity, even if the resulting claim resembles a well-known myth or trivia pattern you recognize. This is a known failure mode: given an unusual claim (e.g. about a horse), you may be tempted to drift toward a more commonly-discussed version (e.g. about a cow, because "cows eating non-food items" is a more familiar topic). Do NOT do this. If the input says "ghoray" (horse), the translation and core_claim MUST say "horse" -- never "cow", "goat", or any other animal, no matter how much more common that other claim might be in your training data. Preserve the exact subject named, always.

Respond ONLY in valid JSON, no extra text, no markdown, in this exact format:
{{
  "english_translation": "...",
  "core_claim": "..."
}}
"""


class ClaimExtractor:
    """Wraps a Groq chat completion call for claim extraction and translation."""

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is missing from the environment (.env).")

        self.client = Groq(api_key=api_key)

        # Model is configurable via .env (GROQ_MODEL_EXTRACT) rather than
        # hardcoded, so extraction and verdict-generation models can be
        # swapped independently (e.g. to work around per-model rate limits)
        # without touching code.
        self.model = os.getenv("GROQ_MODEL_EXTRACT", "llama-3.3-70b-versatile")

    def _transliterate_to_urdu_script(self, roman_urdu_text: str) -> str:
        """
        Pivot step: convert Roman Urdu (Latin script) into proper Urdu
        script (Nasta'liq/Arabic script) first. The idea is that the model
        may parse Roman Urdu more reliably once it's in native script,
        since Roman Urdu spelling is unstandardized (e.g. "qeemat" vs
        "qeematon" vs "kimat") whereas Urdu script is not.

        Returns the Urdu-script text, or the original Roman Urdu text
        unchanged if this step fails (so a failure here doesn't break the
        rest of the pipeline).
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Convert the following Roman Urdu text (Urdu written in "
                            "Latin/English script) into proper Urdu script (Nasta'liq). "
                            "Return ONLY the converted Urdu script text, no explanation, "
                            "no extra commentary, no quotation marks."
                        ),
                    },
                    {"role": "user", "content": roman_urdu_text},
                ],
                temperature=0.1,
            )
            urdu_script = response.choices[0].message.content.strip()
            return urdu_script or roman_urdu_text
        except Exception as exc:  # noqa: BLE001
            logging.error("Transliteration to Urdu script failed, falling back to Roman Urdu: %s", exc)
            return roman_urdu_text

    def extract_claim(self, raw_text: str) -> dict:
        """
        Translate `raw_text` and extract its core factual claim.

        Returns a dict with keys:
            english_translation (str | None)
            core_claim           (str | None)
            is_error              (bool)
            error                 (str, only present on failure)

        On any failure (API error or malformed JSON response), is_error is
        set to True and the claim fields are None. Callers must check
        is_error before using the result, rather than assuming a falsy
        core_claim implies failure.
        """
        raw_output = None
        try:
            # Pivot: Roman Urdu -> Urdu script, before the main
            # translate+extract call. See _transliterate_to_urdu_script for
            # the rationale. If this step fails, urdu_script_text just
            # falls back to the original raw_text, so the pipeline still
            # works even if the pivot itself errors out.
            urdu_script_text = self._transliterate_to_urdu_script(raw_text)

            today = date.today().strftime("%B %d, %Y")
            system_prompt = EXTRACTION_SYSTEM_PROMPT_TEMPLATE.format(today=today)

            user_content = (
                f"Original Roman Urdu: {raw_text}\n"
                f"Urdu script version: {urdu_script_text}\n\n"
                f"Use both versions above (they should mean the same thing) to "
                f"produce the most accurate English translation and core claim."
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,  # low temperature -> consistent, low-creativity output
            )

            raw_output = response.choices[0].message.content.strip()
            # Some models wrap JSON output in markdown code fences; strip them.
            raw_output = raw_output.replace("```json", "").replace("```", "").strip()

            parsed = json.loads(raw_output)
            parsed["is_error"] = False
            return parsed

        except json.JSONDecodeError as exc:
            logger.error("Failed to parse extractor output as JSON: %s | raw=%r", exc, raw_output)
            return {
                "english_translation": None,
                "core_claim": None,
                "error": "parse_failed",
                "is_error": True,
            }
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any API failure lands here
            logger.error("Claim extraction failed: %s", exc)
            return {
                "english_translation": None,
                "core_claim": None,
                "error": str(exc),
                "is_error": True,
            }


if __name__ == "__main__":
    extractor = ClaimExtractor()
    sample = "Garam pani peene se cancer khatam ho jata hai, doctors ne bhi tasdeeq ki hai."
    print(json.dumps(extractor.extract_claim(sample), indent=2, ensure_ascii=False))