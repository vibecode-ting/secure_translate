Build a production-grade full-stack document translation app for books and scanned documents.

The app must accept uploaded images and PDFs, detect text regions, and let the user mark which areas should never be translated, such as titles, fixed text blocks, and secret or internal images. The system must keep those protected areas completely untouched and must not send any image content from those areas to any external API or AI model. Only the selected or detected text regions may be processed.

The app must support heavy-load document translation for book-like workflows, including multi-page PDFs, large image batches, and high throughput. It should be designed for performance, reliability, and scalable background processing. The system should process documents in a way that preserves original page quality, layout, columns, spacing, and visual structure as closely as possible.

The translation output must replace the original text in-place inside the same frame, paragraph block, column, and page structure. The final result should look professionally reconstructed, with translated text placed naturally where the original text was, without requiring human verification after processing. For PDFs, the output should remain high quality and visually consistent with the source. For images, the output should preserve the original appearance as much as possible.

The app must support translation in these languages in any direction: English, Burmese, Simplified Chinese, Traditional Chinese, Vietnamese, Khmer, and Indonesian.

The translation engine should be configurable so it can use either a translation API or the Gemini API. You should choose the best architecture for reliable production use. Handle long documents, chunking, OCR, layout recovery, and rendering carefully. Build with secure document handling in mind, especially for files that contain hidden or sensitive images.

The system should be a polished web application with a modern frontend and a robust backend. It should support:

Image upload.

PDF upload.

Text region selection.

Exclusion regions for text or images that must not be translated.

Automatic text detection.

Translation only for allowed text.

Layout-preserving re-rendering.

Downloadable final image or PDF output.

Use any necessary MCP tools, sub-agents, or helper workflows you think are useful. If there are strong open-source projects, libraries, or repositories that can accelerate this build, reuse them instead of inventing everything from scratch. Prefer production-ready open-source components whenever possible.

Focus on building something practical, secure, scalable, and maintainable. Make your own technical decisions, but explain the architecture clearly in the codebase and README. If there are tradeoffs between perfect visual fidelity and engineering complexity, choose the best production-grade balance.

Deliver the project as a working codebase with clear setup instructions, environment variables, and a path to run locally. Include tests and a clean structure suitable for future extension.


Important product constraints
Protect secret areas absolutely.

Do not expose internal images or excluded content to any external translation service.

Handle both scanned PDFs and normal PDFs.

Support large files and long-running jobs.

Preserve original document structure as much as possible.

Output must be professional enough for book translation use.

What to produce
Build the complete solution, choosing the best architecture yourself. Include:

Frontend.

Backend.

OCR and layout analysis.

Translation integration.

Secure redaction or exclusion handling.

Rendering pipeline.

Background job processing for heavy load.

Tests.

Docker support.

README.

First, inspect the best open-source repositories and decide whether to adapt an existing project or combine multiple approaches. Then implement the solution in a clean, production-ready way.

Language requirements
The system must support translation among:

English.

Burmese.

Simplified Chinese.

Traditional Chinese.

Vietnamese.

Khmer.

Indonesian.

Use these language names and codes consistently in the app, APIs, and UI.

Security requirements
Any region marked as secret, excluded, or protected must remain private and must not be passed to the translation API or Gemini API. Only the allowed text content may leave the system. The final exported document must not leak excluded content through hidden layers, metadata, OCR leftovers, or embedded text.

If the best approach is to rasterize and reconstruct pages to guarantee privacy and visual correctness, do that.

Success criteria
The app should be good enough for production-oriented document translation workflows, especially books and scanned PDFs, with strong layout preservation and strict privacy handling.
