"""
batchtest.py

Runs the full Tehqeeq pipeline over the labeled evaluation dataset and
reports accuracy, both overall and broken down by category.

Rows where the pipeline failed (API errors, rate limits, malformed output)
are identified via the `is_error` flag returned by pipeline.verify() and
are excluded from accuracy calculations -- they represent untested claims,
not incorrect predictions, so counting them as wrong would understate
the tool's real accuracy.
"""

import json
import logging
import pandas as pd
from pipeline import TasdeeqPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Maps the dataset's ground-truth verdict labels onto the pipeline's own
# verdict vocabulary ("true" | "false" | "misleading" | "uncertain").
# "misleading" now maps to itself (previously folded into "uncertain"
# before verifier.py supported it as a distinct category).
LABEL_MAPPING = {
    "false": "false",
    "true": "true",
    "misleading": "misleading",
    "unverified": "uncertain",
    "satire": "uncertain",
}


def normalize_label(label) -> str | None:
    """Normalize a raw dataset verdict label to the pipeline's vocabulary."""
    if not label:
        return None
    return LABEL_MAPPING.get(str(label).strip().lower(), str(label).strip().lower())


def run_batch_test(
    dataset_path: str,
    output_file: str = "test_results_full.json",
    limit: int | None = None,
) -> None:
    """
    Evaluate the pipeline against every row in `dataset_path`.

    Args:
        dataset_path: path to the labeled evaluation spreadsheet. Must
            contain columns: claim_roman_urdu, verdict, and optionally
            category.
        output_file: where raw per-row results are saved as JSON. Written
            after every row, so a crash partway through does not lose
            already-completed results.
        limit: if set, only test the first `limit` rows (useful for a
            quick smoke test before a full run).
    """
    df = pd.read_excel(dataset_path)
    df.columns = df.columns.str.strip()

    if limit:
        df = df.iloc[:limit]

    pipeline = TasdeeqPipeline()
    all_results = []
    total_rows = len(df)

    for i, (idx, row) in enumerate(df.iterrows(), start=1):
        roman_claim = row.get("claim_roman_urdu")
        expected_raw = row.get("verdict")
        expected_normalized = normalize_label(expected_raw)

        logger.info("Testing row %s (%d/%d)", idx, i, total_rows)

        try:
            result = pipeline.verify(roman_claim)
        except Exception as exc:  # noqa: BLE001 - safety net; verify() should already catch its own errors
            logger.error("Row %s raised an unexpected exception: %s", idx, exc)
            result = {
                "verdict": "error",
                "confidence": None,
                "reasoning": str(exc),
                "is_error": True,
            }

        result["row_index"] = int(idx)
        result["expected_label_raw"] = expected_raw
        result["expected_label_normalized"] = expected_normalized
        all_results.append(result)

        status = "ERROR" if result.get("is_error") else "ok"
        print(f"\nRow {idx} ({i}/{total_rows}) [{status}]:")
        print(f"  Claim:    {roman_claim}")
        print(f"  Expected: {expected_raw} -> {expected_normalized}")
        print(f"  Got:      {result.get('verdict')} (confidence: {result.get('confidence')})")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)

    logger.info("All results saved to %s", output_file)
    _print_summary(all_results, df)


def _print_summary(all_results: list[dict], df: pd.DataFrame) -> None:
    """Print overall and per-category accuracy, excluding errored rows."""
    valid_results = [r for r in all_results if not r.get("is_error")]
    errored_results = [r for r in all_results if r.get("is_error")]

    correct = sum(
        1
        for r in valid_results
        if r.get("expected_label_normalized") == str(r.get("verdict", "")).strip().lower()
    )
    total = len(valid_results)

    print("\n=== FINAL RESULTS ===")
    print(f"Total rows tested : {len(all_results)}")
    print(f"Errored/excluded  : {len(errored_results)}")
    print(f"Valid comparisons : {total}")
    print(f"Correct           : {correct}")
    print(f"ACCURACY          : {(correct / total) * 100:.1f}%" if total else "ACCURACY: N/A")

    if errored_results:
        print("\n=== ERRORED ROWS (excluded above, re-test these separately) ===")
        for r in errored_results:
            print(f"  Row {r.get('row_index')}: {r.get('reasoning')}")

    if "category" not in df.columns:
        return

    print("\n=== BREAKDOWN BY CATEGORY (excluding errored rows) ===")
    results_df = pd.DataFrame(valid_results)
    if results_df.empty:
        print("  (no valid results to break down)")
        return

    merged = results_df.merge(
        df[["category"]].reset_index().rename(columns={"index": "row_index"}),
        on="row_index",
        how="left",
    )
    for category, group in merged.groupby("category"):
        cat_correct = sum(
            1
            for _, r in group.iterrows()
            if r.get("expected_label_normalized") == str(r.get("verdict", "")).strip().lower()
        )
        cat_total = len(group)
        print(f"  {category}: {cat_correct}/{cat_total} ({(cat_correct / cat_total) * 100:.1f}%)")


if __name__ == "__main__":
    run_batch_test(dataset_path="data/Tehqeeq Data_clean.xlsx", limit=None)