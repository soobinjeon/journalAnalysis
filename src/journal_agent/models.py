"""Core data models for the journal agent system."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from enum import Enum
from typing import Optional


class PaperSource(str, Enum):
    """Source from which a paper was collected."""

    ARXIV = "arxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    CROSSREF = "crossref"
    DBLP = "dblp"


@dataclass
class Paper:
    """Represents an academic paper."""

    title: str
    authors: list[str]
    abstract: str
    source: PaperSource
    source_id: str  # ID within the source (e.g., arXiv ID)
    url: str
    published_date: Optional[date] = None
    doi: Optional[str] = None
    venue: Optional[str] = None  # Journal or conference name
    open_access: bool = False
    citation_count: int = 0
    areas: list[str] = field(default_factory=list)  # Research area tags
    keywords: list[str] = field(default_factory=list)
    pdf_url: Optional[str] = None
    # Internal
    id: Optional[int] = None
    collected_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["authors"] = json.dumps(self.authors, ensure_ascii=False)
        d["areas"] = json.dumps(self.areas, ensure_ascii=False)
        d["keywords"] = json.dumps(self.keywords, ensure_ascii=False)
        d["source"] = self.source.value
        if self.published_date:
            d["published_date"] = self.published_date.isoformat()
        if self.collected_at:
            d["collected_at"] = self.collected_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Paper:
        d = dict(d)
        d["authors"] = json.loads(d["authors"]) if isinstance(d["authors"], str) else d["authors"]
        d["areas"] = json.loads(d["areas"]) if isinstance(d["areas"], str) else d["areas"]
        d["keywords"] = json.loads(d["keywords"]) if isinstance(d["keywords"], str) else d["keywords"]
        d["source"] = PaperSource(d["source"])
        if d.get("published_date") and isinstance(d["published_date"], str):
            d["published_date"] = date.fromisoformat(d["published_date"])
        if d.get("collected_at") and isinstance(d["collected_at"], str):
            d["collected_at"] = datetime.fromisoformat(d["collected_at"])
        return cls(**d)

    @property
    def unique_key(self) -> str:
        """Return a deduplication key (DOI preferred, then source+source_id)."""
        if self.doi:
            return f"doi:{self.doi}"
        return f"{self.source.value}:{self.source_id}"


@dataclass
class ResearchArea:
    """A research area of interest with associated keywords."""

    name: str
    keywords: list[str]
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["keywords"] = json.dumps(self.keywords, ensure_ascii=False)
        if self.created_at:
            d["created_at"] = self.created_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> ResearchArea:
        d = dict(d)
        d["keywords"] = json.loads(d["keywords"]) if isinstance(d["keywords"], str) else d["keywords"]
        if d.get("created_at") and isinstance(d["created_at"], str):
            d["created_at"] = datetime.fromisoformat(d["created_at"])
        return cls(**d)


@dataclass
class AnalysisResult:
    """Analysis output for a single paper."""

    paper_id: int
    summary: str  # Extractive summary
    extracted_keywords: list[str]
    importance_score: float  # 0-100
    id: Optional[int] = None
    analyzed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["extracted_keywords"] = json.dumps(self.extracted_keywords, ensure_ascii=False)
        if self.analyzed_at:
            d["analyzed_at"] = self.analyzed_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> AnalysisResult:
        d = dict(d)
        d["extracted_keywords"] = (
            json.loads(d["extracted_keywords"])
            if isinstance(d["extracted_keywords"], str)
            else d["extracted_keywords"]
        )
        if d.get("analyzed_at") and isinstance(d["analyzed_at"], str):
            d["analyzed_at"] = datetime.fromisoformat(d["analyzed_at"])
        return cls(**d)


@dataclass
class TrendReport:
    """A trend report for a specific period and area."""

    area_name: str
    period_start: date
    period_end: date
    hot_keywords: list[str]
    top_paper_ids: list[int]
    summary: str
    total_papers: int = 0
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["hot_keywords"] = json.dumps(self.hot_keywords, ensure_ascii=False)
        d["top_paper_ids"] = json.dumps(self.top_paper_ids)
        d["period_start"] = self.period_start.isoformat()
        d["period_end"] = self.period_end.isoformat()
        if self.created_at:
            d["created_at"] = self.created_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> TrendReport:
        d = dict(d)
        d["hot_keywords"] = json.loads(d["hot_keywords"]) if isinstance(d["hot_keywords"], str) else d["hot_keywords"]
        d["top_paper_ids"] = json.loads(d["top_paper_ids"]) if isinstance(d["top_paper_ids"], str) else d["top_paper_ids"]
        if isinstance(d["period_start"], str):
            d["period_start"] = date.fromisoformat(d["period_start"])
        if isinstance(d["period_end"], str):
            d["period_end"] = date.fromisoformat(d["period_end"])
        if d.get("created_at") and isinstance(d["created_at"], str):
            d["created_at"] = datetime.fromisoformat(d["created_at"])
        return cls(**d)
