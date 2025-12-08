import asyncio
from typing import List, Dict, Any
import structlog

from ...parsers.content_parser_factory import ContentParserFactory
from ...services.file_storage import FileStorageService
from ...repositories.file_repository import FileRepository
from ...utils.validation_utils import validate_input_sources, validate_content_results
from ...exceptions import ParsingError

logger = structlog.get_logger(__name__)


class ContentParsingCoordinator:
    def __init__(self, db_session):
        self.parser_factory = ContentParserFactory()
        self.file_storage = FileStorageService()
        self.file_repository = FileRepository(db_session)

    async def parse_all_content_sources(self, input_sources: List[Dict[str, Any]], user_id: str) -> List[Any]:
        validate_input_sources(input_sources)

        logger.info("content_parsing_started", source_count=len(input_sources))

        parse_tasks = self._create_parse_tasks(input_sources, user_id)
        results = await asyncio.gather(*parse_tasks, return_exceptions=True)

        processed_results = self._process_parse_results(results)
        validate_content_results(processed_results)

        logger.info("content_parsing_completed",
                   total_sources=len(input_sources),
                   successful_parses=len(processed_results))

        return processed_results

    def _create_parse_tasks(self, input_sources: List[Dict[str, Any]], user_id: str) -> List[asyncio.Task]:
        tasks = []
        for source in input_sources:
            content_type = source["content_type"]
            source_id = source["id"]

            if content_type == "youtube":
                task = asyncio.create_task(self._parse_url(content_type, source_id, user_id))
            elif content_type == "web_url":
                task = asyncio.create_task(self._parse_url(content_type, source_id, user_id))
            else:
                task = asyncio.create_task(self._parse_file(content_type, source_id, user_id))

            tasks.append(task)

        return tasks

    def _process_parse_results(self, results: List[Any]) -> List[Any]:
        processed = []
        for result in results:
            if isinstance(result, Exception):
                logger.error("parse_task_failed", error=str(result))
                continue

            if hasattr(result, 'success') and result.success:
                processed.append(result)
            else:
                logger.warning("parse_result_failed", error=getattr(result, 'error', 'Unknown error'))

        return processed

    def combine_parsed_results(self, results: List[Any]) -> Dict[str, Any]:
        if not results:
            raise ParsingError("No successful parsing results to combine")

        combined_content = []
        combined_title_parts = []
        total_content_length = 0

        for result in results:
            if hasattr(result, 'content') and result.content:
                combined_content.append(result.content)
                total_content_length += len(result.content)

            if hasattr(result, 'title') and result.title:
                combined_title_parts.append(result.title)

        combined_text = "\n\n".join(combined_content)
        combined_title = " | ".join(combined_title_parts) if combined_title_parts else "Untitled Content"

        return {
            "content": combined_text,
            "title": combined_title,
            "total_length": total_content_length,
            "source_count": len(results)
        }

    async def _parse_url(self, content_type: str, url: str, user_id: str):
        try:
            parser = self.parser_factory.get_parser(content_type)
            if not parser:
                raise ParsingError(f"No parser available for content type: {content_type}")

            result = await parser.parse(url)
            logger.info("url_parse_completed", content_type=content_type, url=url[:100])
            return result

        except Exception as e:
            logger.error("url_parse_failed", content_type=content_type, url=url[:100], error=str(e))
            raise ParsingError(f"Failed to parse {content_type}: {str(e)}")

    async def _parse_file(self, content_type: str, file_id: str, user_id: str):
        try:
            uploaded_file = self.file_repository.get_by_id(file_id)
            if not uploaded_file:
                raise ParsingError(f"File {file_id} not found")

            file_path = self.file_storage.get_file_path(uploaded_file.file_path)
            parser = self.parser_factory.get_parser(content_type)

            if not parser:
                raise ParsingError(f"No parser available for content type: {content_type}")

            result = await parser.parse(str(file_path))
            logger.info("file_parse_completed", content_type=content_type, file_id=file_id)
            return result

        except Exception as e:
            logger.error("file_parse_failed", content_type=content_type, file_id=file_id, error=str(e))
            raise ParsingError(f"Failed to parse {content_type} file: {str(e)}")

    def detect_url_type(self, url: str) -> str:
        url_lower = url.lower()

        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        elif url_lower.startswith(("http://", "https://")):
            return "web_url"

        return "unknown"