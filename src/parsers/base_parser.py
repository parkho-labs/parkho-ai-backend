from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class ContentParseResult:
    def __init__(
        self,
        content: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        self.content = content
        self.title = title
        self.metadata = metadata or {}
        self.error = error
        self.success = error is None

    def __repr__(self):
        status = "Success" if self.success else f"Error: {self.error}"
        return f"ContentParseResult({status}, content_length={len(self.content)})"


class BaseContentParser(ABC):

    @abstractmethod
    async def parse(self, source: str, **kwargs) -> ContentParseResult:
        pass

    @abstractmethod
    def supports_source(self, source: str) -> bool:
        pass

    @property
    @abstractmethod
    def supported_types(self) -> list[str]:
        pass