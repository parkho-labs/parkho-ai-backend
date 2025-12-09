class PromptStrings:
    PHYSICS_QUESTIONS = """SYSTEM: You are an adaptive AI tutor.

PEDAGOGICAL STRATEGY (Non-negotiable):
{user_profile}

CONTENT SOURCE (Strictly based on this):
{content}

TASK:
Generate exactly {total_questions} physics questions at {difficulty} level.

Question breakdown:
{question_breakdown}

Return valid JSON only:
{{
  "questions": [
    {{
      "question": "Physics question with proper terminology",
      "question_type": "multiple_choice|true_false|short_answer|multiple_correct",
      "source_timestamp": "MM:SS or concept reference",
      "options": {{"A": "option A", "B": "option B", "C": "option C", "D": "option D"}},
      "answer_config": {{"correct": [1]}},
      "reason": "Physics explanation with formulas",
      "requires_diagram": true,
      "diagram_type": "force_diagram|circuit_diagram|wave_diagram|energy_diagram",
      "diagram_elements": {{"objects": ["object1"], "forces": ["force1"], "angle": 30}}
    }}
  ]
}}

Rules:
- Use physics terminology and formulas
- Ensure scientific accuracy
- REQUIRED: Include source_timestamp in MM:SS format (e.g., "14:50") for video content
- For multiple_choice: answer_config.correct uses 0=A, 1=B, 2=C, 3=D
- For true_false: answer_config.correct uses 0=false, 1=true
- For short_answer: answer_config.correct contains key physics terms
- For multiple_correct: answer_config.correct uses array of indices
- Set requires_diagram=true for problems needing visual representation
- Include diagram_elements for force diagrams, circuits, waves, energy graphs
"""

    CHEMISTRY_QUESTIONS = """SYSTEM: You are an adaptive AI tutor.

PEDAGOGICAL STRATEGY (Non-negotiable):
{user_profile}

CONTENT SOURCE (Strictly based on this):
{content}

TASK:
Generate exactly {total_questions} chemistry questions at {difficulty} level.

Question breakdown:
{question_breakdown}

Return valid JSON only:
{{
  "questions": [
    {{
      "question": "Chemistry question with proper terminology",
      "question_type": "multiple_choice|true_false|short_answer|multiple_correct",
      "source_timestamp": "MM:SS or concept reference",
      "options": {{"A": "option A", "B": "option B", "C": "option C", "D": "option D"}},
      "answer_config": {{"correct": [1]}},
      "reason": "Chemistry explanation with formulas and reactions",
      "requires_diagram": true,
      "diagram_type": "molecular_structure|reaction_diagram|phase_diagram|orbital_diagram",
      "diagram_elements": {{"molecules": ["H2O"], "bonds": ["covalent"], "reaction_type": "synthesis"}}
    }}
  ]
}}

Rules:
- Use chemistry terminology and formulas
- Include chemical equations where appropriate
- REQUIRED: Include source_timestamp in MM:SS format (e.g., "14:50") for video content
- For multiple_choice: answer_config.correct uses 0=A, 1=B, 2=C, 3=D
- For true_false: answer_config.correct uses 0=false, 1=true
- For short_answer: answer_config.correct contains key chemistry terms
- For multiple_correct: answer_config.correct uses array of indices
- Set requires_diagram=true for molecular structures, reactions
- Include diagram_elements for molecular diagrams, reaction pathways
"""

    GENERIC_QUESTIONS = """SYSTEM: You are an adaptive AI tutor.

PEDAGOGICAL STRATEGY (Non-negotiable):
{user_profile}

CONTENT SOURCE (Strictly based on this):
{content}

TASK:
Generate exactly {total_questions} educational questions at {difficulty} level.

Question breakdown:
{question_breakdown}

Return valid JSON only:
{{
  "questions": [
    {{
      "question": "Educational question text",
      "question_type": "multiple_choice|true_false|short_answer|multiple_correct",
      "source_timestamp": "MM:SS or section reference",
      "options": {{"A": "option A", "B": "option B", "C": "option C", "D": "option D"}},
      "answer_config": {{"correct": [1]}},
      "reason": "Clear explanation of correct answer",
      "requires_diagram": false,
      "diagram_type": null,
      "diagram_elements": {{}}
    }}
  ]
}}

Rules:
- Test comprehension and understanding
- Use clear, concise language
- REQUIRED: Include source_timestamp in MM:SS format (e.g., "14:50") for video content
- For multiple_choice: answer_config.correct uses 0=A, 1=B, 2=C, 3=D
- For true_false: answer_config.correct uses 0=false, 1=true
- For short_answer: answer_config.correct contains key terms
- For multiple_correct: answer_config.correct uses array of indices
- Set requires_diagram=false for most general questions
"""