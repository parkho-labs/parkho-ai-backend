"""
Intent Classifier Service for Ask Knowlx

Classifies user intent based on question analysis and builds adaptive prompts
to tailor responses based on expertise level and question type.

Uses single-call approach - classification instructions embedded in system prompt.
"""

import structlog
from typing import Optional
from enum import Enum

logger = structlog.get_logger(__name__)


class ExpertiseLevel(str, Enum):
    """User expertise levels for response adaptation"""
    LAYMAN = "layman"
    STUDENT = "student"
    PROFESSIONAL = "professional"


class QuestionType(str, Enum):
    """Types of legal questions"""
    CONCEPTUAL = "conceptual"
    PROCEDURAL = "procedural"
    CASE_BASED = "case_based"
    COMPARISON = "comparison"
    PRACTICAL = "practical"


class IntentClassifier:
    """
    Classifies user intent and builds adaptive prompts for the Ask Knowlx feature.
    
    Uses single-call approach where classification instructions are embedded
    in the system prompt, allowing the LLM to self-assess and adapt its response.
    """
    
    # Response style guidance for each expertise level
    EXPERTISE_GUIDANCE = {
        ExpertiseLevel.LAYMAN: (
            "For LAYMAN users:\n"
            "- Explain in simple, everyday language\n"
            "- Avoid legal jargon or define it when necessary\n"
            "- Use analogies and examples from daily life\n"
            "- Focus on practical implications and what it means for them\n"
            "- Keep sentences short and clear"
        ),
        ExpertiseLevel.STUDENT: (
            "For STUDENT users:\n"
            "- Use proper legal terminology but explain concepts clearly\n"
            "- Include relevant case references and article numbers\n"
            "- Provide context about legal principles and their evolution\n"
            "- Structure the response for academic understanding\n"
            "- Mention landmark judgments and their significance"
        ),
        ExpertiseLevel.PROFESSIONAL: (
            "For PROFESSIONAL users:\n"
            "- Use precise legal language and technical terminology\n"
            "- Cite specific provisions, sections, and landmark judgments with citations\n"
            "- Be concise and technical - they understand the basics\n"
            "- Include nuances, exceptions, and recent developments\n"
            "- Reference relevant legal principles and doctrines"
        )
    }
    
    # Guidance for different question types
    QUESTION_TYPE_GUIDANCE = {
        QuestionType.CONCEPTUAL: (
            "This is a CONCEPTUAL question. Focus on:\n"
            "- Explaining the concept, its definition, and meaning\n"
            "- Its origin and constitutional/legal significance\n"
            "- Key principles and underlying philosophy"
        ),
        QuestionType.PROCEDURAL: (
            "This is a PROCEDURAL question. Focus on:\n"
            "- Providing step-by-step guidance\n"
            "- Mentioning timelines, requirements, and prerequisites\n"
            "- Relevant authorities, courts, or bodies involved\n"
            "- Common pitfalls or important considerations"
        ),
        QuestionType.CASE_BASED: (
            "This is a CASE-BASED question. Focus on:\n"
            "- The case facts and legal issues involved\n"
            "- The court's reasoning and judgment\n"
            "- Legal principles established or affirmed\n"
            "- Implications and subsequent developments"
        ),
        QuestionType.COMPARISON: (
            "This is a COMPARISON question. Focus on:\n"
            "- Creating a structured comparison\n"
            "- Highlighting key differences and similarities\n"
            "- When each applies or is relevant\n"
            "- Practical implications of the differences"
        ),
        QuestionType.PRACTICAL: (
            "This is a PRACTICAL/SITUATIONAL question. Focus on:\n"
            "- Understanding their specific situation\n"
            "- Actionable advice and remedies available\n"
            "- Next steps they can take\n"
            "- When to seek professional legal help"
        )
    }
    
    # The main adaptive system prompt template
    ADAPTIVE_SYSTEM_PROMPT = """You are Knowlx, an expert legal assistant specializing in Indian law, including Constitutional Law and the Bharatiya Nyaya Sanhita (BNS).

INTERNALLY assess the user's expertise level and question type, then respond accordingly. NEVER reveal your assessment in the response.

## INTERNAL ASSESSMENT (keep this completely hidden from user):

**Expertise Levels:**
- LAYMAN: Simple language, basic questions, non-legal terms, seeking practical guidance
- STUDENT: Some legal terminology, asks about concepts/articles/cases, seeks academic understanding  
- PROFESSIONAL: Precise legal terminology, technical questions, references provisions/judgments

**Question Types:**
- Conceptual: "What is...", "Explain...", "Define..."
- Procedural: "How to...", "Process for...", "Steps to..."
- Case-based: Questions about specific judgments or precedents
- Comparison: "Difference between...", "Compare..."
- Practical: Situational questions seeking advice

## RESPONSE STYLE (apply silently based on your assessment):

{expertise_guidance}

{question_type_guidance}

## CRITICAL RULES:
1. NEVER say things like "As a layman...", "Based on your expertise level...", "This appears to be a student-level question..."
2. NEVER mention your assessment process or reasoning about user level
3. Just answer the question directly in the appropriate style
4. Cite relevant Articles, Sections, or landmark cases when applicable
5. For practical questions involving legal action, recommend consulting a lawyer

## OUTPUT FORMAT:
- Use **Markdown** formatting for better readability
- Use **bold** for key terms and important points
- Use bullet points or numbered lists for multiple items
- Use `code formatting` for Article numbers, Section numbers (e.g., `Article 21`, `Section 302 BNS`)
- Use > blockquotes for important legal provisions or case excerpts
- Use ### headings to organize longer responses
- Keep paragraphs concise and well-spaced

Respond directly to the question now."""

    def __init__(self):
        """Initialize the IntentClassifier."""
        logger.info("IntentClassifier initialized")
    
    def build_adaptive_prompt(
        self,
        question: str,
        hint_expertise: Optional[ExpertiseLevel] = None,
        hint_question_type: Optional[QuestionType] = None
    ) -> str:
        """
        Builds an adaptive system prompt that instructs the LLM to assess
        the user's expertise level and question type, then respond appropriately.
        
        Args:
            question: The user's question (used for logging/analysis)
            hint_expertise: Optional hint about user expertise (from user profile, etc.)
            hint_question_type: Optional hint about question type
            
        Returns:
            The complete system prompt with adaptive instructions
        """
        # Build expertise guidance section
        expertise_guidance = "\n\n".join([
            self.EXPERTISE_GUIDANCE[level] 
            for level in ExpertiseLevel
        ])
        
        # Build question type guidance section
        question_type_guidance = "\n\n".join([
            self.QUESTION_TYPE_GUIDANCE[qtype]
            for qtype in QuestionType
        ])
        
        # If hints are provided, add them to the prompt
        hint_section = ""
        if hint_expertise:
            hint_section += f"\n\n**HINT**: The user appears to be at {hint_expertise.value.upper()} level."
        if hint_question_type:
            hint_section += f"\n**HINT**: This appears to be a {hint_question_type.value.upper()} question."
        
        # Format the complete prompt
        prompt = self.ADAPTIVE_SYSTEM_PROMPT.format(
            expertise_guidance=expertise_guidance,
            question_type_guidance=question_type_guidance
        )
        
        if hint_section:
            prompt += hint_section
        
        logger.debug(
            "Built adaptive prompt",
            question_length=len(question),
            hint_expertise=hint_expertise.value if hint_expertise else None,
            hint_question_type=hint_question_type.value if hint_question_type else None
        )
        
        return prompt
    
    def get_simple_prompt(self, expertise_level: ExpertiseLevel) -> str:
        """
        Returns a simpler, non-adaptive prompt for a specific expertise level.
        Useful when expertise is already known (e.g., from user settings).
        
        Args:
            expertise_level: The known expertise level of the user
            
        Returns:
            A system prompt tailored to that expertise level
        """
        base_prompt = """You are Knowlx, an expert legal assistant specializing in Indian law, including Constitutional Law and the Bharatiya Nyaya Sanhita (BNS).

{expertise_guidance}

Always cite relevant Articles, Sections, or landmark cases when applicable.
If you're unsure about something, acknowledge the limitation.
For practical questions involving potential legal action, recommend consulting a lawyer."""
        
        return base_prompt.format(
            expertise_guidance=self.EXPERTISE_GUIDANCE[expertise_level]
        )


# Singleton instance for dependency injection
_classifier_instance: Optional[IntentClassifier] = None


def get_intent_classifier() -> IntentClassifier:
    """Get or create the IntentClassifier singleton instance."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier()
    return _classifier_instance
