"""
Module: search_sanity_checker.py
Description: Evaluates Tavily Search API performance on Roman Urdu queries vs. English queries 
             for fake news detection and factual verification.
"""

import os
import logging
import argparse
import pandas as pd
from dotenv import load_dotenv
from tavily import TavilyClient

# Configure Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SearchSanityChecker:
    def __init__(self, dataset_path: str):
        load_dotenv()
        self.api_key = os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise EnvironmentError("TAVILY_API_KEY environment variable is missing.")

        self.client = TavilyClient(api_key=self.api_key)
        self.dataset_path = dataset_path
        self.df = None

    def load_dataset(self) -> pd.DataFrame:
        """Loads and sanitizes column headers of the dataset."""
        try:
            self.df = pd.read_excel(self.dataset_path)
            self.df.columns = self.df.columns.str.strip()
            logger.info(f"Successfully loaded dataset from {self.dataset_path} with {len(self.df)} records.")
            return self.df
        except FileNotFoundError as e:
            logger.error(f"Dataset not found at path: {self.dataset_path}")
            raise e

    def execute_search(self, query: str, max_results: int = 2) -> list:
        """Helper to safely query Tavily API."""
        try:
            response = self.client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results
            )
            return response.get('results', [])
        except Exception as e:
            logger.error(f"Tavily API search failed for query '{query}': {str(e)}")
            return []

    def run_check(self, indices: list):
        """Runs comparative search pipeline across Roman Urdu and English representations."""
        if self.df is None:
            self.load_dataset()

        records = self.df.iloc[indices]
        logger.info(f"Initiating evaluation on {len(records)} designated test cases.")

        for idx, row in records.iterrows():
            roman_query = row.get('claim_roman_urdu')
            english_query = row.get('claim_english')
            category = row.get('category', 'General')
            # FIX: category can be NaN/float for missing values -> str() before .upper()
            category_display = str(category).upper() if pd.notna(category) else "GENERAL"

            print("\n" + "="*100)
            print(f"CASE STUDY {idx+1} | Category: {category_display}")
            print(f"🔍 [Roman Urdu Query]: {roman_query}")
            print(f"🔍 [English Query]   : {english_query}")
            print("="*100 + "\n")

            # Evaluate Test A: Direct Roman Urdu Execution
            logger.info("Executing Test-A (Direct Roman Urdu Native Search)...")
            roman_results = self.execute_search(roman_query)
            logger.info(f"Test-A retrieved {len(roman_results)} hits.")
            for r_idx, res in enumerate(roman_results):
                # FIX: content can be None -> guard with `or ''` before slicing
                content = res.get('content') or ''
                print(f"  [RU-Hit {r_idx+1}] Title: {res.get('title')}")
                print(f"            URL     : {res.get('url')}")
                print(f"            Snippet : {content[:140]}...")

            # Evaluate Test B: Transformed English Execution
            logger.info("Executing Test-B (Semantic/English Query Search)...")
            english_results = self.execute_search(english_query)
            logger.info(f"Test-B retrieved {len(english_results)} hits.")
            for e_idx, res in enumerate(english_results):
                # FIX: same None-safety here
                content = res.get('content') or ''
                print(f"  [EN-Hit {e_idx+1}] Title: {res.get('title')}")
                print(f"            URL     : {res.get('url')}")
                print(f"            Snippet : {content[:140]}...")

            print("\n" + "-"*100)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tavily Search API Query Translation Sanity Checker")
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/Tehqeeq Data.xlsx",
        help="Path to the system ground-truth dataset."
    )
    args = parser.parse_args()

    # Evaluation targets selection
    # FIX: updated to spread across the full 80-row dataset (was hardcoded to old 20-row set)
    # Covers a wider mix of categories including Tech and ND which didn't exist in the old sample.
    target_indices = [0, 15, 30, 45, 60, 70]

    try:
        checker = SearchSanityChecker(dataset_path=args.dataset)
        checker.run_check(indices=target_indices)
    except Exception as error:
        logger.critical(f"System execution halted: {str(error)}")