"""
Question Generator Service
Generates context-specific questions and explore topics for news articles.
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
class SuggestedQuestion:
    """A suggested question for the article"""
    id: str
    question: str
    category: str
    icon: str


@dataclass
class ExploreTopic:
    """A topic to explore further"""
    topic: str
    description: str
    icon: str
    query: str


@dataclass
class ArticleSuggestions:
    """All suggestions for an article"""
    suggested_questions: List[SuggestedQuestion]
    explore_topics: List[ExploreTopic]


class QuestionGeneratorService:
    """
    Generates context-specific questions and topics based on article content.
    Different article types get different types of questions.
    """

    # Category-specific question templates for fallback
    CATEGORY_QUESTIONS = {
        "judicial": [
            {"question": "What was the main ruling in this case?", "category": "case_law", "icon": "⚖️"},
            {"question": "What legal precedent does this set?", "category": "legal_procedure", "icon": "📜"},
            {"question": "How does this affect similar pending cases?", "category": "legal_impact", "icon": "🔍"},
            {"question": "What were the arguments presented by both sides?", "category": "case_law", "icon": "💬"},
            {"question": "What is the timeline for appeal in this case?", "category": "legal_procedure", "icon": "⏰"},
        ],
        "constitutional": [
            {"question": "Which fundamental right is involved here?", "category": "constitutional", "icon": "📜"},
            {"question": "What is the constitutional basis for this ruling?", "category": "constitutional", "icon": "🏛️"},
            {"question": "How does this interpret the Constitution?", "category": "constitutional", "icon": "📖"},
            {"question": "What are the implications for citizens?", "category": "constitutional", "icon": "👥"},
            {"question": "Are there similar constitutional provisions in other countries?", "category": "comparative_law", "icon": "🌍"},
        ],
        "legislative": [
            {"question": "What are the key provisions of this bill/act?", "category": "legislation", "icon": "📋"},
            {"question": "How does this change existing law?", "category": "legislation", "icon": "🔄"},
            {"question": "When will this come into effect?", "category": "legislation", "icon": "📅"},
            {"question": "Who will be affected by this law?", "category": "legal_impact", "icon": "👥"},
            {"question": "What penalties does this law prescribe?", "category": "legislation", "icon": "⚠️"},
        ],
        "business": [
            {"question": "What are the legal implications for businesses?", "category": "corporate_law", "icon": "🏢"},
            {"question": "How does this affect regulatory compliance?", "category": "compliance", "icon": "📊"},
            {"question": "What due diligence is required?", "category": "corporate_law", "icon": "🔍"},
            {"question": "Are there tax implications?", "category": "tax_law", "icon": "💰"},
            {"question": "How should companies prepare for this?", "category": "compliance", "icon": "📝"},
        ],
        "general": [
            {"question": "What are the key legal points in this news?", "category": "legal_general", "icon": "📌"},
            {"question": "Who are the main parties involved?", "category": "legal_general", "icon": "👥"},
            {"question": "What is the current status of this matter?", "category": "legal_general", "icon": "📊"},
            {"question": "What happens next in this case?", "category": "legal_procedure", "icon": "➡️"},
            {"question": "Are there related laws I should know about?", "category": "legal_general", "icon": "📚"},
        ]
    }

    SYSTEM_PROMPT = """You are a legal education assistant. Generate contextual questions and explore topics for a legal news article.

You MUST return valid JSON with this exact structure:
{
    "suggested_questions": [
        {
            "id": "sq_1",
            "question": "Clear, specific question about the article content",
            "category": "category_name",
            "icon": "emoji"
        }
    ],
    "explore_topics": [
        {
            "topic": "Topic Name",
            "description": "Brief description of what user will learn",
            "icon": "emoji",
            "query": "Search query for RAG system"
        }
    ]
}

Question categories to use:
- legal_procedure: Questions about court processes, timelines, appeals
- constitutional: Questions about fundamental rights, constitutional provisions
- case_law: Questions about judgments, precedents, rulings
- legislation: Questions about acts, bills, amendments
- criminal_law: Questions about IPC, CrPC, criminal matters
- civil_law: Questions about civil procedures, contracts
- corporate_law: Questions about company law, business regulations
- tax_law: Questions about taxation
- legal_impact: Questions about real-world implications
- compliance: Questions about regulatory compliance

Icons to use:
- ⚖️ for court/judicial matters
- 📜 for constitutional matters
- 🏛️ for government/legislative
- 📖 for explanations/definitions
- 💬 for quotes/statements
- 🔍 for investigation/analysis
- 📋 for procedures/processes
- ⏰ for timelines/deadlines
- 💰 for financial/tax matters
- 👥 for people/citizens
- 📚 for learning/education

Guidelines:
1. Generate 5 suggested questions specific to the article content
2. Generate 3 explore topics for deeper learning
3. Questions should be answerable using legal knowledge bases
4. Topics should help users understand broader context
5. Make questions progressively deeper (basic to advanced)

