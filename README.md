# Secure Translate

Production-grade document translation app for books and scanned documents.

## Features

- **Image & PDF upload** — drag-and-drop file upload for images (JPG, PNG) and multi-page PDFs
- **Automatic text detection** — OCR-based text region detection using PaddleOCR
- **Exclusion zones** — mark areas that must never be translated or sent to external APIs
- **Layout-preserving translation** — translated text replaces original in-place, preserving structure
- **Multiple translation engines** — configurable: Gemini (default), Azure Translator, Google Cloud Translation
- **7 languages** — English, Burmese, Simplified Chinese, Traditional Chinese, Vietnamese, Khmer, Indonesian
- **Background processing** — Celery + Redis for heavy document workloads
- **Secure by design** — protected regions are filtered server-side before any API call

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Frontend   │────▶│  FastAPI API  │────▶│  Celery Workers  │
│  React + TS  │     │              │     │                  │
└─────────────┘     └──────┬───────┘     └────────┬─────────┘
                           │                      │
                    ┌──────▼───────┐       ┌──────▼─────────┐
                    │   SQLite/PG  │       │ Translation API │
                    │   Database   │       │ Gemini/Azure/…  │
                    └──────────────┘       └────────────────┘
```

### Translation Pipeline

1. **Upload** → Save file, create DB record
2. **Detect** → OCR finds text regions with bounding boxes
3. **Review** → User marks exclusion zones in the editor
4. **Translate** → Security filter removes exclusions, only allowed text sent to engine
5. **Render** → Translated text placed back into original layout
6. **Download** → Output available as image or PDF

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Redis (for background processing)
- pnpm

### 1. Clone & Configure

```bash
cd secure_translate
cp .env.example .env
# Edit .env with your translation API keys
```

### 2. Start Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..
uvicorn backend.main:app --reload --port 8000
```

### 3. Start Frontend

```bash
cd frontend
pnpm install
pnpm dev
# Opens at http://localhost:5173
```

### 4. Start Celery Worker (for background translation)

```bash
celery -A backend.tasks.celery_app worker --loglevel=info
```

### 5. Open

Visit `http://localhost:5173` and upload a document.

## Docker Setup

```bash
cp .env.example .env
# Edit .env with your API keys
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEFAULT_TRANSLATION_ENGINE` | Translation engine to use | `gemini` |
| `GEMINI_API_KEY` | Google Gemini API key | — |
| `AZURE_TRANSLATOR_KEY` | Azure Translator key | — |
| `AZURE_TRANSLATOR_REGION` | Azure region | — |
| `GOOGLE_TRANSLATE_API_KEY` | Google Cloud Translation key | — |
| `DATABASE_URL` | Database connection string | `sqlite:///./secure_translate.db` |
| `REDIS_URL` | Redis URL for Celery | `redis://localhost:6379/0` |
| `OCR_DPI` | DPI for PDF page rendering | `300` |
| `MAX_FILE_SIZE_MB` | Max upload file size | `100` |

## Translation Engines

| Engine | Best For | Pricing |
|--------|----------|---------|
| **Gemini** (default) | Long documents, context-aware translation | ~$0.15-0.45 per book |
| **Azure** | Production reliability, best free tier | $10/1M chars (2M free/month) |
| **Google** | Glossary support, custom models | $20/1M chars |

## Security Model

Exclusion zones are the core security feature:

1. User draws rectangles over sensitive areas (titles, internal images, secret text)
2. These are stored as bounding box coordinates in the database
3. **Before any translation API call**, the security service filters out all text regions that overlap with exclusion zones
4. **No image content from exclusion zones is ever sent externally**
5. The `validate_no_exclusion_leak()` function is the final safety gate

## Supported Languages

| Code | Language |
|------|----------|
| `en` | English |
| `my` | Burmese |
| `zh-Hans` | Simplified Chinese |
| `zh-Hant` | Traditional Chinese |
| `vi` | Vietnamese |
| `km` | Khmer |
| `id` | Indonesian |

Any-to-any translation direction is supported.

## API Endpoints

### Documents
- `POST /api/documents/upload` — Upload image or PDF
- `GET /api/documents/` — List documents
- `GET /api/documents/{id}` — Get document details
- `DELETE /api/documents/{id}` — Delete document
- `POST /api/documents/{id}/detect` — Run OCR text detection
- `GET /api/documents/{id}/pages/{page}/image` — Get page image

### Regions
- `GET /api/regions/document/{doc_id}` — Get regions for document
- `POST /api/regions/` — Create region
- `PUT /api/regions/{id}` — Update region
- `DELETE /api/regions/{id}` — Delete region
- `POST /api/regions/document/{doc_id}/exclusion` — Create exclusion zone

### Jobs
- `POST /api/jobs/` — Start translation job
- `GET /api/jobs/{id}` — Get job status
- `POST /api/jobs/{id}/cancel` — Cancel job

## Running Tests

```bash
cd backend
pytest tests/ -v
```

## License

MIT
