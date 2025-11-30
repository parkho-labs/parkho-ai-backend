import uuid
from typing import Dict, Any

import structlog
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService

from ..agents.physics_tutor_agent import PhysicsTutorAgent
from ..agents.general_tutor_agent import GeneralTutorAgent

logger = structlog.get_logger(__name__)


class ADKService:
    def __init__(self):
        self.session_service = InMemorySessionService()
        self.memory_service = InMemoryMemoryService()
        self.physics_agent = PhysicsTutorAgent()
        self.general_agent = GeneralTutorAgent()

        self.physics_runner = Runner(
            app_name="physics_tutor",
            agent=self.physics_agent,
            session_service=self.session_service,
            memory_service=self.memory_service
        )

        self.general_runner = Runner(
            app_name="general_tutor",
            agent=self.general_agent,
            session_service=self.session_service,
            memory_service=self.memory_service
        )

    async def generate_questions(self, content: str, title: str, question_config: Dict[str, int],
                               difficulty_level: str, subject_type: str = "general") -> Dict[str, Any]:
        try:
            user_id = "system_user"
            session_id = str(uuid.uuid4())

            runner = self.physics_runner if subject_type.lower() == "physics" else self.general_runner

            # Create content with our data
            from google.adk.events import Event
            message_content = {
                "content": content,
                "title": title,
                "question_config": question_config,
                "difficulty_level": difficulty_level
            }

            # Create a text message for the runner
            new_message = f"Generate questions based on this content: {str(message_content)}"

            events = []
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=new_message
            ):
                events.append(event)

            # Extract result from events
            result = {"questions": [], "total_questions": 0, "total_score": 0}
            for event in events:
                if hasattr(event, 'data') and isinstance(event.data, dict):
                    if 'questions' in event.data:
                        result = event.data
                        break

            return result

        except Exception as e:
            logger.error(f"ADK service failed: {str(e)}", exc_info=True)
            return {"questions": [], "total_questions": 0, "total_score": 0}


adk_service = ADKService()# ADK Service for future chatbot implementation - DO NOT COMMIT