IMPORTANT: Return ONLY valid JSON, no markdown."""

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

    async def generate_suggestions(
        self,
        title: str,
        content: str,
        category: str,
        keywords: List[str] = None
    ) -> ArticleSuggestions:
        """
        Generate suggested questions and explore topics for an article.
        
        Args:
            title: Article title
            content: Article content (or summary)
            category: Article category
            keywords: Optional list of keywords
            
        Returns:
            ArticleSuggestions with questions and topics
        """
        try:
            # Build prompt
            user_prompt = self._build_prompt(title, content, category, keywords)
            
            response = await self.llm_service.generate_with_fallback(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.5,
                max_tokens=2000,
                preferred_provider=LLMProvider.GOOGLE
            )
            
            # Parse response
            data = self._parse_response(response)
            
            # Convert to dataclasses
            questions = [
                SuggestedQuestion(
                    id=q.get("id", f"sq_{i+1}"),
                    question=q.get("question", ""),
                    category=q.get("category", "legal_general"),
                    icon=q.get("icon", "📌")
                )
                for i, q in enumerate(data.get("suggested_questions", []))
                if q.get("question")
            ]
            
            topics = [
                ExploreTopic(
                    topic=t.get("topic", ""),
                    description=t.get("description", ""),
                    icon=t.get("icon", "📚"),
                    query=t.get("query", t.get("topic", ""))
                )
                for t in data.get("explore_topics", [])
                if t.get("topic")
            ]
            
            # Ensure we have at least some suggestions
            if not questions:
                questions = self._get_fallback_questions(category)
            
            if not topics:
                topics = self._get_fallback_topics(title, category, keywords)
            
            return ArticleSuggestions(
                suggested_questions=questions[:5],  # Limit to 5
                explore_topics=topics[:3]  # Limit to 3
            )
            
        except Exception as e:
            logger.error(f"Failed to generate suggestions: {e}")
            return ArticleSuggestions(
                suggested_questions=self._get_fallback_questions(category),
                explore_topics=self._get_fallback_topics(title, category, keywords)
            )

    def _build_prompt(
        self,
        title: str,
        content: str,
        category: str,
        keywords: List[str] = None
    ) -> str:
        """Build the user prompt"""
        # Truncate content
        max_length = 3000
        if len(content) > max_length:
            content = content[:max_length] + "..."
        
        keywords_str = ", ".join(keywords) if keywords else "None"
        
        return f"""Generate questions and explore topics for this legal news article:

TITLE: {title}
CATEGORY: {category}
KEYWORDS: {keywords_str}

CONTENT:
{content}

Generate 5 specific questions users might want answered and 3 topics for deeper exploration."""

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response"""
        try:
            # Clean response
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            return json.loads(cleaned)
            
        except json.JSONDecodeError:
            # Try to extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            return {"suggested_questions": [], "explore_topics": []}

    def _get_fallback_questions(self, category: str) -> List[SuggestedQuestion]:
        """Get fallback questions based on category"""
        category_lower = category.lower()
        
        # Map to known categories
        if "judicial" in category_lower or "court" in category_lower:
            questions = self.CATEGORY_QUESTIONS["judicial"]
        elif "constitutional" in category_lower:
            questions = self.CATEGORY_QUESTIONS["constitutional"]
        elif "legislative" in category_lower or "bill" in category_lower:
            questions = self.CATEGORY_QUESTIONS["legislative"]
        elif "business" in category_lower or "corporate" in category_lower:
            questions = self.CATEGORY_QUESTIONS["business"]
        else:
            questions = self.CATEGORY_QUESTIONS["general"]
        
        return [
            SuggestedQuestion(
                id=f"sq_{i+1}",
                question=q["question"],
                category=q["category"],
                icon=q["icon"]
            )
            for i, q in enumerate(questions[:5])
        ]

    def _get_fallback_topics(
        self,
        title: str,
        category: str,
        keywords: List[str] = None
    ) -> List[ExploreTopic]:
        """Generate fallback explore topics"""
        topics = []
        
        # Topic based on category
        category_topics = {
            "judicial": ExploreTopic(
                topic="Indian Judicial System",
                description="Learn about court hierarchy and procedures",
                icon="🏛️",
                query="Indian judicial system court hierarchy"
            ),
            "constitutional": ExploreTopic(
                topic="Fundamental Rights",
                description="Understanding constitutional rights in India",
                icon="📜",
                query="fundamental rights India constitution"
            ),
            "legislative": ExploreTopic(
                topic="Law Making Process",
                description="How bills become laws in India",
                icon="📋",
                query="legislative process India parliament"
            ),
            "business": ExploreTopic(
                topic="Corporate Law Basics",
                description="Key corporate regulations in India",
                icon="🏢",
                query="corporate law India Companies Act"
            ),
        }
        
        category_lower = category.lower()
        for key, topic in category_topics.items():
            if key in category_lower:
                topics.append(topic)
                break
        
        # Add generic legal topics
        topics.append(ExploreTopic(
            topic="Legal Terminology",
            description="Common legal terms and their meanings",
            icon="📖",
            query="legal terminology India law dictionary"
        ))
        
        # Add topic from title keywords
        title_words = title.split()[:3]
        if title_words:
            topics.append(ExploreTopic(
                topic=f"More on: {' '.join(title_words)}",
                description="Related legal developments",
                icon="🔍",
                query=f"{' '.join(title_words)} India law"
            ))
        
        return topics[:3]
