"""Region model — bounding boxes for text regions and exclusion zones."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, Enum as SAEnum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from backend.database import Base
import enum


class RegionType(str, enum.Enum):
    TEXT = "text"            # Detected text region — will be translated
    EXCLUSION = "exclusion"  # User-marked exclusion zone — never translated or sent externally


class Region(Base):
    __tablename__ = "regions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer, nullable=False, default=0)

    # Bounding box — pixel coordinates on the rendered page image
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)

    # Region classification
    region_type = Column(SAEnum(RegionType), nullable=False, default=RegionType.TEXT)

    # For text regions: OCR-detected text content
    original_text = Column(String(5000), nullable=True)
    translated_text = Column(String(5000), nullable=True)

    # Font info from OCR (for rendering translated text)
    font_size = Column(Float, nullable=True)
    font_family = Column(String(100), nullable=True)

    # User can label exclusion zones
    label = Column(String(255), nullable=True)  # e.g., "title", "header image", "secret"

    # Whether this region was auto-detected or manually created
    is_auto_detected = Column(Boolean, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    document = relationship("Document", back_populates="regions")
