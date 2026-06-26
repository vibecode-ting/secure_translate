"""Region API routes — manage text regions and exclusion zones."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

from backend.database import get_db
from backend.models.document import Document
from backend.models.region import Region, RegionType

router = APIRouter()


# --- Request schemas ---


class RegionCreate(BaseModel):
    document_id: str
    page_number: int = Field(ge=0)
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    region_type: str = "text"
    label: Optional[str] = None


class RegionUpdate(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = Field(default=None, gt=0)
    height: Optional[float] = Field(default=None, gt=0)
    region_type: Optional[str] = None
    label: Optional[str] = None
    original_text: Optional[str] = None
    translated_text: Optional[str] = None


class ExclusionCreate(BaseModel):
    page_number: int = Field(ge=0)
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    label: Optional[str] = None


# --- Helpers ---


def _serialize_region(r: Region) -> dict:
    return {
        "id": r.id,
        "document_id": r.document_id,
        "page_number": r.page_number,
        "x": r.x,
        "y": r.y,
        "width": r.width,
        "height": r.height,
        "region_type": r.region_type.value,
        "original_text": r.original_text,
        "translated_text": r.translated_text,
        "font_size": r.font_size,
        "font_family": r.font_family,
        "label": r.label,
        "is_auto_detected": r.is_auto_detected,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# --- Endpoints ---


@router.get("/document/{document_id}")
def get_regions(
    document_id: str,
    page_number: Optional[int] = Query(None, ge=0),
    db: Session = Depends(get_db),
):
    """Get all regions for a document, optionally filtered by page number."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    query = db.query(Region).filter(Region.document_id == document_id)
    if page_number is not None:
        query = query.filter(Region.page_number == page_number)

    regions = query.order_by(Region.page_number, Region.y, Region.x).all()
    return {
        "document_id": document_id,
        "total": len(regions),
        "regions": [_serialize_region(r) for r in regions],
    }


@router.post("/")
def create_region(body: RegionCreate, db: Session = Depends(get_db)):
    """Create a new region (for manual exclusion zones or text regions)."""
    document = db.query(Document).filter(Document.id == body.document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if body.page_number >= document.page_count:
        raise HTTPException(
            status_code=400,
            detail=f"Page {body.page_number} out of range (0-{document.page_count - 1})",
        )

    # Validate region_type
    try:
        region_type = RegionType(body.region_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid region_type: {body.region_type}. Must be 'text' or 'exclusion'",
        )

    region = Region(
        document_id=body.document_id,
        page_number=body.page_number,
        x=body.x,
        y=body.y,
        width=body.width,
        height=body.height,
        region_type=region_type,
        label=body.label,
        is_auto_detected=False,
    )
    db.add(region)
    db.commit()
    db.refresh(region)

    return _serialize_region(region)


@router.put("/{region_id}")
def update_region(region_id: str, body: RegionUpdate, db: Session = Depends(get_db)):
    """Update a region — move/resize, change type, add label, set text."""
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    update_data = body.model_dump(exclude_unset=True)

    # Validate region_type if provided
    if "region_type" in update_data and update_data["region_type"] is not None:
        try:
            update_data["region_type"] = RegionType(update_data["region_type"])
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid region_type: {update_data['region_type']}",
            )

    for field, value in update_data.items():
        setattr(region, field, value)

    db.commit()
    db.refresh(region)

    return _serialize_region(region)


@router.delete("/{region_id}")
def delete_region(region_id: str, db: Session = Depends(get_db)):
    """Delete a region."""
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    db.delete(region)
    db.commit()

    return {"detail": "Region deleted", "region_id": region_id}


@router.post("/document/{document_id}/exclusion")
def create_exclusion_zone(
    document_id: str,
    body: ExclusionCreate,
    db: Session = Depends(get_db),
):
    """Create an exclusion zone — a region that will never be translated or sent externally."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if body.page_number >= document.page_count:
        raise HTTPException(
            status_code=400,
            detail=f"Page {body.page_number} out of range (0-{document.page_count - 1})",
        )

    region = Region(
        document_id=document_id,
        page_number=body.page_number,
        x=body.x,
        y=body.y,
        width=body.width,
        height=body.height,
        region_type=RegionType.EXCLUSION,
        label=body.label or "Exclusion zone",
        is_auto_detected=False,
    )
    db.add(region)
    db.commit()
    db.refresh(region)

    return _serialize_region(region)


@router.delete("/document/{document_id}/exclusions")
def clear_exclusion_zones(document_id: str, db: Session = Depends(get_db)):
    """Clear all exclusion zones for a document."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    deleted_count = (
        db.query(Region)
        .filter(
            Region.document_id == document_id,
            Region.region_type == RegionType.EXCLUSION,
        )
        .delete()
    )
    db.commit()

    return {
        "detail": "Exclusion zones cleared",
        "document_id": document_id,
        "deleted_count": deleted_count,
    }
