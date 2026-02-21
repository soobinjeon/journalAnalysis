"""Semantic Scholar paper collector."""

from __future__ import annotations

import time
from datetime import date

import httpx

from ..models import Paper, PaperSource
from .base import BaseCollector


class SemanticScholarCollector(BaseCollector):
    """Collector using the Semantic Scholar Academic Graph API."""

    source_name = "semantic_scholar"
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    FIELDS = "paperId,title,abstract,authors,year,venue,externalIds,url,openAccessPdf,citationCount,publicationDate"

    def search(self, query: str, max_results: int = 20) -> list[Paper]:
        """Search Semantic Scholar for papers."""
        url = f"{self.BASE_URL}/paper/search"
        params = {
            "query": query,
            "limit": min(max_results, 100),  # API max is 100
            "fields": self.FIELDS,
        }

        # Retry with backoff for rate limiting
        for attempt in range(3):
            try:
                resp = httpx.get(url, params=params, timeout=30, follow_redirects=True)
                if resp.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    print(f"[SemanticScholar] Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            except httpx.HTTPError as e:
                if attempt == 2:
                    print(f"[SemanticScholar] API error: {e}")
                    return []
                time.sleep(2)
                continue
        else:
            print("[SemanticScholar] Max retries exceeded.")
            return []

        data = resp.json()
        papers: list[Paper] = []

        for item in data.get("data", []):
            if not item.get("title"):
                continue

            # Parse authors
            authors = [
                a.get("name", "")
                for a in item.get("authors", [])
                if a.get("name")
            ]

            # Parse date
            pub_date = None
            if item.get("publicationDate"):
                try:
                    pub_date = date.fromisoformat(item["publicationDate"])
                except (ValueError, TypeError):
                    pass
            elif item.get("year"):
                pub_date = date(item["year"], 1, 1)

            # DOI
            ext_ids = item.get("externalIds", {}) or {}
            doi = ext_ids.get("DOI")
            arxiv_id = ext_ids.get("ArXiv")

            # Open access
            oa_pdf = item.get("openAccessPdf")
            pdf_url = oa_pdf.get("url") if oa_pdf else None
            is_oa = pdf_url is not None

            paper = Paper(
                title=item["title"].strip(),
                authors=authors,
                abstract=(item.get("abstract") or "").strip(),
                source=PaperSource.SEMANTIC_SCHOLAR,
                source_id=item.get("paperId", ""),
                url=item.get("url", f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}"),
                published_date=pub_date,
                doi=doi,
                venue=item.get("venue") or None,
                open_access=is_oa,
                citation_count=item.get("citationCount", 0) or 0,
                pdf_url=pdf_url,
            )
            papers.append(paper)

        # Respect rate limit (100 req/5min for unauthenticated)
        time.sleep(1)
        return papers
