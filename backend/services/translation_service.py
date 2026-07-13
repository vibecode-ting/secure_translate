"""Translation pipeline — orchestrates the full document translation workflow."""

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from backend.config import settings
from backend.engines import TranslationEngine, GeminiEngine, AzureEngine, GoogleEngine
from backend.models.document import Document, DocumentType, DocumentStatus
from backend.models.region import Region, RegionType
from backend.services import security_service
from backend.services import ocr_service
from backend.services import pdf_service
from backend.services import image_service

logger = logging.getLogger(__name__)

# Map engine name strings to their classes.
_ENGINE_MAP: dict[str, type[TranslationEngine]] = {
    "gemini": GeminiEngine,
    "azure": AzureEngine,
    "google": GoogleEngine,
}


def _get_engine(name: str) -> TranslationEngine:
    """Instantiate a translation engine by name."""
    cls = _ENGINE_MAP.get(name.lower())
    if cls is None:
        raise ValueError(
            f"Unknown translation engine '{name}'. "
            f"Available: {', '.join(_ENGINE_MAP)}"
        )
    return cls()


class TranslationPipeline:
    """Orchestrates document translation from OCR through rendering.

    Usage::

        pipeline = TranslationPipeline("gemini", "en", "my")
        pipeline.translate_document(document_id, db_session)
    """

    def __init__(self, engine_name: str, source_lang: str, target_lang: str):
        self.engine = _get_engine(engine_name)
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.engine_name = engine_name
        logger.info(
            "TranslationPipeline initialized: %s -> %s via %s",
            source_lang, target_lang, engine_name,
        )

    # ------------------------------------------------------------------
    # Text translation
    # ------------------------------------------------------------------

    def translate_text(self, text: str) -> str:
        """Translate a single text chunk using the configured engine.

        Args:
            text: Source text to translate.

        Returns:
            Translated text.

        Raises:
            Exception: On engine failure.
        """
        if not text.strip():
            return ""
        return self.engine.translate(text, self.source_lang, self.target_lang)

    def chunk_text(self, text: str, max_chars: int = 4000) -> list[str]:
        """Split long text into chunks at sentence boundaries.

        Tries to break on sentence-ending punctuation first, then
        falls back to word boundaries.

        Args:
            text: Text to split.
            max_chars: Maximum characters per chunk.

        Returns:
            List of text chunks.
        """
        if len(text) <= max_chars:
            return [text]

        chunks: list[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= max_chars:
                chunks.append(remaining)
                break

            # Try to find a sentence boundary within the limit
            # Look for . ! ? followed by whitespace, working backwards
            cut = max_chars
            best_cut = -1

            # Sentence-ending pattern (look backwards from max_chars)
            for i in range(min(max_chars, len(remaining)) - 1, max_chars // 2, -1):
                if remaining[i] in ".!?\n" and i + 1 < len(remaining) and remaining[i + 1] in " \n\t":
                    best_cut = i + 1
                    break

            if best_cut > 0:
                cut = best_cut
            else:
                # Fall back to last space
                last_space = remaining.rfind(" ", max_chars // 2, max_chars)
                if last_space > 0:
                    cut = last_space

            chunks.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()

        return chunks

    def translate_regions(self, regions: list[dict]) -> dict[str, str]:
        """Translate all text regions, returning a mapping of original -> translated.

        Long texts are chunked before translation to stay within API limits.

        Args:
            regions: List of region dicts (must include 'text' key).

        Returns:
            Dict mapping original_text -> translated_text.
        """
        translations: dict[str, str] = {}
        total = len(regions)

        for idx, region in enumerate(regions):
            original = region.get("text", "").strip()
            if not original:
                continue

            # Deduplicate: don't translate the same text twice
            if original in translations:
                continue

            try:
                # Chunk long texts
                chunks = self.chunk_text(original, settings.CHUNK_SIZE_CHARS)
                translated_chunks: list[str] = []

                for chunk in chunks:
                    translated = self.translate_text(chunk)
                    translated_chunks.append(translated)

                translations[original] = "".join(translated_chunks)

                if (idx + 1) % 10 == 0 or idx + 1 == total:
                    logger.info("Translated %d / %d regions", idx + 1, total)

            except Exception:
                logger.exception("Failed to translate region: '%s'", original[:80])
                translations[original] = original  # fallback to original

        return translations

    # ------------------------------------------------------------------
    # Full document pipeline
    # ------------------------------------------------------------------

    def translate_document(self, document_id: str, db_session: Session) -> None:
        """Run the full translation pipeline on a document.

        Steps:
        1. Load document and its regions from the database.
        2. Collect exclusion zones.
        3. Filter regions through the security layer.
        4. Validate that no exclusion zones leak.
        5. Translate all safe regions.
        6. Render the translated text onto the output.
        7. Update document status.

        Args:
            document_id: UUID of the document to translate.
            db_session: SQLAlchemy session.
        """
        # --- Load document ---
        document = db_session.query(Document).filter(Document.id == document_id).first()
        if document is None:
            raise ValueError(f"Document {document_id} not found")

        document.status = DocumentStatus.TRANSLATING
        db_session.commit()

        try:
            # --- Load regions ---
            all_regions = (
                db_session.query(Region)
                .filter(Region.document_id == document_id)
                .all()
            )

            text_regions = [
                _region_to_dict(r) for r in all_regions
                if r.region_type == RegionType.TEXT
            ]
            exclusion_zones = [
                _region_to_dict(r) for r in all_regions
                if r.region_type == RegionType.EXCLUSION
            ]

            logger.info(
                "Document %s: %d text regions, %d exclusion zones",
                document_id, len(text_regions), len(exclusion_zones),
            )

            # --- Security filter ---
            safe_regions = security_service.filter_regions_for_translation(
                text_regions, exclusion_zones,
            )

            # Safety validation — must pass before touching any external API
            if not security_service.validate_no_exclusion_leak(safe_regions, exclusion_zones):
                raise RuntimeError(
                    "Security validation failed: exclusion zone leak detected. "
                    "Aborting translation."
                )

            logger.info("Security check passed: %d regions approved for translation", len(safe_regions))

            # --- Translate ---
            translations = self.translate_regions(safe_regions)

            # --- Persist translated text back to DB ---
            region_map = {r.original_text: r for r in all_regions if r.region_type == RegionType.TEXT}
            for original_text, translated_text in translations.items():
                if original_text in region_map:
                    region_map[original_text].translated_text = translated_text

            db_session.commit()

            # --- Render output ---
            self._render_output(document, all_regions, translations, db_session)

            document.status = DocumentStatus.COMPLETED
            document.progress = 1.0
            db_session.commit()

            logger.info("Document %s translation completed", document_id)

        except Exception as exc:
            document.status = DocumentStatus.FAILED
            document.error_message = str(exc)[:2000]
            db_session.commit()
            logger.exception("Translation failed for document %s", document_id)
            raise

    # ------------------------------------------------------------------
    # Output rendering
    # ------------------------------------------------------------------

    def _render_output(
        self,
        document: Document,
        regions: list[Region],
        translations: dict[str, str],
        db_session: Session,
    ) -> None:
        """Render translated content and save the output file."""
        output_dir = settings.OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        source_path = settings.UPLOAD_DIR / document.filename

        if document.doc_type == DocumentType.PDF:
            self._render_pdf_output(
                document, source_path, regions, translations, output_dir,
            )
        else:
            self._render_image_output(
                document, source_path, regions, translations, output_dir,
            )

    def _render_pdf_output(
        self,
        document: Document,
        source_path: Path,
        regions: list[Region],
        translations: dict[str, str],
        output_dir: Path,
    ) -> None:
        """Render a translated PDF using the production-quality rewrite pipeline.

        Steps:
        1. Extract paragraphs from the source PDF (paragraph-level grouping).
        2. Match extracted paragraphs to the translated regions from the DB.
        3. Rewrite the PDF: redact originals, insert translations at same positions.
        """
        output_path = str(output_dir / f"translated_{document.filename}")
        font_path = str(settings.FONT_DIR / "NotoSans-Regular.ttf")

        # Extract paragraphs from the source PDF (groups lines into paragraphs)
        paragraphs = pdf_service.extract_paragraphs_from_pdf(str(source_path))

        if not paragraphs:
            # Fallback: use the legacy region-based replacement if extraction yields nothing
            logger.warning(
                "Paragraph extraction returned empty for %s, falling back to region-based replacement",
                source_path,
            )
            region_dicts = [_region_to_dict(r) for r in regions if r.region_type == RegionType.TEXT]
            pdf_service.replace_text_in_pdf(
                pdf_path=str(source_path),
                translations=translations,
                regions=region_dicts,
                output_path=output_path,
                font_path=font_path,
            )
        else:
            # Build a paragraph-keyed translation map.
            # The DB regions are line-level, but the PDF extraction groups them
            # into paragraphs.  We need to match paragraph text to translations.
            paragraph_translations = _build_paragraph_translations(
                paragraphs, translations,
            )

            pdf_service.rewrite_pdf_with_translations(
                pdf_path=str(source_path),
                paragraphs=paragraphs,
                translations=paragraph_translations,
                output_path=output_path,
                font_path=font_path,
            )

        document.output_filename = f"translated_{document.filename}"
        logger.info("PDF output saved to %s", output_path)

    def _render_image_output(
        self,
        document: Document,
        source_path: Path,
        regions: list[Region],
        translations: dict[str, str],
        output_dir: Path,
    ) -> None:
        """Render a translated image by compositing translated text."""
        from PIL import Image

        image = Image.open(source_path)
        text_region_dicts = [_region_to_dict(r) for r in regions if r.region_type == RegionType.TEXT]

        font_path = str(settings.FONT_DIR / "NotoSans-Regular.ttf")

        result = image_service.composite_page(
            original=image,
            regions=text_region_dicts,
            translations=translations,
            font_path=font_path,
        )

        output_filename = f"translated_{document.filename}"
        output_path = output_dir / output_filename
        result.save(str(output_path), quality=95)

        document.output_filename = output_filename
        logger.info("Image output saved to %s", output_path)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _region_to_dict(region: Region) -> dict:
    """Convert a Region ORM object to a plain dict for service functions."""
    return {
        "id": region.id,
        "page_number": region.page_number,
        "x": region.x,
        "y": region.y,
        "width": region.width,
        "height": region.height,
        "text": region.original_text or "",
        "font_size": region.font_size,
        "region_type": region.region_type.value if region.region_type else "text",
    }


def _build_paragraph_translations(
    paragraphs: list[dict],
    line_translations: dict[str, str],
) -> dict[str, str]:
    """Map paragraph text to translations by combining line-level translations.

    The translation pipeline operates on individual text lines (regions),
    but the PDF rewrite pipeline works at the paragraph level.  This
    function bridges the gap: for each paragraph, it looks up the
    translation for every line that makes up the paragraph and joins them
    in the same order.

    If a paragraph's text does not match any line translations exactly
    (e.g., the paragraph was extracted differently), we fall back to
    concatenating translations for substrings that appear in the
    paragraph text.

    Args:
        paragraphs: Paragraph dicts from ``extract_paragraphs_from_pdf``.
        line_translations: Mapping of original_line_text -> translated_text
                          (from the DB / translation engine).

    Returns:
        Mapping of paragraph_text -> translated_paragraph_text.
    """
    paragraph_translations: dict[str, str] = {}

    for para in paragraphs:
        para_text = para.get("text", "").strip()
        if not para_text:
            continue

        # Fast path: exact match
        if para_text in line_translations:
            paragraph_translations[para_text] = line_translations[para_text]
            continue

        # The paragraph text contains newline-joined lines.
        # Try to translate each line individually and join.
        lines = para_text.split("\n")
        translated_lines: list[str] = []
        all_found = True

        for line in lines:
            stripped = line.strip()
            if not stripped:
                translated_lines.append("")
                continue
            if stripped in line_translations:
                translated_lines.append(line_translations[stripped])
            else:
                # Partial match: check if any translation key is a substring
                found = False
                for orig, trans in line_translations.items():
                    if orig.strip() == stripped:
                        translated_lines.append(trans)
                        found = True
                        break
                if not found:
                    # No translation found for this line -- keep original
                    translated_lines.append(stripped)
                    all_found = False

        if any(t for t in translated_lines if t):  # at least some translation happened
            paragraph_translations[para_text] = "\n".join(translated_lines)

    logger.debug(
        "Built %d paragraph translations from %d line translations",
        len(paragraph_translations), len(line_translations),
    )

    return paragraph_translations
