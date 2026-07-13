"""Document model — tracks uploaded files and their processing state."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, Enum as SAEnum, Text, JSON
from sqlalchemy.orm import relationship
from backend.database import Base
import enum


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"  # OCR / text extraction running
    READY = "ready"            # Regions detected, ready for user review
    TRANSLATING = "translating"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentType(str, enum.Enum):
    PDF = "pdf"
    IMAGE = "image"


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    doc_type = Column(SAEnum(DocumentType), nullable=False)
    status = Column(SAEnum(DocumentStatus), default=DocumentStatus.UPLOADED)
    page_count = Column(Integer, default=1)
    file_size_bytes = Column(Integer, nullable=False)

    # Source/target language
    source_language = Column(String(10), nullable=True)
    target_language = Column(String(10), nullable=True)

    # Processing metadata
    progress = Column(Float, default=0.0)  # 0.0 to 1.0
    error_message = Column(Text, nullable=True)

    # File metadata (JSON — stores PDF-specific info like has_images, title, etc.)
    metadata_json = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    regions = relationship("Region", back_populates="document", cascade="all, delete-orphan")
    jobs = relationship("TranslationJob", back_populates="document", cascade="all, delete-orphan")
