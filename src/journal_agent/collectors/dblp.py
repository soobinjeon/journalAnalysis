"""DBLP paper collector."""

from __future__ import annotations

import time
from datetime import date

import httpx

from ..models import Paper, PaperSource
from .base import BaseCollector


class DBLPCollector(BaseCollector):
    """Collector using the DBLP search API."""

    source_name = "dblp"
    BASE_URL = "https://dblp.org/search/publ/api"

    def search(self, query: str, max_results: int = 20) -> list[Paper]:
        """Search DBLP for papers."""
        params = {
            "q": query,
            "format": "json",
            "h": min(max_results, 100),
        }

        try:
            resp = httpx.get(self.BASE_URL, params=params, timeout=30, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"[DBLP] API error: {e}")
            return []

        data = resp.json()
        papers: list[Paper] = []

        hits = data.get("result", {}).get("hits", {}).get("hit", [])
        for hit in hits:
            info = hit.get("info", {})
            title = info.get("title", "")
            if not title:
                continue

            # Authors - can be string or dict or list
            authors_raw = info.get("authors", {}).get("author", [])
            if isinstance(authors_raw, dict):
                authors_raw = [authors_raw]
            elif isinstance(authors_raw, str):
                authors_raw = [{"text": authors_raw}]
            authors = []
            for a in authors_raw:
                if isinstance(a, dict):
                    authors.append(a.get("text", a.get("@pid", "")))
                else:
                    authors.append(str(a))

            # Date
            pub_date = None
            year = info.get("year")
            if year:
                try:
                    pub_date = date(int(year), 1, 1)
                except (ValueError, TypeError):
                    pass

            # Venue
            venue = info.get("venue")

            # DOI
            doi = info.get("doi")
            if doi and doi.startswith("https://doi.org/"):
                doi = doi.replace("https://doi.org/", "")

            # URL
            url = info.get("ee", info.get("url", ""))
            if isinstance(url, list):
                url = url[0] if url else ""

            # DBLP key as source_id
            source_id = info.get("key", hit.get("@id", ""))

            paper = Paper(
                title=title.strip().rstrip("."),
                authors=authors,
                abstract="",  # DBLP doesn't provide abstracts
                source=PaperSource.DBLP,
                source_id=source_id,
                url=url,
                published_date=pub_date,
                doi=doi,
                venue=venue,
                open_access=False,  # DBLP is metadata-only
                citation_count=0,
            )
            papers.append(paper)

        time.sleep(1)
        return papers
