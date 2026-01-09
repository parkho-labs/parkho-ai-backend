"""
AI Content Formatter Service
Transforms raw news content into structured, formatted content for rich frontend display.
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ...config import get_settings
from ...services.llm_service import LLMService, LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class FormattedArticle:
    """Result of content formatting"""
    quick_summary: str
    key_points: List[str]
    formatted_content: List[Dict[str, Any]]  # List of content sections
    reading_time_minutes: int
    word_count: int
    court_name: Optional[str] = None
    bench_info: Optional[str] = None


class ContentFormatterService:
    """
    AI-powered content formatter that transforms raw news articles
    into structured content sections for rich frontend rendering.
    """

    SYSTEM_PROMPT = """You are a legal news content formatter. Your job is to transform raw legal news articles into well-structured, readable content.

You MUST return valid JSON with this exact structure:
{
    "quick_summary": "2-3 sentence summary of the article",
    "key_points": ["Point 1", "Point 2", "Point 3", "Point 4", "Point 5"],
    "court_name": "Name of court if mentioned, null otherwise",
    "bench_info": "Names of judges/bench if mentioned, null otherwise",
    "sections": [
        {"type": "paragraph", "text": "Opening paragraph..."},
        {"type": "heading", "level": 2, "text": "Section heading"},
        {"type": "paragraph", "text": "Content paragraph..."},
        {"type": "quote", "text": "Important quote from judgment or person", "attribution": "Name of person or court"},
        {"type": "list", "style": "bullet", "items": ["Item 1", "Item 2"]},
        {"type": "case_citation", "case_name": "Case Name", "citation": "Citation number", "court": "Court name"},
        {"type": "highlight", "text": "Important information to highlight"}
    ]
}

Section types you can use:
- "paragraph": Regular text content
- "heading": Section headers (level 2 or 3)
- "quote": Direct quotes with attribution
- "list": Bullet or numbered lists
- "case_citation": Legal case citations
- "highlight": Important information to emphasize

Guidelines:
1. Keep quick_summary to 2-3 sentences maximum
2. Extract 3-5 key points as bullet points
3. Identify court names (Supreme Court, High Courts, etc.)
4. Extract bench/judge information when available
5. Structure content logically with headings and paragraphs
6. Highlight important quotes from judges or key statements
7. Extract and format case citations properly
8. Make content scannable and easy to read

IMPORTANT: Return ONLY valid JSON, no markdown formatting around it."""

    def __init__(self):
        settings = get_settings()
        self.llm_service = LLMService(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key,
            openai_model_name=settings.openai_model_name,
            anthropic_model_name=settings.anthropic_model_name,
            google_model_name=settings.google_model_name
        )

    async def format_article(
        self,
        title: str,
        content: str,
        source: str,
        category: str
    ) -> FormattedArticle:
        """
        Format a raw news article into structured content.
        
        Args:
            title: Article title
            content: Raw article content
            source: News source name
            category: Article category
            
        Returns:
            FormattedArticle with structured content
        """
        # Calculate basic metrics
        word_count = len(content.split())
        reading_time = max(1, word_count // 200)  # ~200 words per minute
        
        # If content is too short, return basic formatting
        if word_count < 50:
            return self._create_basic_formatted_article(title, content, word_count, reading_time)
        
        try:
            # Generate formatted content using LLM
            user_prompt = self._build_user_prompt(title, content, source, category)
            
            response = await self.llm_service.generate_with_fallback(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.3,  # Lower temperature for consistent formatting
                max_tokens=4000,
                preferred_provider=LLMProvider.GOOGLE  # Use Gemini for speed
            )
            
            # Parse the JSON response
            formatted_data = self._parse_response(response)
            
            return FormattedArticle(
                quick_summary=formatted_data.get("quick_summary", title),
                key_points=formatted_data.get("key_points", []),
                formatted_content=formatted_data.get("sections", []),
                reading_time_minutes=reading_time,
                word_count=word_count,
                court_name=formatted_data.get("court_name"),
                bench_info=formatted_data.get("bench_info")
            )
            
        except Exception as e:
            logger.error(f"Failed to format article: {e}")
            return self._create_basic_formatted_article(title, content, word_count, reading_time)

    def _build_user_prompt(self, title: str, content: str, source: str, category: str) -> str:
        """Build the user prompt for content formatting"""
        # Truncate very long content to avoid token limits
        max_content_length = 8000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."
        
        return f"""Format this legal news article:

TITLE: {title}
SOURCE: {source}
CATEGORY: {category}

CONTENT:
{content}

