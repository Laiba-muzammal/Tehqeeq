"""
pipeline.py

Orchestrates the full claim-verification flow:

    raw claim --> ClaimExtractor --> ClaimSearcher --> VerdictGenerator

The pipeline is designed to fail gracefully at each stage: if extraction
or search fails, verification stops early and returns a structured error
result rather than raising -- so batch jobs never crash on a single bad row.
"""

import json
import logging

from extractor import ClaimExtractor
from searcher import ClaimSearcher
from verifier import VerdictGenerator

logger = logging.getLogger(__name__)


class TasdeeqPipeline:
    """End-to-end pipeline: raw claim -> extraction -> search -> verdict."""

    def __init__(self):
        self.extractor = ClaimExtractor()
        self.searcher = ClaimSearcher()
        self.verifier = VerdictGenerator()

    def verify(self, raw_text: str) -> dict:
        """
        Args:
            raw_text: The original claim as submitted by the user
                      (Roman Urdu, English, or mixed).

        Returns:
            A dict with `status` set to "ok" if a verdict was produced,
            or "error" (with `error_stage` and `error_message`) if the
            pipeline could not complete.
        """
        # --- Stage 1: Claim extraction ---
        extraction = self.extractor.extract_claim(raw_text)
        if extraction["status"] != "ok" or not extraction.get("core_claim"):
            return self._pipeline_error(
                stage="extraction",
                message=extraction.get("error_message") or "No core claim extracted.",
                raw_text=raw_text,
            )

        english_claim = extraction["core_claim"]

        # --- Stage 2: Evidence search ---
        search_outcome = self.searcher.search_claim(english_claim)
        if search_outcome["status"] != "ok":
            return self._pipeline_error(
                stage="search",
                message=search_outcome.get("error_message") or "Search failed.",
                raw_text=raw_text,
            )

        evidence = search_outcome["results"]

        # --- Stage 3: Verdict generation ---
        verdict_outcome = self.verifier.generate_verdict(english_claim, evidence)
        if verdict_outcome["status"] != "ok":
            return self._pipeline_error(
                stage="verdict_generation",
                message=verdict_outcome.get("error_message") or "Verdict generation failed.",
                raw_text=raw_text,
            )

        return {
            "status": "ok",
            "original_text": raw_text,
            "english_translation": extraction.get("english_translation"),
            "core_claim": english_claim,
            "sources": evidence,
            "verdict": verdict_outcome["verdict"],
            "confidence": verdict_outcome["confidence"],
            "reasoning": verdict_outcome["reasoning"],
        }

    @staticmethod
    def _pipeline_error(stage: str, message: str, raw_text: str) -> dict:
        logger.error("Pipeline failed at stage=%s: %s", stage, message)
        return {
            "status": "error",
            "error_stage": stage,
            "error_message": message,
            "original_text": raw_text,
            "verdict": None,
            "confidence": None,
            "reasoning": None,
            "sources": [],
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    pipeline = TasdeeqPipeline()
    sample_message = "Garam pani peene se cancer khatam ho jata hai, doctors ne bhi tasdeeq ki hai."
    result = pipeline.verify(sample_message)

    print("\n=== FINAL RESULT ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))