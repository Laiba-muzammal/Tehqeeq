"""
searcher.py

Step 2 of the Tehqeeq pipeline: evidence retrieval.

Change log:
  v1: basic Tavily search, sorted by a small trusted-domain list.
  v2: max_results raised 4 -> 6, is_trusted flag added per result.
  v3: TRUSTED_DOMAINS expanded with more Pakistani news outlets --
      but this list was still Politics-centric.
  v4 (current): TRUSTED_DOMAINS broadened to cover ALL claim categories in
      the dataset, not just Pakistani politics. A full 80-row run after v3
      showed the verifier's trust guardrail (see verifier.py) was
      force-downgrading correct, well-evidenced verdicts in Health, Tech,
      and Natural Disaster claims to "uncertain" -- simply because their
      evidence came from legitimate but non-Pakistani-political domains
      (e.g. health/science sources, global tech news) that weren't on the
      trusted list. This caused Health accuracy to drop from 66.7% to
      25.0% and Tech from 66.7% to 26.7% in one run. The list below adds
      global authoritative sources across health, science, tech, and
      general news so the trust guardrail doesn't unfairly penalize
      claims outside the Politics category.
"""

import os
import logging
from dotenv import load_dotenv
from tavily import TavilyClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

TRUSTED_DOMAINS = [
    # Dedicated fact-checking outlets
    "sochfactcheck.com",
    "geo.tv",
    "factcheck.afp.com",
    "snopes.com",
    "politifact.com",
    "factcheck.org",
    "boomlive.in",
    # Pakistani government / official domains
    "gov.pk",
    "pta.gov.pk",
    "hec.gov.pk",
    "fbr.gov.pk",
    "nadra.gov.pk",
    "ndma.gov.pk",
    "pmd.gov.pk",
    # Major Pakistani news outlets
    "dawn.com",
    "tribune.com.pk",
    "thenews.com.pk",
    "brecorder.com",
    "app.com.pk",
    "radio.gov.pk",
    # Global general news (wire services / major outlets)
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "aljazeera.com",
    # Health / science authorities
    "who.int",
    "cdc.gov",
    "nih.gov",
    "ncbi.nlm.nih.gov",
    "nature.com",
    "sciencedirect.com",
    "thelancet.com",
    # Space / government science agencies
    "nasa.gov",
    "esa.int",
    # Major tech companies / outlets (for tech-product claims)
    "openai.com",
    "meta.com",
    "spotify.com",
    "techcrunch.com",
    "theverge.com",
    "wired.com",
    # Entertainment / awards authorities
    "festival-cannes.com",
    "oscars.org",
    "variety.com",
    "hollywoodreporter.com",
    "imdb.com",
    # Islamic calendar / moon-sighting authorities (added for claims about
    # Ramadan, Eid, and other Hijri-calendar-dependent events)
    "moonsighting.com",
    "islamicfinder.org",
    "timeanddate.com",
    "cabinet.gov.pk",       # Pakistan's Cabinet Division publishes official Ruet-e-Hilal announcements
]

CONTENT_SNIPPET_LENGTH = 500
DEFAULT_MAX_RESULTS = 6
RECENCY_WINDOW_DAYS = 7  # how far back "recent" search results are allowed to be

# English-side keywords that indicate a claim is about something recent/
# relative in time. The claim reaching this point has already been
# translated to English by extractor.py, so we check English keywords here
# (Roman Urdu words like "kal"/"aaj" get translated to "yesterday"/"today"
# before this point).
RECENCY_KEYWORDS = ["yesterday", "today", "this week", "recently", "just happened", "current"]


class ClaimSearcher:
    """Wraps a Tavily search call and post-processes results for downstream use."""

    def __init__(self):
        """Initialize the Tavily client using the `TAVILY_API_KEY` environment variable."""
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise EnvironmentError("TAVILY_API_KEY is missing from the environment (.env).")
        self.client = TavilyClient(api_key=api_key)

    @staticmethod
    def _is_time_sensitive(english_claim: str) -> bool:
        """Cheap keyword check: does this claim reference a recent/relative timeframe?"""
        lowered = english_claim.lower()
        return any(keyword in lowered for keyword in RECENCY_KEYWORDS)

    def search_claim(self, english_claim: str, max_results: int = DEFAULT_MAX_RESULTS) -> list[dict]:
        """Search the web for `english_claim` using Tavily and return
        a list of normalized result dicts for downstream processing.

        Results are sorted to prefer trusted domains and trimmed to
        `max_results` with content snippets shortened to a fixed length.
        """
        search_kwargs = {
            "query": english_claim,
            "search_depth": "advanced",
            "max_results": max_results,
        }

        # If the claim references a recent/relative timeframe, constrain
        # Tavily to recent results only, so stale articles from previous
        # years don\'t get treated as evidence for a "yesterday"/"today" claim.
        if self._is_time_sensitive(english_claim):
            search_kwargs["topic"] = "news"
            search_kwargs["days"] = RECENCY_WINDOW_DAYS
            logger.info("Claim looks time-sensitive; constraining search to last %d days.", RECENCY_WINDOW_DAYS)

        try:
            response = self.client.search(**search_kwargs)
            results = response.get("results", [])

            def is_trusted(url: str) -> bool:
                return any(domain in url for domain in TRUSTED_DOMAINS)

            results.sort(key=lambda r: 0 if is_trusted(r.get("url", "")) else 1)

            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": (r.get("content") or "")[:CONTENT_SNIPPET_LENGTH],
                    "is_trusted": is_trusted(r.get("url", "")),
                    # Tavily includes this for many (not all) results --
                    # None if unavailable, verifier.py handles that case.
                    "published_date": r.get("published_date"),
                }
                for r in results
            ]

        except Exception as exc:  # noqa: BLE001
            logger.error("Search request failed: %s", exc)
            return []


if __name__ == "__main__":
    searcher = ClaimSearcher()
    sample_claim = "Drinking hot water can cure cancer"
    for r in searcher.search_claim(sample_claim):
        tag = "[TRUSTED]" if r["is_trusted"] else "[unverified source]"
        print(f"- {tag} {r['title']}\n  {r['url']}\n  {r['content'][:150]}...\n")