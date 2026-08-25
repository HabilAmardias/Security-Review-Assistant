# ASE Security Review Agent

An **on-premise, local RAG/agent** that reviews software requirements and decides whether an
application needs a **penetration test or only DAST** — with reasoning and a security test scope.

It takes an **FRD** (Functional Requirements Document) and an **NFRD** (Non-Functional
Requirements Document) and returns:

1. **Is a pentest needed, or is DAST sufficient?** (`pentest | dast | none`)
2. **Reasoning** — citing the data classes, your SOP/policy rules that fired, and the relevant
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
│  Ingestion pipeline               │  Review agent             │
│   drop folder watcher             │  1. Extract facts (LLM)   │
│   pypdf (in-memory decrypt)       │  2. Hybrid RRF retrieval  │
│   text / auto / OCR modes         │  3. Rule engine (rules)   │
│   hierarchical chunking           │  4. LLM decision (JSON)   │
│   batched embedding → Chroma      │  5. Conflict check        │
├───────────────────────────────────┴───────────────────────────┤
│  Storage: data/dropbox, data/extracted, data/chroma, app.db   │
└───────────────────────────────────────────────────────────────┘
        Ollama: gemma (reasoning) + gemma-embedding (embeddings)
```

### Backend layers (`backend/src/ase_security_review/`)

| Layer | Role |
|---|---|
| `controller/` | Thin FastAPI routers + Pydantic request/response schemas |
| `usecase/` | Application logic: ingestion, folder watcher, retrieval, fact extraction, review pipeline, chunking, PDF extraction |
| `repository/` | Port interfaces (ABCs) + SQLite implementations + JSON serialization |
| `data/` | Infrastructure: SQLite engine/ORM, Chroma store, Ollama HTTP client, file store |
| `domain/` | Entities, enums, and the pure rule engine |
| `config/` | `config.yaml` + `compliance.yaml` loaders |
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
ollama pull qwen2.5:7b-instruct-q4_K_M   # reasoning (edit config to choose another)
ollama pull qwen3-embedding:0.6b         # embeddings (multilingual EN/ID)
```

The models are configurable — see `backend/config/config.yaml`.

### 2. Backend (uv)

```bash
cd backend
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

Drop PDFs into the drop folder — the background watcher indexes them automatically:

```
backend/data/dropbox/
  sop/        # e.g. SOP_PentestSelection.pdf
  policy/     # e.g. POLICY_DataClassification.pdf
  previous/   # e.g. PREV_Review_PaymentPortal_2024.pdf (becomes precedent)
```

Or upload via the **Knowledge Base** page (choose type: SOP / Policy / Previous, and an extraction
mode: `auto` / `text` / `ocr`).

- **Locked PDF?** It appears as *Needs password*. Enter the password once in the UI — used in
  memory only, never stored. Re-indexing later needs no password.
- **Scanned PDF?** In `auto` mode a PDF whose text density is too low is flagged *Needs OCR* —
  click **Run OCR** (requires Tesseract). You can also force `ocr` mode.
- **Updating a document?** Re-dropping a file with the same name but new content replaces it
  (old chunks are removed and re-indexed). Identical content is skipped.

### Run a review

1. Open **New Review**, upload the **FRD** and **NFRD** (PDF, Markdown, or TXT; add a password if a PDF is locked).
2. The agent: extracts structured facts → retrieves your SOP/policy/precedent → fires rules →
   produces a JSON decision → checks for conflicts with the rules.
3. Open the review to see the **verdict**, **reasoning**, **scope**, fired rules, and retrieved
   sources. If the rule engine and the LLM disagree, a conflict banner appears so a human can make
   the final call (override controls included).

### The output

```jsonc
{
  "requires_pentest": true,
  "test_level": "pentest",              // pentest | dast | none
  "classification_reason": "...",       // cites data classes, fired rules, retrieved sources
  "risk_factors": ["..."],
  "scope": {
    "in_scope": ["web app", "REST APIs", "auth flows"],
    "out_of_scope": ["infrastructure"],
    "test_methods": ["OWASP ASVS L2", "API scanning", "manual authz testing"],
    "environments": ["staging pre-release"],
    "effort_estimate": "3-5 person-days"
  }
}
```

---

## Configuration

### `backend/config/config.yaml`

```yaml
llm:
  base_url: "http://127.0.0.1:11434"
  reasoning_model: "qwen2.5:7b-instruct-q4_K_M"   # change freely
  embedding_model: "qwen3-embedding:0.6b"          # change freely; must match embedding_dim
  embedding_dim: 1024                              # output size of the embedding model
  num_ctx: 16384        # context window; Ollama's 4096 default truncates long reviews
  enable_thinking: false  # keep false for JSON output; qwen3.x can burn tokens on reasoning
```

> Changing the embedding model: update `embedding_dim` to the new model's output size. On the next
> restart the vector index is rebuilt automatically from the cached plaintext (no PDFs or passwords
> needed), or use the **Rebuild index** button on the Knowledge Base page.

extraction:
  default_mode: "auto"        # auto | text | ocr
  auto_detect_threshold: 50   # chars/page below this → flag NEEDS_OCR
  ocr_language: "eng"         # tesseract language, e.g. "eng", "ind", "eng+ind"

data_dir: "data"
poll_interval_sec: 10         # drop folder scan interval
chunk_size: 900
chunk_overlap: 120
embed_batch_size: 64
retrieval_top_k: 6
review_max_input_chars: 60000 # per-doc input budget for the reasoning LLM
```

### `backend/config/compliance.yaml`

- **`compliance.rules`** — the deterministic rule engine. Only the two exposure-based decision
  rules are defined:
  - **R-06** internet/public-facing → `dast` floor (whether a pentest is also needed is left to the
    review analysis — the LLM can recommend `pentest`, which then surfaces as a rule-vs-LLM conflict
    for a human to confirm).
  - **R-11** intranet/internal-only → `dast` with `cap: dast` (intranet is always DAST-only, even if
    the LLM suggests pentest).
  Each rule matches on `data_classes`, `keywords`, `features`, and/or `exposure` extracted from the
  FRD/NFRD and mandates a `test_level` (`pentest | dast | none`). Fired rules are shown in every report.

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
| POST | `/api/documents/rescan` | Trigger a drop-folder scan |
| POST | `/api/documents/{id}/unlock` | Unlock a password-protected PDF (in-memory only) |
| POST | `/api/documents/{id}/ocr` | Run OCR on a scanned document |
| GET | `/api/documents/{id}/progress` | Ingestion status for one document |
| DELETE | `/api/documents/{id}` | Remove a document + its chunks |
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
  config/config.yaml            # model + tuning configuration
  config/compliance.yaml        # deterministic decision rules
  src/ase_security_review/
    main.py                     # FastAPI app (serves built frontend too)
    di.py                       # dependency injection container
    config/ domain/ repository/ data/ usecase/ controller/
  tests/                        # pytest suite + PDF fixture generator
  data/dropbox/{sop,policy,previous}   # <-- drop your documents here

frontend/
  src/pages/                    # KnowledgeBase, NewReview, ReviewDetail, History, Settings
  src/components/               # Layout, Dropzone, PasswordDialog, Stepper, VerdictBanner, ...
  src/api/client.ts             # typed API client
```
