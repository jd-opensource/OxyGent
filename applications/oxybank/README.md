# OxyBank

A lightweight **data annotation & retrieval platform** for building AI training / RAG datasets. OxyBank pairs Elasticsearch for structured search with Vearch for vector similarity, so a single "Bank" can serve both classical keyword/filter queries and semantic search — while giving humans (and annotation agents) a clean workbench to curate the data.

Ships with a FastAPI backend, a jQuery-based single-page frontend, JWT auth, per-bank retrieval APIs, an AI-assisted template designer, and a pluggable annotation-agent framework.

**中文版**: 见 [README_zh.md](README_zh.md)

---

## Feature highlights

- **Banks** — data containers with a user-defined schema. Pick from built-in scene templates (QA / Memory / Customer-service FAQ / Knowledge base / Product catalog) or design a custom schema.
- **Dual-store retrieval** — Elasticsearch (structured filters, full-text) + Vearch (embedding similarity). Any field can be flagged as a vector field; multi-vector search is supported natively.
- **Custom retrieval APIs** — per-bank, admin-editable, each API is a mini-endpoint definition (conditions, modes, output fields).
- **Annotation workbench** — sample list with progress bar, dynamic status filter, template-driven forms (radio / select / textarea / conditional show_when), previous / next navigation, version history.
- **Global template pool** — annotation templates are shared across banks; each sample references its template by name via `sys_template`.
- **AI template designer** — describe what you want in natural language; the LLM generates a template JSON aware of your bank schema.
- **Annotation agents** — external services registered per bank, triggered when a sample's `sys_status` changes to a configured value. Async, timeout-aware, with full execution logs.
- **Document ingestion** — upload `.txt / .md / .pdf / .docx` (auto-chunked when `sys_chunk` is enabled) or `.csv / .xlsx` (each row → sample).
- **i18n** — full Chinese + English coverage, live language switching.

---

## Requirements

- Python 3.10+
- Elasticsearch 7.x (running and reachable)
- Vearch 3.3.x (only needed if any bank uses vector search)
- A Triton (or OpenAI-compatible) embedding endpoint (only needed for vector search)
- An OpenAI-compatible chat-completions endpoint (only needed for the AI template designer / annotation-agent calls)

---

## Repository layout

```
OxyBank/
├── app/              # FastAPI backend (routers, services, storage, auth)
├── web/              # Frontend (static HTML/CSS/JS, jQuery)
├── deployment/       # Dockerfile + startup scripts
├── config.json       # Runtime configuration (see below)
├── requirements.txt  # Python dependencies
└── run.py            # Entry point (spawns uvicorn)
```

Backend code lives directly under `app/` — no wrapping `backend/` folder.

---

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Point the config at your infrastructure

`config.json` is keyed by **environment**. On startup the loader applies the `default` section as a baseline, then deep-merges the section named by the `OXYBANK_ENV` environment variable on top. Fields not listed in the environment section inherit from `default`.

```json
{
  "default": {
    "es":     { "index_prefix": "oxybank" },
    "vearch": { "db_name": "oxybank_db_base" },
    "triton": { "url": "http://.../v2/models/embedding/infer" },
    "openai": { "api_key": "sk-...", "base_url": "https://api.openai.com/v1", "model": "text-embedding-3-small" },
    "llm":    { "api_key": "EMPTY", "base_url": "http://.../v1/chat/completions", "model": "qwen25-32b-native" },
    "annotation": { "max_concurrency": 5, "agent_timeout": 120 },
    "chunking":   { "chunk_size": 512, "chunk_overlap": 50 },
    "server": { "host": "0.0.0.0", "port": 8080 },
    "auth":   { "secret_key": "change-me", "enabled": false }
  },
  "development": {
    "es":     { "hosts": ["dev-es:9200"], "user": "dev", "password": "..." },
    "vearch": { "master_url": "http://dev-vearch-master", "router_url": "http://dev-vearch-router" },
    "auth":   { "enabled": false }
  },
  "production": {
    "es":     { "hosts": ["prod-es:9200"], "user": "prod", "password": "..." },
    "vearch": { "master_url": "http://prod-vearch-master", "router_url": "http://prod-vearch-router" },
    "auth":   { "secret_key": "<strong-random-string>", "enabled": true }
  }
}
```

**Which environment gets loaded** is decided by the `OXYBANK_ENV` env var (default: `development`). Merging is deep — `production.es` overrides only the fields listed there, `index_prefix` and `timeout` still come from `default.es`. An unknown env value simply falls back to `default`.

- `auth.enabled: false` — everyone hits the API as an anonymous admin. Fine for local dev; **flip to true in production** and change `secret_key`.
- Only fill in `vearch`/`triton`/`llm` if you plan to use vector search / AI features. The rest of the app still works without them.