Transform this into structured JSON with quick_summary, key_points, court_name (if applicable), bench_info (if applicable), and sections array."""

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM response into structured data with robust error handling"""
        try:
            # Clean up the response - remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            return json.loads(cleaned)
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            
            # Try to repair common JSON issues
            repaired = self._repair_json(cleaned if 'cleaned' in dir() else response)
            if repaired:
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    pass
            
            # Try to extract JSON from the response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    # Try repair on extracted JSON
                    repaired = self._repair_json(json_match.group())
                    if repaired:
                        try:
                            return json.loads(repaired)
                        except json.JSONDecodeError:
                            pass
            
            # Return empty structure if parsing fails
            return {
                "quick_summary": "",
                "key_points": [],
                "sections": [],
                "court_name": None,
                "bench_info": None
            }
    
    def _repair_json(self, json_str: str) -> Optional[str]:
        """
        Attempt to repair common JSON issues from LLM outputs:
        - Unterminated strings
        - Missing closing brackets
        - Trailing commas
        """
        if not json_str:
            return None
            
        try:
            repaired = json_str.strip()
            
            # Fix unterminated strings by finding the last valid position
            # Count open/close braces and brackets
            brace_count = 0
            bracket_count = 0
            in_string = False
            escape_next = False
            last_valid_pos = 0
            
            for i, char in enumerate(repaired):
                if escape_next:
                    escape_next = False
                    continue
                    
                if char == '\\':
                    escape_next = True
                    continue
                    
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                    
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count >= 0:
                            last_valid_pos = i
                    elif char == '[':
                        bracket_count += 1
                    elif char == ']':
                        bracket_count -= 1
                        if bracket_count >= 0:
                            last_valid_pos = i
            
            # If we're stuck in a string, try to close it
            if in_string:
                # Find the last complete line and truncate there
                lines = repaired.split('\n')
                for i in range(len(lines) - 1, -1, -1):
                    test_str = '\n'.join(lines[:i+1])
                    # Try to close any open structures
                    test_str = test_str.rstrip().rstrip(',')
                    
                    # Close any unclosed strings
                    quote_count = test_str.count('"') - test_str.count('\\"')
                    if quote_count % 2 == 1:
                        test_str += '"'
                    
                    # Add closing brackets/braces as needed
                    open_brackets = test_str.count('[') - test_str.count(']')
                    open_braces = test_str.count('{') - test_str.count('}')
                    
                    test_str = test_str.rstrip().rstrip(',')
                    test_str += ']' * open_brackets
                    test_str += '}' * open_braces
                    
                    try:
                        json.loads(test_str)
                        return test_str
                    except json.JSONDecodeError:
                        continue
            
            # Remove trailing commas before closing brackets
            repaired = re.sub(r',(\s*[\]}])', r'\1', repaired)
            
            # Balance brackets and braces
            open_brackets = repaired.count('[') - repaired.count(']')
            open_braces = repaired.count('{') - repaired.count('}')
            
            # Remove trailing comma if present
            repaired = repaired.rstrip().rstrip(',')
            
            # Add missing closing brackets/braces
            repaired += ']' * max(0, open_brackets)
            repaired += '}' * max(0, open_braces)
            
            return repaired
            
        except Exception as e:
            logger.debug(f"JSON repair failed: {e}")
            return None

    def _create_basic_formatted_article(
        self,
        title: str,
        content: str,
        word_count: int,
        reading_time: int
    ) -> FormattedArticle:
        """Create basic formatted article without AI processing"""
        # Split content into paragraphs
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        sections = []
        for para in paragraphs:
            if para:
                sections.append({
                    "type": "paragraph",
                    "text": para
                })
        
        # Create basic summary from first paragraph
        first_para = paragraphs[0] if paragraphs else content[:200]
        quick_summary = first_para[:300] + "..." if len(first_para) > 300 else first_para
        
        return FormattedArticle(
            quick_summary=quick_summary,
            key_points=[],
            formatted_content=sections,
            reading_time_minutes=reading_time,
            word_count=word_count,
            court_name=None,
            bench_info=None
        )

    def extract_court_info(self, content: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extract court name and bench information from content.
        This is a fallback when AI extraction fails.
        """
        court_name = None
        bench_info = None
        
        content_lower = content.lower()
        
        # Court name patterns
        court_patterns = [
            (r'supreme court of india', 'Supreme Court of India'),
            (r'supreme court', 'Supreme Court'),
            (r'delhi high court', 'Delhi High Court'),
            (r'bombay high court', 'Bombay High Court'),
            (r'madras high court', 'Madras High Court'),
            (r'calcutta high court', 'Calcutta High Court'),
            (r'karnataka high court', 'Karnataka High Court'),
            (r'allahabad high court', 'Allahabad High Court'),
            (r'punjab and haryana high court', 'Punjab and Haryana High Court'),
            (r'national green tribunal', 'National Green Tribunal'),
            (r'national company law tribunal', 'National Company Law Tribunal'),
        ]
        
        for pattern, name in court_patterns:
            if re.search(pattern, content_lower):
                court_name = name
                break
        
        # Try to extract judge names
        judge_pattern = r'(justice\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        judges = re.findall(judge_pattern, content, re.IGNORECASE)
        if judges:
            unique_judges = list(dict.fromkeys(judges))[:3]  # Limit to 3 judges
            bench_info = ', '.join(unique_judges)
        
        return court_name, bench_info
