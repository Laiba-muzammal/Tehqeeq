"""
pipeline.py

Orchestrates the full Tehqeeq verification flow:

    1. extractor.py  -> translate the raw message + extract the core claim
    2. searcher.py   -> retrieve live web evidence for that claim
    3. verifier.py   -> classify the claim as true / false / misleading /
                         uncertain, based only on the retrieved evidence

The output of `verify()` always includes a "verdict" key and an "is_error"
flag, even when an upstream step fails. This guarantee is what makes batch
evaluation (see batchtest.py) reliable -- callers never need to special-case
a missing "verdict" key.

For claims that reference the Islamic (Hijri) calendar -- Ramadan/Roza,
Eid, moon-sighting announcements, etc. -- a deterministic calendar lookup
(calendar_tool.py) is appended to the web-search evidence before the
verdict step. Web search alone often has no relevant coverage for these
claims at the moment they're checked (there's simply no news about a date
that isn't imminent), which previously caused correct-but-unhelpful
"uncertain" verdicts. The calendar tool provides an always-available,
authoritative reference point that doesn't depend on what's currently
being reported in the news.
"""

import json
import logging
from Backend.extractor import ClaimExtractor
from Backend.searcher import ClaimSearcher
from Backend.verifier import VerdictGenerator
from Backend.calendar_tool import is_calendar_related, build_calendar_evidence
from Backend.translator import OutputTranslator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TasdeeqPipeline:
    """End-to-end claim verification pipeline."""

    def __init__(self):
        """Instantiate the pipeline stages (extractor, searcher, verifier, translator)."""
        self.extractor = ClaimExtractor()
        self.searcher = ClaimSearcher()
        self.verifier = VerdictGenerator()
        self.translator = OutputTranslator()

    def verify(self, raw_text: str) -> dict:
        """
        Run the full verification pipeline on a raw user message.

        Returns a dict with keys:
            original_text        - the raw input as received
            english_translation  - full English translation (if extraction succeeded)
            core_claim            - the distilled, checkable claim (English)
            sources                - list of evidence dicts used for the verdict
            verdict                - "true" | "false" | "misleading" | "uncertain" | "error"
            confidence             - "high" | "medium" | "low" | None
            reasoning               - short explanation from the model, or the
                                       failure reason if is_error is True
            is_error                - True if any step failed and no genuine
                                       model verdict was produced
        """
        logger.info("Step 1: extracting claim...")
        extracted = self.extractor.extract_claim(raw_text)

        if extracted.get("is_error") or not extracted.get("core_claim"):
            logger.error("Claim extraction failed: %s", extracted)
            error_message = extracted.get("error", "Claim extraction failed")
            return {
                "original_text": raw_text,
                "english_translation": extracted.get("english_translation"),
                "core_claim": extracted.get("core_claim"),
                "sources": [],
                "verdict": "error",
                "confidence": None,
                "reasoning": {
                    "english": error_message,
                    "roman_urdu": error_message,
                    "urdu_script": error_message,
                },
                "is_error": True,
            }

        english_claim = extracted["core_claim"]

        logger.info("Step 2: searching for evidence on: %s", english_claim)
        search_results = self.searcher.search_claim(english_claim)

        # Supplement with a deterministic calendar reference for
        # Hijri-calendar-related claims -- see module docstring above.
        if is_calendar_related(raw_text) or is_calendar_related(english_claim):
            logger.info("Claim looks calendar-related; adding Hijri date reference.")
            calendar_evidence = build_calendar_evidence()
            if calendar_evidence:
                search_results.append(calendar_evidence)

        logger.info("Step 3: generating verdict...")
        verdict = self.verifier.generate_verdict(english_claim, search_results)

        reasoning_english = verdict.get("reasoning") or ""
        logger.info("Step 4: translating output for display...")
        translated = self.translator.translate(reasoning_english) if reasoning_english else {
            "roman_urdu": "", "urdu_script": "", "is_error": False
        }

        # Translate source titles too (single batch call), so the sources
        # list can also display in Roman Urdu / Urdu script, not just the
        # main reasoning text.
        if search_results:
            titles = [r.get("title", "") for r in search_results]
            translated_titles = self.translator.translate_titles(titles)
            for source, title_translation in zip(search_results, translated_titles):
                source["title_roman_urdu"] = title_translation.get("roman_urdu", source.get("title"))
                source["title_urdu_script"] = title_translation.get("urdu_script", source.get("title"))

        return {
            "original_text": raw_text,
            "english_translation": extracted.get("english_translation"),
            "core_claim": english_claim,
            "sources": search_results,
            "verdict": verdict.get("verdict"),
            "confidence": verdict.get("confidence"),
            "reasoning": {
                "english": reasoning_english,
                "roman_urdu": translated.get("roman_urdu"),
                "urdu_script": translated.get("urdu_script"),
            },
            "is_error": verdict.get("is_error", False),
        }


if __name__ == "__main__":
    pipeline = TasdeeqPipeline()
    sample = "Garam pani peene se cancer khatam ho jata hai, doctors ne bhi tasdeeq ki hai."
    result = pipeline.verify(sample)
    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))