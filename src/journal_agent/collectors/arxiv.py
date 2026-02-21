"""arXiv paper collector using the arXiv API (Atom feed)."""

from __future__ import annotations

import time
from datetime import date

import feedparser
import httpx

from ..models import Paper, PaperSource
from .base import BaseCollector


class ArxivCollector(BaseCollector):
    """Collector for arXiv papers via the arXiv API."""

    source_name = "arxiv"
    BASE_URL = "https://export.arxiv.org/api/query"

    def search(self, query: str, max_results: int = 20) -> list[Paper]:
        """Search arXiv for papers matching the query."""
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        try:
            resp = httpx.get(self.BASE_URL, params=params, timeout=30, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"[arXiv] API error: {e}")
            return []

        feed = feedparser.parse(resp.text)
        papers: list[Paper] = []

        for entry in feed.entries:
            # Extract arXiv ID from the entry id URL
            arxiv_id = entry.id.split("/abs/")[-1]

            # Parse published date
            pub_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                t = entry.published_parsed
                pub_date = date(t.tm_year, t.tm_mon, t.tm_mday)

            # Extract authors
            authors = []
            if hasattr(entry, "authors"):
                authors = [a.get("name", "") for a in entry.authors]
            elif hasattr(entry, "author"):
                authors = [entry.author]

            # Find PDF link
            pdf_url = None
            for link in entry.get("links", []):
                if link.get("type") == "application/pdf":
                    pdf_url = link["href"]
                    break

            # Get categories / venue
            categories = []
            if hasattr(entry, "tags"):
                categories = [t.get("term", "") for t in entry.tags]

            paper = Paper(
                title=entry.title.replace("\n", " ").strip(),
                authors=authors,
                abstract=entry.summary.replace("\n", " ").strip() if entry.summary else "",
                source=PaperSource.ARXIV,
                source_id=arxiv_id,
                url=entry.id,
                published_date=pub_date,
                doi=entry.get("arxiv_doi", None),
                venue=", ".join(categories[:3]) if categories else "arXiv",
                open_access=True,  # arXiv is always OA
                pdf_url=pdf_url,
            )
            papers.append(paper)

        # Respect arXiv rate limit (3 sec between requests)
        time.sleep(3)
        return papers