### 3. Run the server

```bash
# Local development — OXYBANK_ENV defaults to "development"
python run.py

# Production — pick up the "production" section from config.json
OXYBANK_ENV=production python run.py
```

For Docker, set the env var in the container:

```dockerfile
ENV OXYBANK_ENV=production
```

Serves on `http://0.0.0.0:8080` by default (both the API and the frontend).

On first startup a default admin user `admin/admin` is created (if `auth.enabled` was ever true and the users index is empty). Change the password from the Users page.

Open your browser at `http://localhost:8080` and log in.

---

## Core concepts

### Bank

A bank is a container for one dataset. It has:

- a **schema** (list of user-defined fields — types: `text`, `keyword`, `integer`, `float`, `string`)
- an optional **`sys_chunk` field** if you plan to upload documents that get split into chunks (used with vector search)
- one or more **retrieval APIs** (see below)
- an **embedding backend** if any field uses vector mode

Create a bank from the Banks page. Pick a **scene template** to get a sensible starting schema, or use "Custom" to define fields yourself.

### System fields (`sys_*`)

Every sample carries these platform-managed fields on top of the user-defined schema. You rarely need to write them by hand — most are set / advanced by the platform. Custom fields you define in the Bank schema live alongside them.

**Identity (auto-assigned, don't touch)**

| Field | Purpose |
|---|---|
| `sys_sample_id` | Sample UUID. Never changes. |
| `sys_document_id` | UUID of the document this sample came from (one document → many samples). |
| `sys_create_time` / `sys_update_time` | Timestamps (UTC ISO 8601). |

**Workflow — the fields you'll actually set**

| Field | Purpose |
|---|---|
| `sys_status` | Workflow state. Canonical tokens: `Imported`, `To Assign`, `Assigned`, `To Annotate`, `Annotated`, `Rejected`, `Published`, `Ignored`. Custom values allowed. Drives annotation-agent triggers. |
| `sys_template` | The annotation template to render for this sample. Accepts the template UUID or its `name` (name is recommended). |
| `sys_executor` | Username of the annotator this sample is assigned to. |
| `sys_priority` | Sort priority in the annotation workbench (integer; smaller = shown first). |
| `sys_overview` | Short human-readable summary (shown in the sample list). |
| `sys_remarks` | Free-text remarks (e.g. reject reason). |
| `sys_chunk` | Text chunk. Only present when the bank was created with "enable document chunking". This is the one `sys_*` field that supports vector search. |

**State-transition helpers (auto-managed, read-only from your POV)**

| Field | Purpose |
|---|---|
| `sys_next_status` / `sys_next_template` / `sys_next_executor` | The state the sample should advance to on the next save. Set by an annotation agent's output; consumed automatically by the sample-update endpoint. |
| `sys_prev_status` / `sys_prev_template` / `sys_prev_executor` | The state the sample was in before its most recent update. Auto-snapshotted on every sample write (human edit or agent) — the annotation UI's "reject" button uses these to restore the previous state. Don't set these by hand. |

### Retrieval modes

When you define a retrieval API, each field is set to one of:

- `exact` — value equality (`term`)
- `in` — value must be in a list (`terms`)
- `fuzzy` — full-text match (`match` with fuzziness)
- `vector` — embed the query text and rank by similarity against the field's `{field}_vector` column

Multiple vector fields can be combined in one API — Vearch sums their distances.

### Templates

Templates define the annotation form (which fields are editable, radio options, conditional visibility). They are **global** — every bank can use every template. Reference by `name` (globally unique) or UUID.

Two are built in:
- `builtin_qa` — a satisfied/unsatisfied radio + optional reason textarea over `query` + `answer`
- `builtin_business` — a business-domain radio picker over `sys_chunk`

Add more from the Templates page, either by hand (JSON editor) or via the AI designer (describe what you want, it generates the JSON, you tweak and save).

### Annotation agents

Register an external HTTP service on the Agents page with:
- a **service URL** (a POST endpoint that takes a sample and returns modifications)
- **Trigger Statuses** (one or more `sys_status` values)

When a sample transitions into any trigger status, OxyBank calls the agent asynchronously. The agent's response is applied as a sample update; the change flows through the same status-event pipeline, so agents can chain.

### Storage split

- **Elasticsearch** — the authoritative store. Every field of every sample.
- **Vearch** — a slim projection: vector columns + the filter fields referenced by retrieval APIs. Only samples with at least one non-empty vector field are written here.

The frontend hides this split. Retrieval APIs, deposits, and sample updates all keep the two stores in sync automatically — you don't call any "rebuild index" endpoint in normal use.

---

## Typical workflows

### A. Upload and annotate a small dataset

1. **Create a bank** — pick a scene (e.g. QA) or a custom schema.
2. **Upload data** — on the Data page, drag a `.csv` / `.xlsx` (columns must match your schema) or a `.pdf` / `.docx` / `.txt` / `.md` (if `sys_chunk` is enabled, the file is auto-chunked).
3. **Open the Annotation workbench** — filter by status, click a sample, fill the form, hit Save. The form is driven by the template referenced in `sys_template`.
4. **Optional: register an annotation agent** — automate part of the flow. E.g. "when status → `To Annotate`, call my LLM to draft a label".
5. **Query the data** — use the API Test page to inspect the auto-generated retrieval endpoints, copy a curl / Python snippet for integration.

### B. Add a retrieval endpoint mid-project

1. Banks page → edit bank → add a new retrieval API. Define its conditions (fields + modes) and output fields.
2. The new endpoint appears on the API Test page immediately. Existing samples are backfilled to the vector index in the background if you added a vector field.

### C. Integrate with an LLM app

Use `GET /api/banks/{bank}/list_banks` (or the button on the API Test page) — it returns a JSON tool description that most agent frameworks (LangChain, our OxyGent SDK, etc.) can consume directly.

---

## Frontend pages

| Page | Purpose |
|---|---|
| **Banks** | Create / list / delete banks |
| **Data** | Upload documents, browse and edit samples |
| **Annotation** | Sample-by-sample annotation workbench (annotators land here by default) |
| **Agents** | Register annotation agents, view flow diagram, inspect execution logs |
| **API Test** | Interactive docs for the bank's retrieval / deposit APIs |
| **Templates** | Manage annotation templates (edit JSON, AI-assist, preview with real samples) |
| **Users** | User management (admin only) |
| **Config** | System configuration (admin only) |
| **Help** | Built-in user guide |

Annotators (role `annotator`) only see the Annotation and Help pages.

---

## API surface (short version)

All endpoints are prefixed `/api`:

| Group | Base path |
|---|---|
| Auth | `/api/auth/*` |
| Banks | `/api/banks` |
| Documents | `/api/banks/{bank_name}/documents` |
| Samples | `/api/banks/{bank_name}/samples` |
| Retrieval | `/api/banks/{bank_name}/{api_id}/withdraw`, plus the auto `withdraw` / `deposit` / `deposit_batch` / `list_banks` under `/api/banks/{bank_name}/` |
| Templates | `/api/banks/{bank_name}/templates` (templates are actually global; the bank path is preserved for URL compatibility) |
| Agents | `/api/banks/{bank_name}/agents` |
| Users | `/api/users` |
| Config | `/api/config` |

The API Test page in the frontend renders live docs (URL, params, curl snippet, Python snippet, Try-it) for every retrieval API on the currently-selected bank.

---

## Common gotchas

- **PDF/DOCX upload puts the whole file into one sample.** Enable `has_sys_chunk` when creating the bank, otherwise files aren't chunked.
- **CSV/XLSX columns must match the bank schema field names.** Extra columns are ignored, missing columns become empty.
- **Vector search returns 0 rows even though ES has samples.** The vector field was empty at deposit time (e.g. samples deposited before an annotation agent filled the field in) — Vearch skips samples with empty vector fields. Once the field is later filled in (via sample update or agent), the sample is auto-upserted to Vearch, no manual step required.
- **`sys_template` value doesn't render the right form.** The template resolver first tries UUID lookup, then falls back to name lookup within the global pool. Make sure the value is exactly one of those — spaces / casing matter.
- **Built-in templates are read-only.** Clone them from the Templates page to derive an editable copy.

---

## Development

```bash
# Dev-run with the same command production uses
python run.py
```

- The frontend is plain HTML/CSS/JS + jQuery, served by FastAPI's static mounts (`/css`, `/js`) and a catch-all route to `web/*.html`. No build step.
- Backend hot-reload is off by default (see `run.py`). Restart on code changes.
- The frontend caches `oxybank-token` and `oxybank-user` in `localStorage`. Clear those to force a re-login.

### Adding a new retrieval mode / status / field type

- **Retrieval mode** — teach `app/services/retrieval_service.py` how to translate the mode into an ES clause + a Vearch filter (if applicable); add to the mode dropdown in `web/js/banks.js`.
- **Canonical status** — add to `CANONICAL_STATUSES` in `web/js/agents.js` and give it a color in `STATUS_COLOR_OVERRIDES` (`web/js/annotation.js`). No backend change needed — `sys_status` is a free-form string.
- **Field type** — extend `app/services/bank_service.py::_build_vearch_properties` if the new type needs a special Vearch column; teach the schema-fields UI in `web/js/banks.js` about the new type.
