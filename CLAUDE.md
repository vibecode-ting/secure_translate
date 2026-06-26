# Secure Translate — CLAUDE.md

## Project Overview

Production-grade document translation app for books and scanned documents. Accepts images and PDFs, detects text regions, lets users mark exclusion zones (never sent to external APIs), translates only allowed text, and produces layout-preserving output.

## Tech Stack

- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS
- **Backend**: Python FastAPI
- **OCR**: RapidOCR (PaddleOCR ONNX)
- **PDF**: PyMuPDF (pymupdf/fitz)
- **Image Processing**: Pillow + PangoCairo
- **Translation**: Configurable — Gemini (default), Azure, Google
- **Task Queue**: Celery + Redis
- **Database**: SQLite (dev) / PostgreSQL (prod)

## Target Languages

English, Burmese, Simplified Chinese, Traditional Chinese, Vietnamese, Khmer, Indonesian (any direction).

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

### Backend
```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env  # Edit with your API keys
uvicorn backend.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
pnpm install
pnpm dev  # Runs on http://localhost:5173
```

### Celery Worker (for background translation)
```bash
celery -A backend.tasks.celery_app worker --loglevel=info
```

## Security Model

- Exclusion zones are enforced server-side
- Protected pixels never leave the server — only extracted text from allowed regions is sent to translation APIs
- API keys stored in .env, never committed
- Uploads stored locally

## Translation Pipeline

1. Upload image/PDF
2. OCR/text extraction with bounding boxes
3. User reviews detected regions + marks exclusion zones
4. Security service filters out exclusion zones
5. Only allowed text sent to translation engine
6. Translated text rendered back into original layout
7. Output available for download (image or PDF)
