"""
extractor.py

Responsible for taking a raw user claim (Roman Urdu, English, or mixed)
and using an LLM to produce:
  1. A clean English translation
  2. The core factual claim to be fact-checked

This module never raises on API/parsing failures during extraction calls;
it always returns a structured dict with an explicit `status` field so
callers can distinguish "genuine uncertainty" from "system failure".
"""

import os
import json
import logging
from typing import Optional

from dotenv import load_dotenv
from groq import Groq

logger = logging.getLogger(__name__)
load_dotenv()

MODEL_NAME = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are a claim extraction assistant. You will receive a message written in Roman Urdu (Urdu written in English script), possibly mixed with English words.

Your task:
1. Translate the message to clear English.
2. Extract the core factual claim being made (the specific thing that could be true or false).

Respond ONLY in valid JSON, no extra text, no markdown, in this exact format:
{
  "english_translation": "...",
  "core_claim": "..."
}
"""


class ClaimExtractor:
    """Extracts a clean, English-language factual claim from raw input text."""

    def __init__(self, api_key: Optional[str] = None, model: str = MODEL_NAME):
        resolved_key = api_key or os.getenv("GROQ_API_KEY")
        if not resolved_key:
            raise EnvironmentError(
                "GROQ_API_KEY not found. Set it in your .env file or pass it explicitly."
            )
        self.client = Groq(api_key=resolved_key)
        self.model = model

    def extract_claim(self, raw_text: str) -> dict:
        """
        Args:
            raw_text: The original user-submitted claim.

        Returns:
            {
                "status": "ok" | "error",
                "english_translation": str | None,
                "core_claim": str | None,
                "error_message": str | None,
            }
        """
        if not raw_text or not raw_text.strip():
            return self._error_result("Empty input text provided.")

        raw_output = None
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": raw_text},
                ],
                temperature=0.2,  # low temperature for consistent, factual output
            )

            raw_output = response.choices[0].message.content.strip()
            raw_output = raw_output.replace("```json", "").replace("```", "").strip()

            parsed = json.loads(raw_output)
            return {
                "status": "ok",
                "english_translation": parsed.get("english_translation"),
                "core_claim": parsed.get("core_claim"),
                "error_message": None,
            }

        except json.JSONDecodeError as e:
            logger.error("Claim extraction JSON parse failure: %s | raw_output=%r", e, raw_output)
            return self._error_result(f"JSON parse failed: {e}")

        except Exception as e:
            logger.exception("Claim extraction request failed.")
            return self._error_result(str(e))

    @staticmethod
    def _error_result(message: str) -> dict:
        return {
            "status": "error",
            "english_translation": None,
            "core_claim": None,
            "error_message": message,
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    extractor = ClaimExtractor()
    sample_claim = "Garam pani peene se cancer khatam ho jata hai, doctors ne bhi tasdeeq ki hai."
    result = extractor.extract_claim(sample_claim)
    print(json.dumps(result, indent=2, ensure_ascii=False))