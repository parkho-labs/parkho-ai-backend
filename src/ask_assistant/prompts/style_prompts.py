"""Response style prompts for Ask Assistant"""

from ..models.enums import ResponseStyle

STYLE_PROMPTS = {
    ResponseStyle.CONCISE: """## Response Style: CONCISE

Keep your response **brief and focused**:
- Maximum 2-3 short paragraphs
- Use bullet points for multiple items
- No unnecessary elaboration
- Get straight to the point
- Only include essential information
- Skip lengthy introductions and conclusions""",

    ResponseStyle.DETAILED: """## Response Style: DETAILED

Provide a **comprehensive response**:
- Include relevant background and context
- Explain concepts thoroughly
- Cite specific provisions, articles, and cases
- Discuss nuances and exceptions
- Cover multiple aspects of the question
- Use examples to illustrate points
- Include practical implications""",

    ResponseStyle.LEARNING: """## Response Style: LEARNING (Educational)

Teach the concept **step-by-step** like a tutor:
- Start with the basics before going deeper
- Build understanding progressively
- Use analogies and real-world examples
- Define all technical terms when introduced
- Include "why" explanations, not just "what"
- Summarize key points at the end
- Use headers to organize the explanation
- Make it easy to follow for someone learning""",

    ResponseStyle.PROFESSIONAL: """## Response Style: PROFESSIONAL (Technical)

Use **precise legal language**:
- Proper legal terminology throughout
- Cite provisions with full references (Article X, Section Y)
- Include case citations in proper format
- Reference legal doctrines and principles by name
- Assume familiarity with legal concepts
- Focus on technical accuracy
- Include statutory interpretation where relevant"""
}


def get_style_prompt(style: ResponseStyle) -> str:
    """Get the style instruction for a specific response style"""
    return STYLE_PROMPTS.get(style, STYLE_PROMPTS[ResponseStyle.DETAILED])


# Style metadata for API responses
STYLE_METADATA = {
    ResponseStyle.CONCISE: {
        "id": "concise",
        "name": "Concise",
        "description": "Brief, to-the-point responses (2-3 paragraphs)"
    },
    ResponseStyle.DETAILED: {
        "id": "detailed",
        "name": "Detailed", 
        "description": "Comprehensive answers with context and examples"
    },
    ResponseStyle.LEARNING: {
        "id": "learning",
        "name": "Learning",
        "description": "Educational, step-by-step explanations for students"
    },
    ResponseStyle.PROFESSIONAL: {
        "id": "professional",
        "name": "Professional",
        "description": "Technical legal language with full citations"
    }
}


# Output format instructions (common to all)
OUTPUT_FORMAT = """
## Output Format
- Use **Markdown** formatting for better readability
- Use **bold** for key terms and important points
- Use bullet points or numbered lists for multiple items
- Use `code formatting` for Article numbers, Section numbers (e.g., `Article 21`, `Section 302 BNS`)
- Use > blockquotes for important legal provisions or case excerpts
- Use ### headings to organize longer responses
- Keep paragraphs concise and well-spaced
"""
