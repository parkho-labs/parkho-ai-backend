from typing import List, Dict, Any
import asyncio
import structlog

logger = structlog.get_logger(__name__)

class QuizEvaluator:

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    async def evaluate_quiz_submission(self, questions: List[Dict], user_answers: List[Dict]) -> Dict[str, Any]:
        question_results = []
        total_score = 0
        max_possible_score = 0

        for question in questions:
            user_answer = self._find_user_answer(question["question_id"], user_answers)
            if not user_answer:
                continue

            max_possible_score += question["max_score"]
            result = await self._evaluate_single_question(question, user_answer["user_answer"])
            total_score += result["score"]
            question_results.append(result)

        return {
            "total_score": total_score,
            "max_possible_score": max_possible_score,
            "question_results": question_results,
            "evaluated_at": self._get_current_timestamp()
        }

    async def _evaluate_single_question(self, question: Dict, user_answer: str) -> Dict[str, Any]:
        question_type = question["type"]
        answer_config = question["answer_config"]

        if question_type in ["mcq", "true_false"]:
            return self._evaluate_objective_question(question, user_answer)
        else:
            return await self._evaluate_subjective_question(question, user_answer)

    def _evaluate_objective_question(self, question: Dict, user_answer: str) -> Dict[str, Any]:
        answer_config = question["answer_config"]
        correct_answer = answer_config["correct_answer"]

        # Normalize both answers for comparison
        user_answer_normalized = str(user_answer).strip().lower()
        correct_answer_normalized = str(correct_answer).strip().lower()

        # Special handling for true/false - accept variations
        if question["type"] == "true_false":
            # Normalize true/false variations
            true_values = ["true", "t", "yes", "1"]
            false_values = ["false", "f", "no", "0"]

            if user_answer_normalized in true_values:
                user_answer_normalized = "true"
            elif user_answer_normalized in false_values:
                user_answer_normalized = "false"

            if correct_answer_normalized in true_values:
                correct_answer_normalized = "true"
            elif correct_answer_normalized in false_values:
                correct_answer_normalized = "false"

        is_correct = user_answer_normalized == correct_answer_normalized
        score = question["max_score"] if is_correct else 0

        return {
            "question_id": question["question_id"],
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "score": score,
            "max_score": question["max_score"],
            "is_correct": is_correct,
            "evaluation_method": "exact_match",
            "feedback": "Correct!" if is_correct else f"Incorrect. The correct answer is: {correct_answer}. {answer_config.get('reason', '')}"
        }

    async def _evaluate_subjective_question(self, question: Dict, user_answer: str) -> Dict[str, Any]:
        answer_config = question["answer_config"]
        correct_answer = answer_config.get("correct_answer", "No model answer provided")

        prompt = self._build_evaluation_prompt(question, user_answer, answer_config)

        try:
            llm_response = await self.llm_provider.generate_async(prompt)
            evaluation_result = self._parse_llm_evaluation(llm_response)

            final_score = min(evaluation_result["score"], question["max_score"])
            is_correct = final_score == question["max_score"]

            return {
                "question_id": question["question_id"],
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "score": final_score,
                "max_score": question["max_score"],
                "is_correct": is_correct,
                "evaluation_method": "llm_evaluated",
                "feedback": evaluation_result["feedback"]
            }
        except Exception as e:
            logger.error("LLM evaluation failed", error=str(e), question_id=question["question_id"])

            return {
                "question_id": question["question_id"],
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "score": 0,
                "max_score": question["max_score"],
                "is_correct": False,
                "evaluation_method": "evaluation_failed",
                "feedback": "Unable to evaluate this answer automatically."
            }

    def _build_evaluation_prompt(self, question: Dict, user_answer: str, answer_config: Dict) -> str:
        return f"""Evaluate this answer based on the provided criteria:

Question: {question["question"]}
Context: {question.get("context", "N/A")}

Expected Answer: {answer_config["correct_answer"]}
Scoring Criteria: {answer_config.get("reason", "Standard evaluation criteria")}
Maximum Score: {question["max_score"]}

Student Answer: {user_answer}

Provide evaluation in this exact format:
SCORE: [number between 0 and {question["max_score"]}]
FEEDBACK: [brief feedback explaining the score]"""

    def _parse_llm_evaluation(self, llm_response: str) -> Dict[str, Any]:
        lines = llm_response.strip().split('\n')
        score = 0
        feedback = "No feedback provided"

        for line in lines:
            if line.startswith("SCORE:"):
                try:
                    score = int(line.split(":", 1)[1].strip())
                except (ValueError, IndexError):
                    score = 0
            elif line.startswith("FEEDBACK:"):
                feedback = line.split(":", 1)[1].strip()

        return {"score": score, "feedback": feedback}

    def _find_user_answer(self, question_id: str, user_answers: List[Dict]) -> Dict:
        for answer in user_answers:
            if answer.get("question_id") == question_id:
                return answer
        return None

    def _get_current_timestamp(self) -> str:
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"