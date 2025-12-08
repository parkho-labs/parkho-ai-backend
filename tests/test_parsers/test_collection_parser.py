import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.parsers.collection_parser import CollectionParser


class TestCollectionParser:
    @patch("src.parsers.collection_parser.RAGIntegrationService")
    @pytest.mark.asyncio
    async def test_parse_with_embeddings(self, mock_rag_service):
        mock_instance = MagicMock()
        mock_instance.get_embeddings = AsyncMock(return_value=[
            {"text": "Chunk 1", "source": "file1"},
            {"text": "Chunk 2", "source": "file2"},
        ])
        mock_rag_service.return_value = mock_instance

        parser = CollectionParser()
        result = await parser.parse("my-collection", user_id="user-123")

        mock_instance.get_embeddings.assert_awaited_with("my-collection", "user-123", 100)
        assert result.success
        assert "Chunk 1" in result.content
        assert "Chunk 2" in result.content
        assert result.metadata["collection_name"] == "my-collection"
        assert result.metadata["chunk_count"] == 2
        assert result.title == "Collection: my-collection"

    @patch("src.parsers.collection_parser.RAGIntegrationService")
    @pytest.mark.asyncio
    async def test_parse_no_embeddings_returns_error(self, mock_rag_service):
        mock_instance = MagicMock()
        mock_instance.get_embeddings = AsyncMock(return_value=[])
        mock_rag_service.return_value = mock_instance

        parser = CollectionParser()
        result = await parser.parse("empty-collection", user_id="user-123")

        assert not result.success
        assert "no files" in result.error.lower()

    def test_supports_source(self):
        parser = CollectionParser()
        assert parser.supports_source("collection-name")
        assert not parser.supports_source("")

    def test_supported_types(self):
        parser = CollectionParser()
        assert parser.supported_types == ["collection"]

