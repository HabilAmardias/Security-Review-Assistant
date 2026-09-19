# ASE Security Review Agent

An **on-premise, local RAG/agent** that reviews software requirements and decides whether an
application needs a **penetration test or only DAST** — with reasoning and a security test scope.

It takes an **FRD** (Functional Requirements Document) and an **NFRD** (Non-Functional
Requirements Document) and returns:

1. **Is a pentest needed, or is DAST sufficient?** (`pentest | dast | none`)
2. **Reasoning** — citing the STRIDE threats, trust boundaries, assets, and the relevant
   previous security reviews that were retrieved.
3. **Scope** — in/out of scope components, test methods, environments, and effort estimate.

The agent decides based on **your** SOP, policies, and previous security review documents, which
you upload. Everything runs locally (Ollama for LLM + embeddings, Chroma for vectors, SQLite for
audit logging).

---

## Key features

- **Fully on-premise** — no cloud calls. Local Ollama (LLM + embeddings), Chroma (vector store),
  SQLite (metadata + audit log).
- **Password-protected PDFs** — enter the password once at upload/unlock time; it is used only
  **in memory** during decryption and is **never stored in the database or logs**. Re-indexing
  later uses a cached plaintext copy, so the password is never needed again.
- **Scalable ingestion** — hierarchical chunking (headings in English *and* Indonesian: BAB/Pasal,
  numbered, markdown), batched embedding, streaming page extraction, and a per-document state
  machine (`pending → extracting → chunking → embedding → ready`) with progress exposed via the API.
- **Hybrid retrieval** — multi-query vector search fused with BM25 keyword search via Reciprocal
  Rank Fusion, so acronyms like `DAST`, `NFRD`, `SOP` are matched robustly in EN/ID corpora.
- **Auditable decisions** — deterministic rule engine (config-driven) + LLM reasoning. Every review
  stores the extracted facts, retrieved sources, rules fired, the LLM decision, and any
  rule-vs-LLM **conflicts** that need a human call.
- **Form-field extraction (Confluence radio/checkbox grids)** — PyMuPDF reads font colours in the
  review PDFs and deterministically detects which option is *selected* in fields. Selections
  are shown in the report and used to ground the facts.
- **Deterministic exposure + human confirmation** — app exposure (intranet / internet-facing /
  partner) is resolved by *human override → PDF form field → LLM*; when it can't be determined, the
  UI asks you to confirm it so the exposure rules fire correctly.
