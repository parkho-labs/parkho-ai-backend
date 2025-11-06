class ContentAnalysisPrompts:
    @staticmethod
    def get_analysis_prompt() -> str:
        """Prompt for analyzing video/content transcript"""
        return """Analyze the following video transcript and return a JSON object with:

1. main_topic: The primary subject or theme (max 50 chars)
2. key_topics: Array of 3-5 important topics covered
3. complexity_level: "beginner", "intermediate", or "advanced"
4. estimated_reading_time: Time in minutes to read the content
5. content_type: "educational", "tutorial", "discussion", "presentation"
6. target_audience: Brief description of intended audience

Return valid JSON only, no additional text."""

    @staticmethod
    def get_key_concepts_prompt() -> str:
        """Prompt for extracting key concepts from content"""
        return """Extract key concepts from the transcript and return a JSON array where each concept has:

1. concept: The concept name (2-4 words)
2. definition: Brief explanation (max 100 chars)
3. importance: "high", "medium", "low"
4. category: "technical", "theoretical", "practical", "fundamental"

Extract 5-8 key concepts. Return valid JSON array only."""

    @staticmethod
    def get_summary_prompt() -> str:
        """Prompt for creating comprehensive summaries"""
        return """Create a comprehensive summary of the video content with:

1. A clear, engaging title
2. Main points organized in logical sections
3. Key takeaways or conclusions
4. Any important examples or case studies mentioned

Write in markdown format with clear headings. Make it informative yet concise."""


class QuestionGenerationPrompts:
    """Prompts for question generation operations"""

    @staticmethod
    def get_multiple_choice_prompt(num_questions: int, difficulty_level: str) -> str:
        """Prompt for generating multiple choice questions"""
        return f"""Generate {num_questions} multiple-choice questions based on the content. Each question should be {difficulty_level} level and have:

- question: the question text
- answer_config: object with options array, correct_answer, and reason
- context: relevant excerpt from content
- max_score: 1

Requirements:
- Options should be plausible but only one correct
- Avoid "all of the above" or "none of the above" options
- Include brief explanation for correct answer
- Focus on understanding, not memorization

Return valid JSON array only."""

    @staticmethod
    def get_true_false_prompt(num_questions: int, difficulty_level: str) -> str:
        """Prompt for generating true/false questions"""
        return f"""Generate {num_questions} true/false questions based on the content. Each question should be {difficulty_level} level and have:

- question: the statement to evaluate
- answer_config: object with correct_answer (true/false) and reason
- context: relevant excerpt from content
- max_score: 1

Requirements:
- Statements should be clear and unambiguous
- Avoid trick questions or overly obvious answers
- Include brief explanation for the correct answer
- Test understanding of key concepts

Return valid JSON array only."""

    @staticmethod
    def get_short_answer_prompt(num_questions: int, difficulty_level: str) -> str:
        """Prompt for generating short answer questions"""
        return f"""Generate {num_questions} short-answer questions based on the content. Each question should be {difficulty_level} level and have:

- question: the question requiring 2-3 sentence answer
- answer_config: object with sample_answer and key_points array
- context: relevant excerpt from content
- max_score: 3

Requirements:
- Questions should require explanation, not just recall
- Answers should be 2-3 sentences maximum
- Include key points that good answers should cover
- Focus on application and understanding

Return valid JSON array only."""

    @staticmethod
    def get_essay_prompt(num_questions: int, difficulty_level: str) -> str:
        """Prompt for generating essay questions"""
        return f"""Generate {num_questions} long-form essay questions based on the content. Each question should be {difficulty_level} level and have:

- question: the essay prompt requiring detailed analysis
- answer_config: object with sample_outline and evaluation_criteria array
- context: relevant excerpt from content
- max_score: 10

Requirements:
- Questions should require critical thinking and synthesis
- Include suggested structure/outline for answers
- Provide clear evaluation criteria
- Encourage deeper analysis of concepts

Return valid JSON array only."""


class ValidationPrompts:
    """Prompts for validation and quality checking"""

    @staticmethod
    def get_content_validation_prompt() -> str:
        """Prompt for validating content quality"""
        return """Evaluate the content quality and return a JSON object with:

1. readability_score: 1-10 (10 = very clear)
2. completeness_score: 1-10 (10 = comprehensive)
3. accuracy_concerns: Array of potential issues
4. improvement_suggestions: Array of recommendations
5. overall_rating: 1-10

Focus on educational value and clarity."""

    @staticmethod
    def get_question_validation_prompt() -> str:
        """Prompt for validating generated questions"""
        return """Review the generated questions and return a JSON object with:

1. clarity_score: 1-10 (10 = very clear)
2. difficulty_appropriate: true/false
3. coverage_score: 1-10 (10 = comprehensive coverage)
4. problematic_questions: Array of question IDs with issues
5. improvement_suggestions: Array of recommendations

Ensure questions test understanding, not just memorization."""


class SystemPrompts:
    """System-wide prompts and templates"""

    @staticmethod
    def get_error_handling_prompt() -> str:
        """Prompt for handling content processing errors"""
        return """An error occurred during content processing. Analyze the issue and provide:

1. error_type: Classification of the error
2. user_message: Clear, non-technical explanation for users
3. suggested_action: What the user should try next
4. severity: "low", "medium", "high"

Be helpful and reassuring in your response."""

    @staticmethod
    def get_feedback_analysis_prompt() -> str:
        """Prompt for analyzing user feedback"""
        return """Analyze the user feedback and return insights:

1. sentiment: "positive", "negative", "neutral"
2. main_concerns: Array of key issues raised
3. feature_requests: Array of requested features
4. priority_level: "low", "medium", "high"
5. response_suggestions: Recommended response approach

Focus on actionable insights for product improvement."""