"""
Tehqeeq Dataset Cleaner
Standardizes verdict and category casing across both CSV and Excel files.
Run this once, it'll fix both files and save clean versions.
"""

import pandas as pd

# ---- File paths (update if your files are named differently) ----
CSV_PATH = "data/tehqeeq_data.csv"
XLSX_PATH = "data/Tehqeeq Data.xlsx"

CSV_OUTPUT = "data/tehqeeq_data_clean.csv"
XLSX_OUTPUT = "data/Tehqeeq Data_clean.xlsx"


def clean_dataframe(df):
    # Strip whitespace from column names
    df.columns = [c.strip() for c in df.columns]

    # Standardize verdict: strip spaces, fix casing -> Title Case
    df["verdict"] = df["verdict"].astype(str).str.strip().str.title()

    # Standardize category: strip spaces, fix casing -> Title Case
    df["category"] = df["category"].astype(str).str.strip().str.title()

    # Drop exact duplicate rows if any snuck in
    before = len(df)
    df = df.drop_duplicates(subset=["claim_roman_urdu", "claim_english"])
    after = len(df)
    if before != after:
        print(f"⚠️  Removed {before - after} duplicate rows")

    return df


def main():
    # Clean CSV
    try:
        df_csv = pd.read_csv(CSV_PATH)
        df_csv = clean_dataframe(df_csv)
        df_csv.to_csv(CSV_OUTPUT, index=False)
        print(f"✅ Cleaned CSV saved to {CSV_OUTPUT} ({len(df_csv)} rows)")
        print("Verdict counts:\n", df_csv["verdict"].value_counts())
        print("Category counts:\n", df_csv["category"].value_counts())
    except FileNotFoundError:
        print(f"⚠️  {CSV_PATH} not found, skipping CSV cleanup")

    print()

    # Clean Excel
    try:
        df_xlsx = pd.read_excel(XLSX_PATH)
        df_xlsx = clean_dataframe(df_xlsx)
        df_xlsx.to_excel(XLSX_OUTPUT, index=False)
        print(f"✅ Cleaned Excel saved to {XLSX_OUTPUT} ({len(df_xlsx)} rows)")
    except FileNotFoundError:
        print(f"⚠️  {XLSX_PATH} not found, skipping Excel cleanup")


if __name__ == "__main__":
    main()