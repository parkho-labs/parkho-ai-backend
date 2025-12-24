from .base import (
    RagChunk, RagQueryResponse, RagRetrieveResponse,
    RagLinkItem, RagLinkResponse, RagStatusItem,
    RagStatusResponse, RagDeleteResponse, RagLinkRequest,
    RagQueryRequest, BaseRagClient
)
from .core_client import CoreRagClient
from .law_client import LawRagClient
from .library_client import LibraryRagClient

# Singletons for convenience
core_rag_client = CoreRagClient()
law_rag_client = LawRagClient()
library_rag_client = LibraryRagClient()

__all__ = [
    "RagChunk", "RagQueryResponse", "RagRetrieveResponse",
    "RagLinkItem", "RagLinkResponse", "RagStatusItem",
    "RagStatusResponse", "RagDeleteResponse", "RagLinkRequest",
    "RagQueryRequest", "BaseRagClient",
    "CoreRagClient", "LawRagClient", "LibraryRagClient",
    "core_rag_client", "law_rag_client", "library_rag_client"
]
