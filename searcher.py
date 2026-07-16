"""
searcher.py

Responsible for taking an English factual claim and retrieving supporting
or contradicting evidence from the web via the Tavily search API.

Results from known fact-checking / authoritative domains are ranked above
general web results, and each result is tagged with `is_trusted_source`
so downstream components (or a human reviewer) can weigh evidence
accordingly.
"""

import os
import logging
from typing import Optional

from dotenv import load_dotenv
from tavily import TavilyClient

logger = logging.getLogger(__name__)
load_dotenv()

# Domains treated as higher-reliability sources for fact-checking purposes.
TRUSTED_DOMAINS = [
    "sochfactcheck.com",
    "geo.tv",
    "factcheck.afp.com",
    "who.int",
]

MAX_CONTENT_CHARS = 500  # Trim long snippets to keep downstream LLM prompts compact.


class ClaimSearcher:
    """Searches the web for evidence relevant to a given factual claim."""

    def __init__(self, api_key: Optional[str] = None):
        resolved_key = api_key or os.getenv("TAVILY_API_KEY")
        if not resolved_key:
            raise EnvironmentError(
                "TAVILY_API_KEY not found. Set it in your .env file or pass it explicitly."
            )
        self.client = TavilyClient(api_key=resolved_key)

    def search_claim(self, english_claim: str, max_results: int = 4) -> dict:
        """
        Args:
            english_claim: The claim to search for, in English.
            max_results: Maximum number of results to retrieve.

        Returns:
            {
                "status": "ok" | "error",
                "results": list[dict],   # empty on error or no matches
                "error_message": str | None,
            }
        """
        if not english_claim or not english_claim.strip():
            return {"status": "error", "results": [], "error_message": "Empty claim provided."}

        try:
            response = self.client.search(
                query=english_claim,
                search_depth="advanced",
                max_results=max_results,
            )
            raw_results = response.get("results", [])
            raw_results.sort(key=self._priority)

            cleaned_results = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:MAX_CONTENT_CHARS],
                    "is_trusted_source": self._is_trusted(r.get("url", "")),
                }
                for r in raw_results
            ]

            return {"status": "ok", "results": cleaned_results, "error_message": None}

        except Exception as e:
            logger.exception("Web search failed for claim: %s", english_claim)
            return {"status": "error", "results": [], "error_message": str(e)}

    @staticmethod
    def _is_trusted(url: str) -> bool:
        return any(domain in url for domain in TRUSTED_DOMAINS)

    @classmethod
    def _priority(cls, result: dict) -> int:
        """Lower value = higher priority in sort order."""
        return 0 if cls._is_trusted(result.get("url", "")) else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    searcher = ClaimSearcher()
    outcome = searcher.search_claim("Drinking hot water can cure cancer")

    print(f"Status: {outcome['status']}")
    if outcome["status"] == "error":
        print(f"Error: {outcome['error_message']}")
    else:
        for r in outcome["results"]:
            trust_tag = "[TRUSTED]" if r["is_trusted_source"] else "[general]"
            print(f"{trust_tag} {r['title']}\n  {r['url']}\n  {r['content'][:150]}...\n")