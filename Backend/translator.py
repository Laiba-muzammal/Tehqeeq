"""
translator.py

Translates the final verdict + reasoning into Roman Urdu and Urdu script,
so the frontend can offer a three-way output toggle (English / Roman Urdu
/ Urdu) without re-running the full verification pipeline per language.

This is a single extra Groq call made AFTER the verdict is already
generated -- it translates the finished, verified text, it does not
re-verify anything. No fine-tuning or training involved (see extractor.py
for the entity-preservation lesson learned there -- the same "don't
substitute the subject" caution applies here).
"""

import os
import re
import json
import logging
from dotenv import load_dotenv
from groq import Groq

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

# Unicode range covering Arabic script (used for Urdu). If this shows up
# in a field that's supposed to be Roman (Latin-script) Urdu, the model
# didn\'t follow instructions and we treat that field as invalid.
_ARABIC_SCRIPT_PATTERN = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")


def _contains_arabic_script(text: str) -> bool:
    """Return True if `text` contains any Arabic-script characters (used for Urdu)."""
    return bool(_ARABIC_SCRIPT_PATTERN.search(text or ""))

TRANSLATION_SYSTEM_PROMPT = """You are a translator. You will be given an English fact-check verdict and its reasoning. Translate it into two additional formats:

1. "roman_urdu": natural, conversational Roman Urdu (Urdu written in Latin script), the way an average Pakistani WhatsApp user would write it -- not overly formal or literal.
2. "urdu_script": the same content in proper Urdu script (Nasta'liq/Arabic script), grammatically correct standard Urdu.

Do NOT change the meaning, add information, or remove information. Do NOT substitute any named entity, number, date, or fact -- translate faithfully.

Respond ONLY in valid JSON, no extra text, no markdown, in this exact format:
{
  "roman_urdu": "...",
  "urdu_script": "..."
}
"""


class OutputTranslator:
    """Translates a finished English verdict/reasoning into Roman Urdu and Urdu script."""

    def __init__(self):
        """Create a Groq client and select the translator model from environment."""
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is missing from the environment (.env).")
        self.client = Groq(api_key=api_key)
        self.model = os.getenv("GROQ_MODEL_EXTRACT", "llama-3.3-70b-versatile")

    def translate(self, english_text: str) -> dict:
        """
        Returns a dict: {"roman_urdu": ..., "urdu_script": ..., "is_error": bool}
        On failure, roman_urdu/urdu_script fall back to the original English
        text (so the UI always has something to show) and is_error is True.
        """
        raw_output = None
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
                    {"role": "user", "content": english_text},
                ],
                temperature=0.3,
            )
            raw_output = response.choices[0].message.content.strip()
            raw_output = raw_output.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(raw_output)

            # FIX: the model sometimes fills "roman_urdu" with Urdu script
            # text instead of Latin script, despite the prompt instruction.
            # Detect this and fall back to the English text for that field
            # rather than silently showing mislabeled Urdu-script content
            # under the "Roman Urdu" toggle.
            if _contains_arabic_script(parsed.get("roman_urdu", "")):
                logger.error(
                    "Translator returned Arabic-script text in the roman_urdu "
                    "field; falling back to English for that field. raw=%r",
                    parsed.get("roman_urdu"),
                )
                parsed["roman_urdu"] = english_text

            parsed["is_error"] = False
            return parsed
        except Exception as exc:  # noqa: BLE001
            logger.error("Output translation failed: %s | raw=%r", exc, raw_output)
            return {
                "roman_urdu": english_text,
                "urdu_script": english_text,
                "is_error": True,
            }

    def translate_titles(self, titles: list[str]) -> list[dict]:
        """
        Batch-translates a list of source titles into Roman Urdu and Urdu
        script in a SINGLE API call (rather than one call per title), to
        keep the extra cost/latency of translating evidence sources low.

        Returns a list the same length as `titles`, in the same order,
        each item a dict: {"roman_urdu": ..., "urdu_script": ...}.
        On failure, every item falls back to the original English title.
        """
        if not titles:
            return []

        system_prompt = """You are a translator. You will be given a JSON array of English article titles (search result titles, not full articles).

Translate EACH title into:
1. "roman_urdu": natural Roman Urdu (Latin script).
2. "urdu_script": proper Urdu script (Nasta'liq).

Do not change meaning, add, or remove information from any title. Preserve the exact order of the input array.

Respond ONLY in valid JSON, no extra text, no markdown, in this exact format:
{
  "titles": [
    {"roman_urdu": "...", "urdu_script": "..."},
    {"roman_urdu": "...", "urdu_script": "..."}
  ]
}
"""
        raw_output = None
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(titles, ensure_ascii=False)},
                ],
                temperature=0.3,
            )
            raw_output = response.choices[0].message.content.strip()
            raw_output = raw_output.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(raw_output)
            translated_titles = parsed.get("titles", [])

            # Defensive check: if the model returned a different number of
            # items than we sent, fall back entirely rather than risk
            # misaligned translations attached to the wrong source.
            if len(translated_titles) != len(titles):
                raise ValueError(
                    f"Expected {len(titles)} translated titles, got {len(translated_titles)}"
                )

            # Same Arabic-script-in-roman_urdu check as translate() above,
            # applied per-title.
            for i, item in enumerate(translated_titles):
                if _contains_arabic_script(item.get("roman_urdu", "")):
                    logger.error(
                        "Title translation returned Arabic script in roman_urdu "
                        "for title %r; falling back to original.", titles[i]
                    )
                    item["roman_urdu"] = titles[i]

            return translated_titles

        except Exception as exc:  # noqa: BLE001
            logger.error("Title batch translation failed: %s | raw=%r", exc, raw_output)
            return [{"roman_urdu": t, "urdu_script": t} for t in titles]


if __name__ == "__main__":
    translator = OutputTranslator()
    sample = "This claim is false. Multiple trusted sources confirm no such event took place."
    print(json.dumps(translator.translate(sample), indent=2, ensure_ascii=False))