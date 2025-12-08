import asyncio
from typing import List, Dict, Any
from pathlib import Path
import structlog

from ...parsers.content_parser_factory import ContentParserFactory
from ...services.file_storage import FileStorageService
from ...repositories.file_repository import FileRepository
from ...utils.validation_utils import validate_input_sources, validate_content_results
from ...exceptions import ParsingError
from ...api.v1.schemas import InputType

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

    def _create_parse_tasks(self, input_sources: List[Dict[str, Any]]) -> List[asyncio.Task]:
        tasks = []
        for source in input_sources:
            content_type = source["content_type"]
            source_id = source["id"]

            match content_type:
                case InputType.YOUTUBE:
                    tasks.append(asyncio.create_task(self._parse_youtube(source_id, user_id)))
                case InputType.WEB_URL:
                    tasks.append(asyncio.create_task(self._parse_web(source_id, user_id)))
                case InputType.COLLECTION:
                    tasks.append(asyncio.create_task(self._parse_collection(source_id, user_id)))
                case InputType.FILES:
                    tasks.append(asyncio.create_task(self._parse_file(content_type, source_id, user_id)))
                case _:
                    logger.warning("unsupported_content_type", content_type=content_type, source_id=source_id)

        return tasks

    async def _parse_youtube(self, url: str, user_id: str):
        return await self._parse_url(InputType.YOUTUBE.value, url, user_id)

    async def _parse_web(self, url: str, user_id: str):
        return await self._parse_url(InputType.WEB_URL.value, url, user_id)

    async def _parse_collection(self, collection_name: str, user_id: str):
        try:
            parser = self.parser_factory.get_parser("collection")
            if not parser:
                raise ParsingError("No parser available for collection type")

            result = await parser.parse(collection_name, user_id=user_id)
            logger.info("collection_parse_completed", collection=collection_name)
            return result

        except Exception as e:
            logger.error("collection_parse_failed", collection=collection_name, error=str(e))
            raise ParsingError(f"Failed to parse collection: {str(e)}")

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

            file_path = Path(self.file_storage.get_file_path(uploaded_file.file_path))

            # Prefer explicit parser; if not, detect based on filename/extension (for generic "files").
            parser = self.parser_factory.get_parser(content_type)
            if not parser:
                detected_type = self.parser_factory.detect_input_type(str(file_path), file_path.name)
                if detected_type:
                    parser = self.parser_factory.get_parser(detected_type)
                    content_type = detected_type

            if not parser:
                raise ParsingError(f"No parser available for content type: {content_type}")

            result = await parser.parse(str(file_path))
            logger.info("file_parse_completed", content_type=content_type, file_id=file_id, detected_type=content_type)
            return result

        except Exception as e:
            logger.error("file_parse_failed", content_type=content_type, file_id=file_id, error=str(e))
            raise ParsingError(f"Failed to parse {content_type} file: {str(e)}")
