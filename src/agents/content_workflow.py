from sqlalchemy.orm import Session
import structlog

from .workflow.workflow_orchestrator import WorkflowOrchestrator
from ..exceptions import WorkflowError

logger = structlog.get_logger(__name__)


class ContentWorkflow:
    def __init__(self, db_session: Session):
        self.orchestrator = WorkflowOrchestrator(db_session)

    async def process_content(self, job_id: int) -> None:
        try:
            await self.orchestrator.process_content(job_id)
        except Exception as e:
            logger.error("content_workflow_failed", job_id=job_id, error=str(e))
            raise WorkflowError(f"Content workflow failed: {str(e)}")


class LegacyContentWorkflow:
    def __init__(self):
        from ..core.database import SessionLocal
        logger.warning("using_legacy_content_workflow",
                      message="Consider migrating to dependency-injected ContentWorkflow")
        self.session_factory = SessionLocal

    async def process_content(self, job_id: int) -> None:
        with self.session_factory() as session:
            workflow = ContentWorkflow(session)
            await workflow.process_content(job_id)

    async def process_content_legacy(self, job_id: int):
        return await self.process_content(job_id)