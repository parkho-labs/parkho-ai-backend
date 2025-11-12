import requests
from typing import Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time

from .base_parser import BaseContentParser, ContentParseResult


#REVISIT - Feels complicatied, should we make it a vector embedding for rag in default collection.. instead of parsing, query result would be much better I think
# Same for youtube video, docx and others. 
class WebParser(BaseContentParser):
    def __init__(self):
        self.timeout = 30  
        self.max_content_length = 1000000  # 1MB text limit
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    async def parse(self, source: str, **kwargs) -> ContentParseResult:
        try:
            parsed_url = urlparse(source)
            if not parsed_url.scheme or not parsed_url.netloc:
                return ContentParseResult("", error=f"Invalid URL: {source}")

            try:
                response = requests.get(
                    source,
                    headers=self.headers,
                    timeout=self.timeout,
                    allow_redirects=True
                )
                response.raise_for_status()
            except requests.exceptions.Timeout:
                return ContentParseResult("", error="Request timed out")
            except requests.exceptions.RequestException as e:
                return ContentParseResult("", error=f"Failed to fetch URL: {str(e)}")

            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type:
                return ContentParseResult("", error=f"Unsupported content type: {content_type}")

            soup = BeautifulSoup(response.content, "html.parser")

            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()

            title = soup.title.string.strip() if soup.title else parsed_url.netloc
            content = self._extract_main_content(soup)

            if len(content) > self.max_content_length:
                content = content[:self.max_content_length] + "... [Content truncated]"

            if not content.strip():
                return ContentParseResult("", error="No readable content found on webpage")

            metadata = self._extract_metadata(soup, response, source)

            return ContentParseResult(
                content=content.strip(),
                title=title,
                metadata=metadata
            )

        except Exception as e:
            return ContentParseResult("", error=f"Failed to parse web content: {str(e)}")

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        content_parts = []

        main_selectors = [
            "main",
            "article",
            ".content",
            ".main-content",
            "#content",
            "#main",
            ".post-content",
            ".entry-content"
        ]

        main_content = None
        for selector in main_selectors:
            elements = soup.select(selector)
            if elements:
                main_content = elements[0]
                break

        if main_content is None:
            main_content = soup.body or soup

        for element in main_content.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "div"]):
            text = element.get_text(strip=True)
            if text and len(text) > 20:  # Filter out very short text
                content_parts.append(text)

        return "\n\n".join(content_parts)

    def _extract_metadata(self, soup: BeautifulSoup, response: requests.Response, url: str) -> Dict[str, Any]:
        metadata = {
            "url": url,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "content_length": len(response.content),
        }

        description = soup.find("meta", attrs={"name": "description"})
        if description:
            metadata["description"] = description.get("content", "")

        author = soup.find("meta", attrs={"name": "author"})
        if author:
            metadata["author"] = author.get("content", "")

        keywords = soup.find("meta", attrs={"name": "keywords"})
        if keywords:
            metadata["keywords"] = keywords.get("content", "")

        og_title = soup.find("meta", property="og:title")
        if og_title:
            metadata["og_title"] = og_title.get("content", "")

        og_description = soup.find("meta", property="og:description")
        if og_description:
            metadata["og_description"] = og_description.get("content", "")

        metadata["domain"] = urlparse(url).netloc
        metadata["extraction_time"] = time.time()

        return metadata

    def supports_source(self, source: str) -> bool:
        try:
            parsed = urlparse(source)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False

    @property
    def supported_types(self) -> list[str]:
        return ["web_url"]