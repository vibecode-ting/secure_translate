# Secure Translate — CLAUDE.md

## Project Overview

Production-grade document translation app for books, scanned documents, and multi-page PDFs. Users upload PDFs (with text, images, and mixed content), preview them live, select language pairs, and get layout-preserving translated output.

## Core User Flow

```
Upload PDF → Live Preview → Select Languages → Translate → Download translated PDF
```

1. **Upload** — User uploads one or more PDFs (10+ pages, mixed text/images)
2. **Live Preview** — Rendered preview of all pages with zoom/scroll
3. **Language Selection** — Source language (or auto-detect) → Target language
4. **Translate** — Text extracted paragraph-by-paragraph, translated via selected engine
5. **Rewrite PDF** — Original text removed, translated text embedded in-place preserving layout
6. **Download** — User downloads `translated_filename.pdf`

## Target Languages

| Code | Language |
|------|----------|
| `auto` | Auto-detect |
| `en` | English |
| `my` | Burmese |
| `zh-Hans` | Simplified Chinese |
| `zh-Hant` | Traditional Chinese |
| `vi` | Vietnamese |
| `km` | Khmer |
| `id` | Indonesian |
| `ja` | Japanese |
| `ko` | Korean |
| `th` | Thai |

Any-to-any translation direction.

## Tech Stack

- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS
- **Backend**: Python FastAPI
- **OCR**: RapidOCR (PaddleOCR ONNX)
- **PDF**: PyMuPDF (pymupdf/fitz) — text extraction + redaction + insertion
- **Image Processing**: Pillow + PangoCairo
- **Translation**: Configurable — Gemini (default), Azure, Google
- **Task Queue**: Celery + Redis
- **Database**: SQLite (dev) / PostgreSQL (prod)

## Project Structure

```
secure_translate/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Settings from env vars
│   ├── database.py          # SQLAlchemy setup
│   ├── api/                 # REST endpoints (documents, regions, jobs)
│   ├── models/              # SQLAlchemy models (Document, Region, TranslationJob)
│   ├── services/            # Business logic (OCR, PDF, image, translation, security)
│   ├── engines/             # Translation engines (Gemini, Azure, Google)
│   ├── tasks/               # Celery background tasks
│   ├── fonts/               # Noto Sans font files
│   └── tests/               # pytest tests
├── frontend/
│   ├── src/
│   │   ├── api/             # API client
│   │   ├── hooks/           # React hooks
│   │   ├── components/      # UI components
│   │   └── pages/           # Route pages
│   └── ...
├── idea.md                  # Original project idea
├── README.md                # Setup instructions
├── CLAUDE.md                # This file
├── .env.example             # Environment template
└── docker-compose.yml       # Docker setup
```

## Running Locally

### Quick Start
```bash
./start.sh
```

### Manual Start

**Backend:**
```bash
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
pnpm install
pnpm dev
```

**Celery Worker (for background translation):**
```bash
celery -A backend.tasks.celery_app worker --loglevel=info
```

### URLs
| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

### Tests
```bash
cd backend && pytest tests/ -v
```

## API Endpoints

### Documents
- `POST /api/documents/upload` — Upload PDF(s)
- `GET /api/documents/` — List documents
- `GET /api/documents/{id}` — Get document details
- `DELETE /api/documents/{id}` — Delete document
- `POST /api/documents/{id}/detect` — Run OCR text detection
- `GET /api/documents/{id}/pages/{page}/image` — Get page image for preview
- `GET /api/documents/{id}/pages/{page}/text` — Get extracted text for a page

### Regions
- `GET /api/regions/document/{doc_id}` — Get regions for document
- `POST /api/regions/` — Create region
- `PUT /api/regions/{id}` — Update region
- `DELETE /api/regions/{id}` — Delete region
- `POST /api/regions/document/{doc_id}/exclusion` — Create exclusion zone

### Jobs
- `POST /api/jobs/` — Start translation job
- `GET /api/jobs/{id}` — Get job status (with progress %)
- `POST /api/jobs/{id}/cancel` — Cancel job
- `GET /api/jobs/{id}/result` — Get translation result

### Languages
- `GET /api/languages` — List supported languages
- `POST /api/languages/detect` — Auto-detect document language

## Security Model

- Exclusion zones enforced server-side
- Protected text never sent to external APIs
- API keys in `.env`, never committed
- Uploaded files stored locally only

## Translation Pipeline (Detailed)

1. **Upload** → Save PDF, create DB record, extract page count
2. **Preview** → Render each page as image for live preview
3. **Detect** → OCR extracts text regions with bounding boxes per page
4. **Language** → Auto-detect source language, user selects target
5. **Filter** → Security service removes exclusion zones from text regions
6. **Translate** → Each paragraph/region translated individually via selected engine
7. **Render** → PyMuPDF redacts original text, inserts translated text at same positions
8. **Output** → New PDF saved with translated content, original layout preserved

## Build Status

- [x] Basic FastAPI + React scaffold
- [x] File upload (images + PDFs)
- [x] OCR text detection (RapidOCR)
- [x] Region management (text + exclusion zones)
- [x] Translation engines (Gemini, Azure, Google)
- [x] Basic PDF text replacement
- [x] Image compositing with translated text
- [x] Background Celery tasks
- [x] Docker setup
- [ ] Multi-page PDF preview (live viewer)
- [ ] Language auto-detection
- [ ] Source/target language selector UI
- [ ] Paragraph-level translation pipeline
- [ ] Layout-preserving PDF rewrite (production quality)
- [ ] Progress tracking with percentage
- [ ] Batch PDF upload
- [ ] Download translated PDF

## Conventions

- **Package manager**: pnpm (frontend), pip (backend)
- **Python**: 3.11+
- **Node**: 20+
- **Git**: conventional commits (`feat:`, `fix:`, `chore:`, `security:`)
- **Branching**: Feature branches from `main`, PR to merge
- **Testing**: pytest for backend, vitest for frontend
