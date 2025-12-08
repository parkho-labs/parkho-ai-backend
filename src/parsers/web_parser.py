import time
import structlog
import httpx

from .base_parser import BaseContentParser, ContentParseResult
from ..exceptions import NetworkError, ValidationError, ParsingError
from ..utils.url_utils import validate_url, extract_domain, supports_web_url
from ..utils.string_utils import truncate_text, clean_text


logger = structlog.get_logger(__name__)


class WebContentFetcher:
    JINA_READER_BASE = "https://r.jina.ai"
    TIMEOUT_SECONDS = 30

    async def fetch_content(self, url: str) -> httpx.Response:
        jina_url = f"{self.JINA_READER_BASE}/{url}"

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
                response = await client.get(jina_url)
                response.raise_for_status()
                return response
        except httpx.TimeoutException as e:
            raise NetworkError("Request timed out")
        except httpx.HTTPStatusError as e:
            raise NetworkError(f"HTTP {e.response.status_code}")


class WebContentProcessor:
    MAX_CONTENT_LENGTH = 1000000

    def process_response(self, response: httpx.Response) -> str:
        content = response.text

        if not content or not content.strip():
            raise ParsingError("No readable content found on webpage")

        if len(content) > self.MAX_CONTENT_LENGTH:
            content = truncate_text(content, self.MAX_CONTENT_LENGTH)

        return clean_text(content)

    def build_metadata(self, url: str, response: httpx.Response, content: str) -> dict:
        domain = extract_domain(url)
        title = response.headers.get("X-Title", domain)
        description = response.headers.get("X-Description", "")

        return {
            "url": url,
            "domain": domain,
            "title": title,
            "description": description,
            "content_length": len(content),
            "source_type": "web_url"
        }


class WebParser(BaseContentParser):
    def __init__(self):
        self.fetcher = WebContentFetcher()
        self.processor = WebContentProcessor()

    async def parse(self, source: str, **kwargs) -> ContentParseResult:
        start_time = time.time()

        try:
            validate_url(source)
            logger.info("web_parse_started", url=source)

            response = await self.fetcher.fetch_content(source)
            content = self.processor.process_response(response)
            metadata = self.processor.build_metadata(source, response, content)

            processing_time = time.time() - start_time
            logger.info("web_parse_completed", url=source, processing_time=round(processing_time, 2))

            return ContentParseResult(
                content=content,
                title=metadata.get("title"),
                metadata=metadata
            )

        except (ValidationError, NetworkError, ParsingError) as e:
            logger.error("web_parse_failed", error=str(e), url=source)
            return ContentParseResult("", error=str(e))

    def _build_metadata(self, url: str, domain: str, response, content: str) -> dict:
        return self.processor.build_metadata(url, response, content)

    def supports_source(self, source: str) -> bool:
        return supports_web_url(source)

    @property
    def supported_types(self) -> list[str]:
        return ["web_url"]
