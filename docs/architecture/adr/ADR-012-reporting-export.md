# ADR-012 — Reporting and Export Tooling

## Status

Proposed

## Context

The Reporting module requires generating PDF reports, CSV exports, executive dashboards, and clinical summaries from analytics and prediction data. These outputs need to be visually consistent with the web dashboard, generated reliably in a server environment (no headless browser dependency at request time if avoidable), and capable of running as background jobs when a report is large or spans many patients.

## Decision

- **PDF generation** uses **WeasyPrint**, rendering report content as HTML/CSS via **Jinja2** templates and converting that HTML to PDF, rather than composing PDFs programmatically with a low-level canvas library.
- **CSV/XLSX exports** use **pandas** together with **openpyxl** for spreadsheet-formatted output.
- Report generation is triggered as a **background job** (reusing the Celery + Redis infrastructure introduced in ADR-010) whenever a report covers a large patient cohort or a full dashboard export; the API returns a job id and the frontend polls a status endpoint until the file is ready for download.
- Report templates reuse the same design tokens (Tailwind-derived colors/typography) as the web dashboard so PDF exports visually match the on-screen analytics.

## Alternatives Considered

- ReportLab (low-level PDF canvas API)
- wkhtmltopdf
- Puppeteer / headless Chrome PDF rendering
- py-pdf / fpdf2

## Consequences

### Positive

- HTML/CSS report templates are quick to design and iterate on, reusing existing frontend styling knowledge instead of learning a separate canvas-drawing API.
- Reusing Celery + Redis (already introduced for ML training) avoids adding a second background-job system just for reporting.
- Clinical summaries and executive dashboards can share template partials with the live dashboard, reducing duplicated layout logic.

### Negative

- WeasyPrint depends on system-level libraries (Pango, Cairo, GDK-PixBuf) that must be added to the Docker image, increasing image size and build complexity relative to a pure-Python PDF library.
- Complex multi-page pagination and print-specific layout (page breaks, running headers/footers) are more fiddly to control precisely in HTML/CSS than in a purpose-built PDF canvas library.
- Large-cohort PDF/CSV generation must be carefully bounded (streaming or job-based) to avoid memory spikes, since naive in-memory generation over thousands of patient records would not scale.

## References

- `docs/00_PROJECT_SCOPE.md` — Reporting requirements
- ADR-010 — ML model training, registry, and serving strategy (Celery + Redis infrastructure)
- ADR-006 — Docker for containerization
