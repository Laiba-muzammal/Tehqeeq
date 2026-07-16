"""
batch_test.py

Runs the TasdeeqPipeline against every row (or a limited subset) of the
evaluation dataset and reports accuracy.

Accuracy is computed ONLY over rows where the pipeline completed
successfully (status == "ok"). Rows that failed due to system/API errors
are reported separately as `errored_rows` and excluded from accuracy --
so a network blip cannot be misread as the model being "uncertain",
and cannot silently inflate or deflate the reported accuracy.
"""

import json
import logging

import pandas as pd

from pipeline import TasdeeqPipeline

logger = logging.getLogger(__name__)

# Maps raw dataset verdict labels to the pipeline's output vocabulary.
LABEL_MAPPING = {
    "false": "false",
    "true": "true",
    "misleading": "uncertain",
    "unverified": "uncertain",
    "satire": "uncertain",
    "uncertain": "uncertain",
}


def normalize_label(label) -> str | None:
    """Maps a raw dataset label to the pipeline's verdict vocabulary."""
    if label is None or (isinstance(label, float) and pd.isna(label)):
        return None
    return LABEL_MAPPING.get(str(label).strip().lower(), str(label).strip().lower())


def run_batch_test(
    dataset_path: str,
    output_file: str = "test_results_full.json",
    limit: int | None = None,
) -> None:
    """
    Args:
        dataset_path: Path to the .xlsx evaluation dataset. Must contain
            columns `claim_roman_urdu`, `verdict`, and optionally `category`.
        output_file: Where to write the full JSON results (saved after
            every row, so a crash mid-run doesn't lose completed work).
        limit: If set, only test the first N rows (useful for a quick
            smoke test before running the full dataset).
    """
    df = pd.read_excel(dataset_path)
    df.columns = df.columns.str.strip()

    if limit:
        df = df.iloc[:limit]

    pipeline = TasdeeqPipeline()

    all_results = []
    total_rows = len(df)

    for position, (row_index, row) in enumerate(df.iterrows(), start=1):
        roman_claim = row.get("claim_roman_urdu")
        expected_label_raw = row.get("verdict")
        expected_label = normalize_label(expected_label_raw)

        logger.info("Testing row %s (%d/%d)", row_index, position, total_rows)

        result = pipeline.verify(roman_claim)
        result["row_index"] = int(row_index)
        result["expected_label_raw"] = expected_label_raw
        result["expected_label_normalized"] = expected_label

        all_results.append(result)

        print(f"\nRow {row_index} ({position}/{total_rows}):")
        print(f"  Claim     : {roman_claim}")
        print(f"  Expected  : {expected_label_raw} -> {expected_label}")
        if result["status"] == "ok":
            print(f"  Got       : {result['verdict']} (confidence: {result['confidence']})")
        else:
            print(f"  ERRORED at stage '{result['error_stage']}': {result['error_message']}")

        # Persist progress after every row so partial results survive a crash.
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)

    _print_summary(all_results, df)
    logger.info("All results saved to: %s", output_file)


def _print_summary(all_results: list, df: pd.DataFrame) -> None:
    """Prints overall accuracy and a per-category breakdown."""
    ok_results = [r for r in all_results if r["status"] == "ok"]
    errored_results = [r for r in all_results if r["status"] == "error"]

    correct = sum(
        1 for r in ok_results
        if r["expected_label_normalized"] == str(r.get("verdict", "")).strip().lower()
    )
    total_ok = len(ok_results)

    print("\n=== FINAL RESULTS ===")
    print(f"Total rows tested   : {len(all_results)}")
    print(f"Errored rows        : {len(errored_results)}  (excluded from accuracy)")
    print(f"Valid comparisons   : {total_ok}")
    print(f"Correct             : {correct}")
    print(f"ACCURACY            : {(correct / total_ok) * 100:.1f}%" if total_ok else "ACCURACY: N/A")

    if errored_results:
        print("\n--- Errored rows (system/API failures, not model judgments) ---")
        for r in errored_results:
            print(f"  Row {r['row_index']}: [{r['error_stage']}] {r['error_message']}")

    if "category" in df.columns and ok_results:
        print("\n=== BREAKDOWN BY CATEGORY ===")
        results_df = pd.DataFrame(ok_results)
        category_lookup = df[["category"]].reset_index().rename(columns={"index": "row_index"})
        merged = results_df.merge(category_lookup, on="row_index", how="left")

        for category, group in merged.groupby("category"):
            cat_correct = sum(
                1 for _, r in group.iterrows()
                if r["expected_label_normalized"] == str(r.get("verdict", "")).strip().lower()
            )
            cat_total = len(group)
            print(f"  {category}: {cat_correct}/{cat_total} ({(cat_correct / cat_total) * 100:.1f}%)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    run_batch_test(dataset_path="data/Tehqeeq Data_clean.xlsx", limit=None)