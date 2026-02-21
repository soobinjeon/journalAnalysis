"""CrossRef paper collector."""

from __future__ import annotations

import time
from datetime import date

import httpx

from ..models import Paper, PaperSource
from .base import BaseCollector


class CrossRefCollector(BaseCollector):
    """Collector using the CrossRef REST API."""

    source_name = "crossref"
    BASE_URL = "https://api.crossref.org/works"

    def search(self, query: str, max_results: int = 20) -> list[Paper]:
        """Search CrossRef for papers."""
        params = {
            "query.bibliographic": query,
            "filter": "has-abstract:true",
            "rows": min(max_results, 100),
            "sort": "published",
            "order": "desc",
            "select": "DOI,title,author,abstract,URL,published,container-title,link,is-referenced-by-count",
        }
        headers = {
            "User-Agent": "JournalAgent/0.1 (mailto:research@example.com)",
        }

        try:
            resp = httpx.get(self.BASE_URL, params=params, headers=headers, timeout=30, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"[CrossRef] API error: {e}")
            return []

        data = resp.json()
        papers: list[Paper] = []

        for item in data.get("message", {}).get("items", []):
            # Title
            titles = item.get("title", [])
            title = titles[0] if titles else ""
            if not title:
                continue

            # Authors
            authors = []
            for a in item.get("author", []):
                name_parts = []
                if a.get("given"):
                    name_parts.append(a["given"])
                if a.get("family"):
                    name_parts.append(a["family"])
                if name_parts:
                    authors.append(" ".join(name_parts))

            # Abstract (CrossRef often has JATS XML, strip tags)
            abstract_raw = item.get("abstract", "")
            if abstract_raw:
                import re
                abstract = re.sub(r"<[^>]+>", "", abstract_raw).strip()
            else:
                abstract = ""

            # Published date
            pub_date = None
            date_parts = item.get("published", {}).get("date-parts", [[]])
            if date_parts and date_parts[0]:
                parts = date_parts[0]
                try:
                    year = parts[0]
                    month = parts[1] if len(parts) > 1 else 1
                    day = parts[2] if len(parts) > 2 else 1
                    pub_date = date(year, month, day)
                except (ValueError, IndexError):
                    pass

            # Venue
            containers = item.get("container-title", [])
            venue = containers[0] if containers else None

            # DOI
            doi = item.get("DOI", "")

            # PDF link
            pdf_url = None
            for link in item.get("link", []):
                if link.get("content-type") == "application/pdf":
                    pdf_url = link.get("URL")
                    break

            # OA detection: if there's a free PDF link
            is_oa = pdf_url is not None

            paper = Paper(
                title=title.strip(),
                authors=authors,
                abstract=abstract,
                source=PaperSource.CROSSREF,
                source_id=doi,
                url=item.get("URL", f"https://doi.org/{doi}"),
                published_date=pub_date,
                doi=doi,
                venue=venue,
                open_access=is_oa,
                citation_count=item.get("is-referenced-by-count", 0) or 0,
                pdf_url=pdf_url,
            )
            papers.append(paper)

        time.sleep(1)
        return papers
