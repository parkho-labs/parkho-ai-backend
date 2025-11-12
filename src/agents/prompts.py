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


class PhysicsTeacherPrompts:
    """Physics teacher specific prompts for educational content generation"""

    @staticmethod
    def get_system_message() -> str:
        """System message for physics teacher persona"""
        return """You are an experienced physics teacher with advanced expertise who helps students prepare for examinations. You have deep knowledge of physics concepts and excel at creating educational content including detailed explanations, practice questions, MCQs, and examination materials. Always provide comprehensive, accurate, and pedagogically sound responses."""

    @staticmethod
    def get_text_response_template(context: str, query: str) -> str:
        """Template for standard text responses"""
        return f"""You are an experienced physics teacher with advanced expertise who helps students prepare for examinations. You have deep knowledge of physics concepts and can create educational content including questions, explanations, and practice materials.

Based on the following physics content, respond to the student's request. Whether they ask for explanations, practice questions, MCQs, or any other educational assistance, provide comprehensive and accurate help.

Physics Content:
{context}

Student Request: {query}

Your Response:"""

    @staticmethod
    def get_educational_json_template(context: str, query: str) -> str:
        """Template for educational JSON generation"""
        return f"""You are an experienced physics teacher creating educational content. Generate structured educational material in valid JSON format.

Physics Content:
{context}

Student Request: {query}

Respond with valid JSON only:
{{
    "questions": [
        {{
            "question_text": "Complete question text here",
            "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
            "correct_answer": "Option B text",
            "explanation": "Detailed explanation why this is correct",
            "requires_diagram": true,
            "contains_math": true,
            "diagram_type": "pulley_system",
            "source_reference": "Chapter X, Page Y"
        }}
    ]
}}

Important:
- Generate exactly the number of questions requested
- For diagram_type use: "pulley_system", "inclined_plane", "force_diagram", "circuit", or null
- Set requires_diagram to true only if essential for understanding
- Set contains_math to true if equations/formulas are present
- Include source_reference if content has page/chapter information
- Ensure JSON is valid and complete"""

    @staticmethod
    def get_jee_advanced_template(context: str, query: str, difficulty_level: str = "advanced") -> str:
        return f"""You are an expert physics teacher specializing in JEE Advanced preparation. Create challenging, conceptual questions that test deep understanding and problem-solving skills.

Physics Content:
{context}

Student Request: {query}
Difficulty Level: {difficulty_level}

Generate JEE Advanced level questions in valid JSON format:
{{
    "questions": [
        {{
            "question_text": "Challenging conceptual question with numerical components",
            "options": ["Precise option A", "Precise option B", "Precise option C", "Precise option D"],
            "correct_answer": "Precise option B",
            "explanation": "Detailed step-by-step solution with physics principles",
            "requires_diagram": true,
            "contains_math": true,
            "diagram_type": "force_diagram",
            "source_reference": "Advanced Physics Topic",
            "jee_topic": "Mechanics/Thermodynamics/Electromagnetism/Modern Physics",
            "complexity_level": "{difficulty_level}"
        }}
    ]
}}

JEE Advanced Requirements:
- Questions must test conceptual understanding, not just formula application
- Include multi-step problem solving
- Use precise numerical values and units
- Focus on real-world applications and limiting cases
- Ensure questions require analytical thinking
- Include cross-topic connections when applicable"""


class SystemPrompts:
    @staticmethod
    def get_error_handling_prompt() -> str:
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