"""Base class for paper collectors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Paper


class BaseCollector(ABC):
    """Abstract base class for all paper source collectors."""

    source_name: str = "unknown"

    @abstractmethod
    def search(self, query: str, max_results: int = 20) -> list[Paper]:
        """Search for papers matching the query.

        Args:
            query: Search query string (keywords, topic, etc.)
            max_results: Maximum number of results to return.

        Returns:
            List of Paper objects.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} source={self.source_name}>"
