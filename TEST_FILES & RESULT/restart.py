"""
selective_retest.py

Re-tests a specific subset of dataset rows through the pipeline, instead of
the full 80-row set. Useful after a targeted prompt/logic change (e.g. the
verifier.py trust-tagging update) to check whether it actually fixed the
rows it was meant to fix, without burning the full daily API quota on a
complete re-run.

Usage:
    python selective_retest.py
    (edit ROW_INDICES below to target a different set of rows)
"""

import json
import logging
import pandas as pd
from pipeline import TasdeeqPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

LABEL_MAPPING = {
    "false": "false",
    "true": "true",
    "misleading": "misleading",
    "unverified": "uncertain",
    "satire": "uncertain",
}


def normalize_label(label):
    if not label:
        return None
    return LABEL_MAPPING.get(str(label).strip().lower(), str(label).strip().lower())


# All 15 Politics-category row indices from the last full run.
ROW_INDICES = [8, 12, 13, 15, 16, 17, 34, 35, 38, 47, 48, 51, 68, 69, 78]


def run_selective_retest(dataset_path: str, indices: list[int], output_file: str = "politics_retest.json"):
    df = pd.read_excel(dataset_path)
    df.columns = df.columns.str.strip()

    pipeline = TasdeeqPipeline()
    results = []

    for i, idx in enumerate(indices, start=1):
        row = df.loc[idx]
        roman_claim = row.get("claim_roman_urdu")
        expected_raw = row.get("verdict")
        expected_normalized = normalize_label(expected_raw)

        logger.info("Testing row %s (%d/%d)", idx, i, len(indices))

        try:
            result = pipeline.verify(roman_claim)
        except Exception as exc:  # noqa: BLE001
            logger.error("Row %s raised an unexpected exception: %s", idx, exc)
            result = {"verdict": "error", "confidence": None, "reasoning": str(exc), "is_error": True}

        result["row_index"] = int(idx)
        result["expected_label_raw"] = expected_raw
        result["expected_label_normalized"] = expected_normalized
        results.append(result)

        is_correct = (
            not result.get("is_error")
            and result.get("expected_label_normalized") == str(result.get("verdict", "")).strip().lower()
        )
        mark = "CORRECT" if is_correct else "WRONG"
        print(f"\nRow {idx} [{mark}]:")
        print(f"  Claim:    {roman_claim}")
        print(f"  Expected: {expected_raw} -> {expected_normalized}")
        print(f"  Got:      {result.get('verdict')} (confidence: {result.get('confidence')})")
        print(f"  Reasoning: {result.get('reasoning')}")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    valid = [r for r in results if not r.get("is_error")]
    correct = sum(
        1 for r in valid
        if r.get("expected_label_normalized") == str(r.get("verdict", "")).strip().lower()
    )

    print(f"\n=== SELECTIVE RETEST SUMMARY ===")
    print(f"Rows tested : {len(results)}")
    print(f"Errored     : {len(results) - len(valid)}")
    print(f"Correct     : {correct}/{len(valid)} ({(correct/len(valid))*100:.1f}%)" if valid else "N/A")


if __name__ == "__main__":
    run_selective_retest(dataset_path="data/Tehqeeq Data_clean.xlsx", indices=ROW_INDICES)