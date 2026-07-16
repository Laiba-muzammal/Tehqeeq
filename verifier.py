"""
verifier.py

Responsible for producing a final verdict on a claim, given a set of
search-derived evidence. The verdict is generated strictly from the
provided evidence -- the model is explicitly instructed not to rely on
outside/prior knowledge, to keep results auditable and evidence-grounded.

Verdict values ("true" | "false" | "uncertain") represent the model's
genuine assessment. System failures (API errors, malformed output) are
NEVER mapped to "uncertain" -- they are reported separately via `status`
so evaluation metrics are not distorted by infrastructure issues.
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

SYSTEM_PROMPT = """You are a fact-checking assistant. You will be given a CLAIM and EVIDENCE (search results from the web).

Your task: Based ONLY on the evidence provided, determine if the claim is true, false, or uncertain.

Rules:
- If evidence clearly supports the claim, verdict is "true"
- If evidence clearly contradicts the claim, verdict is "false"
- If evidence is insufficient, unclear, or missing, verdict is "uncertain"
- Never use outside knowledge beyond what's in the evidence
- Be conservative -- if unsure, say "uncertain"

Respond ONLY in valid JSON, no extra text, no markdown, in this exact format:
{
  "verdict": "true" | "false" | "uncertain",
  "confidence": "high" | "medium" | "low",
  "reasoning": "brief explanation in 1-2 sentences"
}
"""


class VerdictGenerator:
    """Generates an evidence-grounded verdict for a factual claim."""

    def __init__(self, api_key: Optional[str] = None, model: str = MODEL_NAME):
        resolved_key = api_key or os.getenv("GROQ_API_KEY")
        if not resolved_key:
            raise EnvironmentError(
                "GROQ_API_KEY not found. Set it in your .env file or pass it explicitly."
            )
        self.client = Groq(api_key=resolved_key)
        self.model = model

    def generate_verdict(self, claim: str, search_results: list) -> dict:
        """
        Args:
            claim: The core factual claim (in English).
            search_results: List of evidence dicts (title/url/content).

        Returns:
            {
                "status": "ok" | "error",
                "verdict": "true" | "false" | "uncertain" | None,
                "confidence": "high" | "medium" | "low" | None,
                "reasoning": str | None,
                "error_message": str | None,
            }
        """
        evidence_text = self._format_evidence(search_results)
        user_prompt = f"CLAIM: {claim}\n\nEVIDENCE:\n{evidence_text}"

        raw_output = None
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,  # very low: prioritize consistency over creativity
            )

            raw_output = response.choices[0].message.content.strip()
            raw_output = raw_output.replace("```json", "").replace("```", "").strip()

            parsed = json.loads(raw_output)
            return {
                "status": "ok",
                "verdict": parsed.get("verdict"),
                "confidence": parsed.get("confidence"),
                "reasoning": parsed.get("reasoning"),
                "error_message": None,
            }

        except json.JSONDecodeError as e:
            logger.error("Verdict JSON parse failure: %s | raw_output=%r", e, raw_output)
            return self._error_result(f"JSON parse failed: {e}")

        except Exception as e:
            logger.exception("Verdict generation request failed.")
            return self._error_result(str(e))

    @staticmethod
    def _format_evidence(search_results: list) -> str:
        if not search_results:
            return "No search results found."
        return "\n\n".join(
            f"Source: {r.get('title', '')} ({r.get('url', '')})\n{r.get('content', '')}"
            for r in search_results
        )

    @staticmethod
    def _error_result(message: str) -> dict:
        return {
            "status": "error",
            "verdict": None,
            "confidence": None,
            "reasoning": None,
            "error_message": message,
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    generator = VerdictGenerator()
    sample_claim = "Drinking hot water can cure cancer"
    sample_evidence = [
        {
            "title": "No evidence hot water cures cancer",
            "url": "https://who.int/example",
            "content": "There is no scientific evidence that drinking hot water cures or treats cancer.",
        }
    ]
    result = generator.generate_verdict(sample_claim, sample_evidence)
    print(json.dumps(result, indent=2, ensure_ascii=False))