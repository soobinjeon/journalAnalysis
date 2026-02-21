"""SQLite storage layer for the journal agent system."""

from __future__ import annotations

import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from .models import Paper, ResearchArea, AnalysisResult, TrendReport

DEFAULT_DB_PATH = Path.home() / ".journal_agent" / "papers.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    keywords TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    authors TEXT NOT NULL,
    abstract TEXT NOT NULL,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    published_date TEXT,
    doi TEXT,
    venue TEXT,
    open_access INTEGER DEFAULT 0,
    citation_count INTEGER DEFAULT 0,
    areas TEXT DEFAULT '[]',
    keywords TEXT DEFAULT '[]',
    pdf_url TEXT,
    collected_at TEXT NOT NULL,
    UNIQUE(source, source_id)
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL REFERENCES papers(id),
    summary TEXT NOT NULL,
    extracted_keywords TEXT NOT NULL,
    importance_score REAL NOT NULL,
    analyzed_at TEXT NOT NULL,
    UNIQUE(paper_id)
);

CREATE TABLE IF NOT EXISTS trend_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area_name TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    hot_keywords TEXT NOT NULL,
    top_paper_ids TEXT NOT NULL,
    summary TEXT NOT NULL,
    total_papers INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_published ON papers(published_date);
CREATE INDEX IF NOT EXISTS idx_papers_collected ON papers(collected_at);
"""


class Storage:
    """SQLite-backed storage for papers, areas, analyses, and reports."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(_SCHEMA)
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Research Areas ──────────────────────────────────────────────

    def add_area(self, area: ResearchArea) -> ResearchArea:
        area.created_at = area.created_at or datetime.now()
        d = area.to_dict()
        cur = self.conn.execute(
            "INSERT INTO research_areas (name, keywords, created_at) VALUES (?, ?, ?)",
            (d["name"], d["keywords"], d["created_at"]),
        )
        self.conn.commit()
        area.id = cur.lastrowid
        return area

    def get_areas(self) -> list[ResearchArea]:
        rows = self.conn.execute("SELECT * FROM research_areas ORDER BY name").fetchall()
        return [ResearchArea.from_dict(dict(r)) for r in rows]

    def get_area_by_name(self, name: str) -> Optional[ResearchArea]:
        row = self.conn.execute(
            "SELECT * FROM research_areas WHERE name = ?", (name,)
        ).fetchone()
        return ResearchArea.from_dict(dict(row)) if row else None

    def delete_area(self, name: str) -> bool:
        cur = self.conn.execute("DELETE FROM research_areas WHERE name = ?", (name,))
        self.conn.commit()
        return cur.rowcount > 0

    # ── Papers ──────────────────────────────────────────────────────

    def save_paper(self, paper: Paper) -> Paper:
        """Insert or update a paper. Returns paper with id set."""
        paper.collected_at = paper.collected_at or datetime.now()
        d = paper.to_dict()
        # Remove id for insert
        d.pop("id", None)
        cols = list(d.keys())
        placeholders = ", ".join(["?"] * len(cols))
        update_clause = ", ".join(
            f"{c} = excluded.{c}" for c in cols if c not in ("source", "source_id")
        )
        sql = (
            f"INSERT INTO papers ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(source, source_id) DO UPDATE SET {update_clause}"
        )
        cur = self.conn.execute(sql, [d[c] for c in cols])
        self.conn.commit()
        if cur.lastrowid:
            paper.id = cur.lastrowid
        else:
            # Fetch existing id
            row = self.conn.execute(
                "SELECT id FROM papers WHERE source = ? AND source_id = ?",
                (paper.source.value, paper.source_id),
            ).fetchone()
            if row:
                paper.id = row["id"]
        return paper

    def save_papers(self, papers: list[Paper]) -> int:
        """Bulk save papers. Returns count of new papers inserted."""
        count = 0
        for p in papers:
            before_id = p.id
            self.save_paper(p)
            if before_id is None:
                count += 1
        return count

    def get_papers(
        self,
        area: Optional[str] = None,
        recent_days: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Paper]:
        conditions: list[str] = []
        params: list = []

        if area:
            conditions.append("areas LIKE ?")
            params.append(f"%{area}%")

        if recent_days is not None:
            cutoff = (datetime.now() - timedelta(days=recent_days)).isoformat()
            conditions.append("collected_at >= ?")
            params.append(cutoff)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM papers {where} ORDER BY collected_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self.conn.execute(sql, params).fetchall()
        return [Paper.from_dict(dict(r)) for r in rows]

    def get_paper_by_id(self, paper_id: int) -> Optional[Paper]:
        row = self.conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        return Paper.from_dict(dict(row)) if row else None

    def count_papers(self, area: Optional[str] = None) -> int:
        if area:
            row = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM papers WHERE areas LIKE ?",
                (f"%{area}%",),
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) as cnt FROM papers").fetchone()
        return row["cnt"] if row else 0

    def get_unanalyzed_papers(self, limit: int = 50) -> list[Paper]:
        sql = """
            SELECT p.* FROM papers p
            LEFT JOIN analysis_results a ON p.id = a.paper_id
            WHERE a.id IS NULL
            ORDER BY p.collected_at DESC
            LIMIT ?
        """
        rows = self.conn.execute(sql, (limit,)).fetchall()
        return [Paper.from_dict(dict(r)) for r in rows]

    # ── Analysis Results ────────────────────────────────────────────

    def save_analysis(self, result: AnalysisResult) -> AnalysisResult:
        result.analyzed_at = result.analyzed_at or datetime.now()
        d = result.to_dict()
        d.pop("id", None)
        cols = list(d.keys())
        placeholders = ", ".join(["?"] * len(cols))
        update_clause = ", ".join(
            f"{c} = excluded.{c}" for c in cols if c != "paper_id"
        )
        sql = (
            f"INSERT INTO analysis_results ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(paper_id) DO UPDATE SET {update_clause}"
        )
        cur = self.conn.execute(sql, [d[c] for c in cols])
        self.conn.commit()
        result.id = cur.lastrowid
        return result

    def get_analysis(self, paper_id: int) -> Optional[AnalysisResult]:
        row = self.conn.execute(
            "SELECT * FROM analysis_results WHERE paper_id = ?", (paper_id,)
        ).fetchone()
        return AnalysisResult.from_dict(dict(row)) if row else None

    # ── Trend Reports ───────────────────────────────────────────────

    def save_trend_report(self, report: TrendReport) -> TrendReport:
        report.created_at = report.created_at or datetime.now()
        d = report.to_dict()
        d.pop("id", None)
        cols = list(d.keys())
        placeholders = ", ".join(["?"] * len(cols))
        sql = f"INSERT INTO trend_reports ({', '.join(cols)}) VALUES ({placeholders})"
        cur = self.conn.execute(sql, [d[c] for c in cols])
        self.conn.commit()
        report.id = cur.lastrowid
        return report

    def get_latest_trend(self, area_name: str) -> Optional[TrendReport]:
        row = self.conn.execute(
            "SELECT * FROM trend_reports WHERE area_name = ? ORDER BY created_at DESC LIMIT 1",
            (area_name,),
        ).fetchone()
        return TrendReport.from_dict(dict(row)) if row else None

    # ── Stats ───────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        papers = self.conn.execute("SELECT COUNT(*) as cnt FROM papers").fetchone()["cnt"]
        areas = self.conn.execute("SELECT COUNT(*) as cnt FROM research_areas").fetchone()["cnt"]
        analyzed = self.conn.execute("SELECT COUNT(*) as cnt FROM analysis_results").fetchone()["cnt"]
        reports = self.conn.execute("SELECT COUNT(*) as cnt FROM trend_reports").fetchone()["cnt"]

        source_counts = {}
        for row in self.conn.execute(
            "SELECT source, COUNT(*) as cnt FROM papers GROUP BY source"
        ).fetchall():
            source_counts[row["source"]] = row["cnt"]

        return {
            "total_papers": papers,
            "total_areas": areas,
            "total_analyzed": analyzed,
            "total_reports": reports,
            "papers_by_source": source_counts,
        }
