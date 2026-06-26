"""Translation job model — tracks background translation tasks."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, Enum as SAEnum, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.database import Base
import enum


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TranslationJob(Base):
    __tablename__ = "translation_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    celery_task_id = Column(String(255), nullable=True)

    # Configuration
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    engine = Column(String(50), nullable=False, default="gemini")  # gemini, azure, google

    # Status
    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING)
    progress = Column(Float, default=0.0)  # 0.0 to 1.0
    pages_completed = Column(Integer, default=0)
    total_pages = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    # Output
    output_filename = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    document = relationship("Document", back_populates="jobs")