- **Enforced intranet cap** — an intranet app's final verdict is clamped to **DAST** even if the LLM
  recommends pentest (the LLM's recommendation stays visible as a conflict; you can still override).
- **Web UI** — Vite + React (Trust & Authority design, dark/light mode), Knowledge Base,
  New Review, Review Detail, History, and Settings pages.
- **Layered, unit-testable backend** — `controller → usecase → repository → data`, dependency
  injection, and an in-memory test suite (no network/DB in unit tests).

---

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│  Web UI (React/Vite)  ──  FastAPI (127.0.0.1:8000)            │
│   Knowledge Base   New Review   Review Detail   Settings       │
├───────────────────────────────────┬───────────────────────────┤
│  Ingestion pipeline (UI upload)   │  Review agent             │
│   pypdf (in-memory decrypt)       │  1. Extract facts (LLM)   │
│   text / auto / OCR modes         │  2. Hybrid RRF retrieval  │
│   hierarchical chunking           │  3. Rule engine (bounds)  │
│   batched embedding → Chroma      │  4. STRIDE pipeline       │
├───────────────────────────────────┴───────────────────────────┤
│  Storage: data/documents, data/extracted, data/chroma, app.db │
└───────────────────────────────────────────────────────────────┘
        Ollama: reasoning model + embedding model (configured in the UI)
```

### Backend layers (`backend/src/ase_security_review/`)

| Layer | Role |
|---|---|
| `controller/` | Thin FastAPI routers + Pydantic request/response schemas |
| `usecase/` | Application logic: ingestion, retrieval, fact extraction, threat pipeline, chunking, PDF extraction, settings |
| `repository/` | Port interfaces (ABCs) + SQLite implementations + JSON serialization |
| `data/` | Infrastructure: SQLite engine/ORM, Chroma store, Ollama HTTP client, file store |
| `domain/` | Entities, enums, and the pure rule engine |
| `config/` | `settings.py` (env + business defaults) and `compliance.yaml` (rules) |
| `di.py` | Composition root (dependency injection container) |

---

## Requirements

- macOS / Linux, **Python 3.13+** (managed via [`uv`](https://docs.astral.sh/uv/))
- **Node.js 20+** and pnpm/npm (for the frontend)
- **Ollama** installed and running (`ollama serve`)
- Optional: **Tesseract** for OCR of scanned PDFs
  (`brew install tesseract tesseract-lang`)

> `uv sync` installs everything automatically, including **PyMuPDF** (used to read form-field
> selections from Confluence PDF exports).

---

## Setup

### 1. Ollama models

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M   # reasoning
ollama pull qwen3-embedding:0.6b         # embeddings (multilingual EN/ID)
```

The models are selected in the **Settings** page of the UI.

### 2. Backend (uv)

```bash
cd backend
cp .env.example .env          # infrastructure config (Ollama URL, data dir, host/port)
uv sync
uv run pytest                 # run the test suite
uv run ase-security-review    # or: uv run uvicorn ase_security_review.main:app --port 8000
```

### 3. Frontend (Vite + React)

```bash
cd frontend
pnpm install
pnpm build                    # builds to frontend/dist — served by the backend automatically
pnpm dev                      # dev mode with proxy to :8000 (http://localhost:5173)
```

If `frontend/dist` exists, the backend serves the UI at `http://127.0.0.1:8000/`. In development
you can instead run `pnpm dev` and open `http://localhost:5173`.

---

## Usage

### Add SOP / policies / previous reviews (the knowledge base)

Upload PDFs via the **Knowledge Base** page (choose type: SOP / Policy / Previous, and an extraction
mode: `auto` / `text` / `ocr`). There is no drop folder — ingestion is UI-only.

- **Locked PDF?** It appears as *Needs password*. Enter the password once in the UI — used in
  memory only, never stored. Re-indexing later needs no password.
- **Scanned PDF?** In `auto` mode a PDF whose text density is too low is flagged *Needs OCR* —
  click **Run OCR** (requires Tesseract). You can also force `ocr` mode.
- **Updating a document?** Re-uploading a file with the same name but new content replaces it
  (old chunks are removed and re-indexed). Identical content is skipped.

### Run a review

1. Open **New Review**, upload the **FRD** and **NFRD** (PDF, Markdown, or TXT; add a password if a PDF is locked).
2. The agent runs the **staged threat-model pipeline**:
   1. **Read diagrams** — PDF pages containing images (e.g. use-case/architecture diagrams) are rasterized
      and understood by a vision-capable model. (Skips gracefully if no images or the model isn't
      multimodal — diagrams aren't required for the rest to run.)
   2. **Understand requirement** — what information is submitted, by whom, where it goes, who approves.
   3. **Architecture & trust boundaries** — components, data flows, entry points, integrations, trust boundaries.
   4. **Identify assets** — what is being protected, grounded in the knowledge base (SOP/policy/previous reviews).
   5. **STRIDE threat modelling** — concrete threats per element/flow/trust boundary with severity.
   6. **Determine the security test** — `none | dast | pentest` + scope from the STRIDE findings, bounded by
      the deterministic rules.
3. Open the review to see each stage's artifact (requirement, trust boundaries, assets, STRIDE threat
   table), the **verdict** + scope, and the human override controls. Changing **exposure** or
   **change scope** re-runs the whole pipeline with the corrected context.

> The review is **change-scoped**: the agent analyzes what the FRD change introduces or modifies
> (requirement, architecture & trust boundaries, assets, STRIDE threats, and test scope), using the
> rest of the application as background context only. The **change scope is free text**, decided by
> the LLM (the explicit FRD statement when present, otherwise a summary of what the FRD describes)
> and overridable by the reviewer. The deterministic rules remain **hard bounds**
> on the final verdict: intranet/internal apps are capped at DAST and internet/public apps require at
> least DAST. Toggle **Enable rule engine** in the Settings page to keep them dormant
> (STRIDE/LLM decides without bounds).

### The output

```jsonc
{
  "requires_pentest": true,
  "test_level": "pentest",              // pentest | dast | none
  "classification_reason": "...",       // cites STRIDE threats, trust boundaries, assets
  "risk_factors": ["..."],
  "scope": {
    "in_scope": ["payment API", "auth flows"],
    "out_of_scope": ["infrastructure"],
    "test_methods": ["OWASP ASVS L2", "API scanning", "manual authz testing"],
    "environments": ["staging pre-release"],
    "effort_estimate": "3-5 person-days"
  }
}
```

---

## Configuration

### Infrastructure — `backend/.env`

Copy `backend/.env.example` to `backend/.env`. Only deployment-level settings live here:

```dotenv
ASE_OLLAMA_BASE_URL=http://127.0.0.1:11434
# ASE_REQUEST_TIMEOUT_SEC=300        # unset = no timeout (recommended for slow local models)
ASE_DATA_DIR=data
ASE_HOST=127.0.0.1
ASE_PORT=8000
ASE_CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
ASE_ASYNCIO_DEBUG=false
ASE_LOG_LEVEL=INFO
```

### Business logic — **Settings page** (stored in the DB, applied without restart)

Edited in the UI, validated, persisted in `data/app.db`, and applied to running components:

- **Models**: reasoning + embedding model (dropdowns of installed Ollama models) and embedding dimension
  (auto-probed). Changing the embedding model triggers a knowledge-base re-index.
- **Generation**: temperature, max tokens, context window (`num_ctx`).
- **Thinking**: per-step reasoning toggle (fact extraction, diagrams, requirement, architecture, assets, threats, decision).
- **Extraction & diagrams**: default mode, OCR threshold/language, diagram DPI, max diagram pages.
- **Retrieval & chunking**: chunk size/overlap, embedding batch size, retrieval top-k, review max input chars.
- **Policy**: enable/disable the rule engine.

### `backend/config/compliance.yaml`

- **`compliance.rules`** — the deterministic rule engine. Two exposure-based **hard-bound** rules:
  - **R-06** internet/public-facing → `dast` **floor** (never below DAST; STRIDE/LLM can still escalate to `pentest`).
  - **R-11** intranet/internal-only → `dast` with `cap: dast` (intranet is always DAST-only, even if
    STRIDE finds critical threats or the LLM suggests pentest).
  Each rule matches on `data_classes`, `keywords`, `features`, and/or `exposure`
  extracted from the FRD/NFRD and mandates a `test_level` (`pentest | dast | none`). Fired rules and
  any rule-bound violations by the agent are shown in every report.

---

## Security model for passwords

- PDF passwords are accepted over the local API and held **only in memory** while decrypting.
- They are never written to disk, SQLite, Chroma, logs, or sent to the LLM.
- The decrypted **content** is cached as plaintext (`data/extracted/<id>.txt`) so re-indexing and
  vector rebuilds never require the password again. (For OCR of a locked PDF, a decrypted PDF copy
  is written temporarily and removed after OCR; it carries the same trust as the plaintext cache.)
- If you prefer to encrypt even the extracted plaintext at rest, add a local
  [`cryptography`](https://cryptography.io) Fernet key — the cache files are plaintext by default.

---

## API surface

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Ollama status, models, indexed chunk count |
| GET | `/api/models` | Available models + configured models |
| GET/POST | `/api/documents` | List / upload knowledge-base documents |
| POST | `/api/documents/reindex` | Rebuild the vector index from cached plaintext |
| POST | `/api/documents/{id}/unlock` | Unlock a password-protected PDF (in-memory only) |
| POST | `/api/documents/{id}/ocr` | Run OCR on a scanned document |
| GET | `/api/documents/{id}/progress` | Ingestion status for one document |
| DELETE | `/api/documents/{id}` | Remove a document + its chunks |
| GET/PUT | `/api/settings` | Read / update business-logic settings |
| POST | `/api/settings/reset` | Reset business settings to defaults |
| POST | `/api/reviews` | Upload FRD+NFRD (PDF/MD/TXT) and start a review; optional `exposure` form field |
| GET | `/api/reviews` / `/api/reviews/{id}` | Review history / detail (audit trail) |
| PATCH | `/api/reviews/{id}/exposure` | Confirm/override the app exposure (recomputes rules) |
| DELETE | `/api/reviews/{id}` | Delete a review from history |
| PATCH | `/api/reviews/{id}/decision` | Set the human final decision |

---

## Testing

```bash
cd backend
uv run pytest            # 35 tests: rule engine, chunking, extraction (encrypted PDFs),
                         # ingestion, review pipeline, retrieval, HTTP API (in-memory fakes)
```

Test fixtures (`tests/fixtures/make_pdf.py`) generate plain and password-protected PDFs with
`reportlab` + `pypdf` — no network needed.

---

## Project layout

```
backend/
  .env.example                  # infrastructure configuration template (copy to .env)
  config/compliance.yaml        # deterministic decision rules
  src/ase_security_review/
    main.py                     # FastAPI app (serves built frontend too)
    di.py                       # dependency injection container
    config/ domain/ repository/ data/ usecase/ controller/
  tests/                        # pytest suite + PDF fixture generator
  data/documents/               # uploaded knowledge-base PDFs (via the UI)

frontend/
  src/pages/                    # KnowledgeBase, NewReview, ReviewDetail, History, Settings
  src/components/               # Layout, Dropzone, PasswordDialog, Stepper, VerdictBanner, ...
  src/api/client.ts             # typed API client
```
