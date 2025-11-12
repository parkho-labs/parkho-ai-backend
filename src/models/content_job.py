from datetime import datetime
from typing import Optional, Dict, Any
import json
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
import enum

from ..core.database import Base


class ContentJob(Base):
    __tablename__ = "content_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=True)

    status = Column(String, nullable=False, default="pending")
    progress = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    input_config = Column(Text, nullable=True)
    output_config = Column(Text, nullable=True)

    title = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    # RAG/Collection integration fields
    collection_name = Column(String, nullable=True)  # Selected collection for quiz generation
    should_add_to_collection = Column(Boolean, default=False)  # User choice to add content to collection
    rag_context_used = Column(Boolean, default=False)  # Track if RAG context was used in generation

    @property
    def input_config_dict(self) -> Optional[Dict[str, Any]]:
        if self.input_config:
            try:
                return json.loads(self.input_config)
            except json.JSONDecodeError:
                return None
        return None

    @input_config_dict.setter
    def input_config_dict(self, value: Optional[Dict[str, Any]]):
        if value is not None:
            self.input_config = json.dumps(value)
        else:
            self.input_config = None

    @property
    def output_config_dict(self) -> Optional[Dict[str, Any]]:
        if self.output_config:
            try:
                return json.loads(self.output_config)
            except json.JSONDecodeError:
                return None
        return None

    @output_config_dict.setter
    def output_config_dict(self, value: Optional[Dict[str, Any]]):
        if value is not None:
            self.output_config = json.dumps(value)
        else:
            self.output_config = None

    @property
    def input_url(self) -> Optional[str]:
        config = self.input_config_dict
        return config.get("input_url") if config else None

    @property
    def file_ids(self) -> list[str]:
        config = self.input_config_dict
        return config.get("file_ids", []) if config else []

    @property
    def questions(self) -> Optional[list]:
        config = self.output_config_dict
        return config.get("questions") if config else None

    @property
    def summary(self) -> Optional[str]:
        config = self.output_config_dict
        return config.get("summary") if config else None

    @property
    def content_text(self) -> Optional[str]:
        config = self.output_config_dict
        return config.get("content_text") if config else None

    def set_input_config(
        self,
        input_config: list = None,
        question_types: Optional[list[str]] = None,
        difficulty_level: str = "intermediate",
        num_questions: int = 5,
        generate_summary: bool = True,
        llm_provider: str = "openai"
    ):
        config = {
            "difficulty_level": difficulty_level,
            "num_questions": num_questions,
            "generate_summary": generate_summary,
            "llm_provider": llm_provider
        }

        if input_config:
            config["input_config"] = input_config

        if question_types:
            config["question_types"] = question_types

        self.input_config_dict = config

    def update_output_config(self, **updates):
        current = self.output_config_dict or {}
        current.update(updates)
        self.output_config_dict = current