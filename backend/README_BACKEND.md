# Infiniti Solutions — Steel Detailing System · Backend README

> **FastAPI · LangGraph · PostgreSQL · ChromaDB · Celery · Ollama (Local LLM)**
> Local-first. No API dependency. Engineering-governed. Fully traceable.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Tech Stack](#2-tech-stack)
3. [Project Structure](#3-project-structure)
4. [Installation & Setup](#4-installation--setup)
5. [Environment Configuration](#5-environment-configuration)
6. [Database Setup — PostgreSQL](#6-database-setup--postgresql)
7. [Vector DB Setup — ChromaDB](#7-vector-db-setup--chromadb)
8. [LLM Setup — Ollama](#8-llm-setup--ollama)
9. [ODA File Converter Setup](#9-oda-file-converter-setup)
10. [Agent Architecture — LangGraph](#10-agent-architecture--langgraph)
11. [Phase 1 Agents](#11-phase-1-agents)
12. [Phase 2 Agents](#12-phase-2-agents)
13. [Phase 3 Agents](#13-phase-3-agents)
14. [Master Orchestration Agent](#14-master-orchestration-agent)
15. [Validator & Fallback Pattern](#15-validator--fallback-pattern)
16. [Data Extraction Layer (Parsers)](#16-data-extraction-layer-parsers)
17. [Learning Agent](#17-learning-agent)
18. [Output Generator Agent](#18-output-generator-agent)
19. [FastAPI Endpoints](#19-fastapi-endpoints)
20. [WebSocket — Live Tracking](#20-websocket--live-tracking)
21. [Celery — Background Jobs](#21-celery--background-jobs)
22. [PostgreSQL Schema — Full Reference](#22-postgresql-schema--full-reference)
23. [Running the Backend](#23-running-the-backend)
24. [Testing Strategy](#24-testing-strategy)
25. [Deployment Notes](#25-deployment-notes)

---

## 1. Overview

The backend is a Python-based multi-agent orchestration system. It handles:

- **Project and file management** — intake, classification, storage
- **Phase 1 master database creation** — extracting standards from 50 reference jobs
- **Phase 2 per-project AB/GA generation** — ingestion → completeness → AB → GA → validation
- **Phase 3 detailing and release** — sheeting → shop → shipping → installation → final check
- **Output generation** — DXF → DWG (via ODA) → PDF per drawing type
- **Learning system** — correction event tracking, rule proposals, similarity search
- **Live tracking** — WebSocket broadcast of stage status to React frontend

Every agent runs as a node in a LangGraph state machine. The Master Orchestration Agent controls all stage entry/exit decisions.

---

## 2. Tech Stack

| Component | Library / Tool | Version | Purpose |
|-----------|---------------|---------|---------|
| Web Framework | FastAPI | ≥0.110 | REST API + WebSocket |
| Agent Orchestration | LangGraph | ≥0.1 | Multi-agent state machines |
| LLM Engine | Ollama + `langchain-community` | latest | Local LLM inference |
| Task Queue | Celery | ≥5.3 | Async agent execution |
| Message Broker | Redis (local) | ≥7.0 | Celery broker + result backend |
| Structured DB | PostgreSQL | ≥15 | Project data, rules, events |
| ORM | SQLAlchemy + Alembic | ≥2.0 | DB access + migrations |
| Vector DB | ChromaDB | ≥0.4 | Project profile similarity search |
| DXF Generation | ezdxf | ≥1.2 | Create DXF drawing files |
| DWG Export | ODA File Converter | free | Convert DXF → DWG (R2018) |
| PDF Generation | ezdxf + matplotlib | ≥3.8 | Render DXF to PDF |
| PDF Parsing | pdfplumber | ≥0.10 | Extract text/tables from PDFs |
| PDF (image) | PyMuPDF (fitz) | ≥1.23 | Image-based PDF extraction |
| OCR | pytesseract + Tesseract | ≥0.3.10 | OCR on scanned drawing images |
| Excel Parsing | openpyxl + pandas | ≥3.1 / ≥2.0 | ETABS Excel export parsing |
| Archive | rarfile + zipfile (stdlib) | ≥4.0 | ZIP + RAR extraction |
| Config | python-dotenv | ≥1.0 | Environment variables |
| Validation | Pydantic | ≥2.0 | Request/response models |
| Logging | Python logging + structlog | ≥23 | Structured audit logging |

---

## 3. Project Structure

```
backend/
├── main.py                          # FastAPI app entry point
├── requirements.txt
├── .env                             # Environment config (gitignored)
├── alembic/                         # DB migrations
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│
├── app/
│   ├── api/                         # FastAPI routers
│   │   ├── __init__.py
│   │   ├── projects.py              # Project CRUD, file upload
│   │   ├── stages.py                # Stage control, status
│   │   ├── handoffs.py              # Handoff package endpoints
│   │   ├── outputs.py               # Output download endpoints
│   │   ├── learning.py              # Rule proposals, suggestions
│   │   └── ws.py                    # WebSocket live tracking
│   │
│   ├── orchestrator/                # Master Orchestration Agent
│   │   ├── __init__.py
│   │   ├── controller.py            # Main orchestration logic
│   │   ├── dependency_checker.py    # Stage prereq validation
│   │   ├── cascade_manager.py       # Re-run cascade logic
│   │   ├── handoff_manager.py       # Handoff package creation/validation
│   │   └── status_model.py          # PASS/FAIL/BLOCKED/ESCALATE enum
│   │
│   ├── agents/                      # All agent definitions
│   │   ├── __init__.py
│   │   │
│   │   ├── phase1/                  # Master DB creation agents
│   │   │   ├── __init__.py
│   │   │   ├── p1_01_template_extraction.py
│   │   │   ├── p1_02_field_dictionary.py
│   │   │   ├── p1_03_source_mapping.py
│   │   │   ├── p1_04_validation_rules.py
│   │   │   └── p1_05_db_consolidator.py
│   │   │
│   │   ├── phase2/                  # Per-project AB/GA agents
│   │   │   ├── __init__.py
│   │   │   ├── p2_01_ingestion.py
│   │   │   ├── p2_02_completeness.py
│   │   │   ├── p2_03_ab_generation.py
│   │   │   ├── p2_04_ga_generation.py
│   │   │   └── p2_05_abga_validation.py
│   │   │
│   │   ├── phase3/                  # Per-project detailing agents
│   │   │   ├── __init__.py
│   │   │   ├── p3_01_sheeting.py
│   │   │   ├── p3_02_shop_detail.py
│   │   │   ├── p3_03_shipping.py
│   │   │   ├── p3_04_installation.py
│   │   │   └── p3_05_final_check.py
│   │   │
│   │   └── support/                 # Support agents (always running)
│   │       ├── __init__.py
│   │       ├── validator.py         # Generic validator (used by all stages)
│   │       ├── fallback.py          # Fallback agent (one retry)
│   │       ├── checkpoint.py        # State save/restore
│   │       ├── state_tracker.py     # Job/stage/error tracking
│   │       ├── notification.py      # WebSocket push notifications
│   │       ├── escalation.py        # Escalation routing and logging
│   │       └── output_generator.py  # DXF → DWG → PDF rendering
│   │
│   ├── learning/                    # Three-level learning system
│   │   ├── __init__.py
│   │   ├── correction_listener.py   # Level 1: logs correction events
│   │   ├── rule_analyser.py         # Level 1: proposes rule updates
│   │   ├── suggestion_engine.py     # Level 2: field value suggestions
│   │   └── vector_updater.py        # Level 3: ChromaDB index updates
│   │
│   ├── parsers/                     # Data extraction layer
│   │   ├── __init__.py
│   │   ├── staad_parser.py          # STAAD Pro .std file parser (highest priority)
│   │   ├── mbs_parser.py            # MBS XML/text export parser
│   │   ├── etabs_parser.py          # ETABS Excel export parser
│   │   ├── prota_parser.py          # Prota Steel DXF + PDF parser
│   │   ├── dwg_dxf_parser.py        # ezdxf + ODA DWG/DXF parser
│   │   ├── pdf_text_parser.py       # pdfplumber text PDF parser
│   │   ├── pdf_image_parser.py      # PyMuPDF + Tesseract OCR parser
│   │   ├── archive_handler.py       # ZIP + RAR recursive extraction
│   │   └── source_classifier.py     # Classifies files by type and role
│   │
│   ├── cad/                         # CAD output generation
│   │   ├── __init__.py
│   │   ├── dxf_builder.py           # ezdxf drawing builder
│   │   ├── oda_converter.py         # ODA File Converter wrapper
│   │   ├── pdf_renderer.py          # matplotlib-based PDF renderer
│   │   └── template_populator.py    # Applies master DB templates to DXF
│   │
│   ├── db/                          # Database layer
│   │   ├── __init__.py
│   │   ├── session.py               # SQLAlchemy session factory
│   │   ├── models.py                # All ORM models
│   │   └── crud/                    # CRUD operations per entity
│   │       ├── projects.py
│   │       ├── stages.py
│   │       ├── handoffs.py
│   │       ├── validation.py
│   │       ├── learning.py
│   │       └── master_db.py
│   │
│   ├── schemas/                     # Pydantic request/response models
│   │   ├── __init__.py
│   │   ├── project.py
│   │   ├── stage.py
│   │   ├── handoff.py
│   │   ├── validation.py
│   │   ├── output.py
│   │   └── learning.py
│   │
│   ├── tasks/                       # Celery task definitions
│   │   ├── __init__.py
│   │   ├── celery_app.py            # Celery app instance + config
│   │   ├── phase1_tasks.py          # Phase 1 async tasks
│   │   ├── phase2_tasks.py          # Phase 2 async tasks
│   │   ├── phase3_tasks.py          # Phase 3 async tasks
│   │   └── learning_tasks.py        # Learning agent background tasks
│   │
│   ├── vector/                      # ChromaDB interface
│   │   ├── __init__.py
│   │   ├── chroma_client.py         # ChromaDB client setup
│   │   ├── embedder.py              # Project profile → vector embedding
│   │   └── searcher.py              # Similarity search queries
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py              # App config (loaded from .env)
│   │   └── constants.py             # Stage codes, status enums, failure classes
│   │
│   └── utils/
│       ├── __init__.py
│       ├── file_utils.py            # File path helpers, UUID generation
│       ├── traceability.py          # Source traceability matrix builder
│       └── audit_logger.py          # Structured audit log writer
│
├── tests/
│   ├── unit/
│   │   ├── test_parsers.py
│   │   ├── test_validators.py
│   │   └── test_orchestrator.py
│   ├── integration/
│   │   ├── test_phase1_pipeline.py
│   │   ├── test_phase2_pipeline.py
│   │   └── test_phase3_pipeline.py
│   └── fixtures/
│       ├── sample_std_file.std
│       ├── sample_mbs_export.xml
│       └── sample_etabs_export.xlsx
│
└── scripts/
    ├── init_db.py                   # Create all tables from models
    ├── seed_phase1.py               # Load 50 reference jobs and run Phase 1
    └── check_oda.py                 # Verify ODA File Converter is reachable
```

---

## 4. Installation & Setup

### Prerequisites

```bash
# Python 3.11+
python --version

# PostgreSQL 15+
psql --version

# Redis 7+
redis-server --version

# Tesseract OCR (for image PDFs)
tesseract --version

# Node.js (for ODA File Converter — not needed if using Windows installer)
# ODA File Converter installed separately (see Section 9)
```

### Python Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### requirements.txt (Key Packages)

```txt
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
langgraph>=0.1.0
langchain>=0.1.0
langchain-community>=0.0.20
celery>=5.3.6
redis>=5.0.1
sqlalchemy>=2.0.0
alembic>=1.13.0
psycopg2-binary>=2.9.9
chromadb>=0.4.22
ezdxf>=1.2.0
matplotlib>=3.8.0
pdfplumber>=0.10.0
pymupdf>=1.23.0
pytesseract>=0.3.10
openpyxl>=3.1.0
pandas>=2.0.0
rarfile>=4.1
python-dotenv>=1.0.0
pydantic>=2.0.0
structlog>=23.0.0
python-multipart>=0.0.9
websockets>=12.0
```

---

## 5. Environment Configuration

Create `.env` in `backend/`:

```env
# ── Application ──────────────────────────────────────────────
APP_NAME=Infiniti_Steel_Agent_System
APP_ENV=development                   # development | production
SECRET_KEY=your-secret-key-here
DEBUG=true

# ── PostgreSQL ────────────────────────────────────────────────
DATABASE_URL=postgresql://infiniti:password@localhost:5432/steel_agent_db
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# ── Redis (Celery broker) ─────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# ── ChromaDB ─────────────────────────────────────────────────
CHROMA_PERSIST_DIR=./data/chromadb
CHROMA_COLLECTION_PROJECT_PROFILES=project_profiles
CHROMA_COLLECTION_TEMPLATES=template_patterns

# ── Ollama (Local LLM) ────────────────────────────────────────
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3                   # llama3 | mistral | codellama
OLLAMA_TIMEOUT=120

# ── ODA File Converter ────────────────────────────────────────
ODA_CONVERTER_PATH=C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe
# Linux: ODA_CONVERTER_PATH=/home/user/Apps/ODAFileConverter.AppImage

# ── File Storage ─────────────────────────────────────────────
STORAGE_BASE_PATH=./data/projects
REFERENCE_JOBS_PATH=./data/reference_jobs     # 50 reference jobs folder
TEMP_PATH=./data/temp

# ── Learning System ───────────────────────────────────────────
LEARNING_CORRECTION_THRESHOLD=5              # errors before rule proposal
LEARNING_PERIODIC_TRIGGER_COUNT=10          # new projects before Phase 1 re-run flag

# ── WebSocket ─────────────────────────────────────────────────
WS_PING_INTERVAL=30
WS_MAX_CONNECTIONS=50
```

---

## 6. Database Setup — PostgreSQL

### Create Database

```sql
CREATE USER infiniti WITH PASSWORD 'password';
CREATE DATABASE steel_agent_db OWNER infiniti;
GRANT ALL PRIVILEGES ON DATABASE steel_agent_db TO infiniti;
```

### Run Migrations

```bash
cd backend
alembic upgrade head
```

### Initialize Tables (First Run)

```bash
python scripts/init_db.py
```

### Full PostgreSQL Schema

**Core Project Tables**

```sql
-- projects
CREATE TABLE projects (
    project_uuid        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id         VARCHAR(50) NOT NULL,     -- e.g. Q-157
    project_name        VARCHAR(255) NOT NULL,
    location            VARCHAR(100),             -- e.g. Palghar
    project_type        VARCHAR(100),             -- Industrial / Commercial etc.
    client_name         VARCHAR(255),
    start_date          DATE,
    outputs_required    JSONB,                    -- {ab, ga, shop, sheeting, shipping, installation}
    status              VARCHAR(50) DEFAULT 'created',
    created_at          TIMESTAMP DEFAULT NOW(),
    approved_at         TIMESTAMP,
    approved_by         VARCHAR(100)
);

-- files
CREATE TABLE files (
    file_internal_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_uuid        UUID REFERENCES projects(project_uuid),
    original_filename   VARCHAR(500) NOT NULL,
    stored_path         TEXT NOT NULL,
    file_extension      VARCHAR(20),
    file_category       VARCHAR(100),   -- design_file | cad | pdf | archive | unsupported
    source_application  VARCHAR(100),   -- MBS | STAAD | ETABS | PROTA | UNKNOWN
    likely_role         VARCHAR(100),   -- governing | supporting | template | irrelevant
    revision_indicator  VARCHAR(50),
    classification_conf DECIMAL(4,2),   -- 0.00 to 1.00
    upload_timestamp    TIMESTAMP DEFAULT NOW(),
    processing_status   VARCHAR(50) DEFAULT 'pending'
);

-- project_stages
CREATE TABLE project_stages (
    stage_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_uuid        UUID REFERENCES projects(project_uuid),
    stage_code          VARCHAR(10) NOT NULL,     -- P2-01, P2-02, P3-01 etc.
    stage_name          VARCHAR(100),
    status              VARCHAR(50) DEFAULT 'pending',
    downstream_eligible BOOLEAN DEFAULT FALSE,
    start_time          TIMESTAMP,
    end_time            TIMESTAMP,
    duration_seconds    INTEGER,
    run_number          INTEGER DEFAULT 1,        -- increments on re-run
    triggered_by        VARCHAR(100),             -- manual | cascade | retry
    created_at          TIMESTAMP DEFAULT NOW()
);

-- stage_checkpoints
CREATE TABLE stage_checkpoints (
    checkpoint_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_id            UUID REFERENCES project_stages(stage_id),
    checkpoint_number   INTEGER NOT NULL,          -- CP1, CP2 etc.
    state_snapshot      JSONB NOT NULL,
    rollback_available  BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- handoff_packages
CREATE TABLE handoff_packages (
    package_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_id            UUID REFERENCES project_stages(stage_id),
    project_uuid        UUID REFERENCES projects(project_uuid),
    input_package_ids   JSONB,                    -- list of upstream package UUIDs
    governing_source    VARCHAR(500),
    output_summary      TEXT,
    status              VARCHAR(50),
    warnings            JSONB,                    -- list of {id, summary, carry_forward}
    traceability_ref    JSONB,
    export_readiness    JSONB,                    -- {dwg: true, pdf: true}
    downstream_eligible BOOLEAN DEFAULT FALSE,
    known_limitations   TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- validation_results
CREATE TABLE validation_results (
    result_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_id            UUID REFERENCES project_stages(stage_id),
    field_code          VARCHAR(100),
    field_name          VARCHAR(200),
    design_source_value TEXT,
    generated_value     TEXT,
    status              VARCHAR(20),   -- PASS | FAIL | WARNING
    severity            VARCHAR(20),   -- CRITICAL | MAJOR | MINOR | INFORMATIONAL
    correction_required TEXT,
    failure_class       VARCHAR(100),  -- SOURCE_MISSING, FIELD_CONFLICT, etc.
    checked_at          TIMESTAMP DEFAULT NOW()
);

-- escalations
CREATE TABLE escalations (
    escalation_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_id            UUID REFERENCES project_stages(stage_id),
    project_uuid        UUID REFERENCES projects(project_uuid),
    escalation_type     VARCHAR(30),   -- ENGINEERING | IT_DATA
    reason              TEXT NOT NULL,
    severity            VARCHAR(20),
    evidence            TEXT,
    likely_cause        TEXT,
    recommended_action  TEXT,
    downstream_blocked  BOOLEAN DEFAULT TRUE,
    status              VARCHAR(20) DEFAULT 'open',
    reviewer            VARCHAR(100),
    resolved_at         TIMESTAMP,
    resolution_notes    TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- correction_events (Level 1 learning feed)
CREATE TABLE correction_events (
    event_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_uuid        UUID REFERENCES projects(project_uuid),
    stage_id            UUID REFERENCES project_stages(stage_id),
    field_code          VARCHAR(100) NOT NULL,
    original_value      TEXT,
    corrected_value     TEXT,
    correction_source   VARCHAR(50),   -- human | fallback_agent | level2_suggestion
    confidence          DECIMAL(4,2),
    event_timestamp     TIMESTAMP DEFAULT NOW()
);

-- rule_proposals (Level 1 output)
CREATE TABLE rule_proposals (
    proposal_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_field_code  VARCHAR(100),
    trigger_event_count INTEGER,
    existing_rule_id    UUID,                      -- FK to validation_rules
    proposed_rule_text  TEXT NOT NULL,
    existing_rule_text  TEXT,
    proposal_rationale  TEXT,
    status              VARCHAR(20) DEFAULT 'pending',   -- pending | approved | rejected
    reviewed_by         VARCHAR(100),
    reviewed_at         TIMESTAMP,
    review_notes        TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- output_packages
CREATE TABLE output_packages (
    output_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_uuid        UUID REFERENCES projects(project_uuid),
    output_type         VARCHAR(50),   -- AB | GA | SHOP | SHEETING | SHIPPING | INSTALLATION | PACKAGE
    file_paths          JSONB,         -- {dxf: "path", dwg: "path", pdf: "path"}
    release_status      VARCHAR(20) DEFAULT 'pending',
    approved_by         VARCHAR(100),
    approved_at         TIMESTAMP,
    generated_at        TIMESTAMP DEFAULT NOW()
);
```

**Master DB Tables (Phase 1 Outputs)**

```sql
-- template_library
CREATE TABLE template_library (
    template_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_code       VARCHAR(50) UNIQUE NOT NULL,
    template_name       VARCHAR(200),
    output_class        VARCHAR(50),      -- AB | GA | SHEETING | SHOP | SHIPPING | INSTALLATION
    family_id           VARCHAR(50),
    family_name         VARCHAR(200),
    status              VARCHAR(20),      -- standard | optional | deprecated
    title_block_type    VARCHAR(100),
    revision_block_type VARCHAR(100),
    layout_rules        JSONB,
    note_structure      JSONB,
    observed_frequency  INTEGER,
    source_jobs         JSONB,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- field_dictionary
CREATE TABLE field_dictionary (
    field_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    field_code          VARCHAR(100) UNIQUE NOT NULL,
    field_name          VARCHAR(200),
    description         TEXT,
    category            VARCHAR(50),      -- engineering | derived | presentation | metadata | control
    subcategory         VARCHAR(100),
    data_type           VARCHAR(50),
    unit_of_measure     VARCHAR(50),
    is_mandatory        BOOLEAN DEFAULT FALSE,
    field_role          VARCHAR(30),      -- governing | derived | presentation | metadata
    primary_source      VARCHAR(100),
    secondary_source    VARCHAR(100),
    source_file_type    VARCHAR(100),
    extraction_method   TEXT,
    normalization_rule  TEXT,
    validation_rule_ref VARCHAR(100),
    override_priority   INTEGER,
    missing_data_impact VARCHAR(20),      -- blocks | warns | none
    downstream_outputs  JSONB,            -- list of output classes affected
    notes               TEXT
);

-- source_mapping_rules
CREATE TABLE source_mapping_rules (
    mapping_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mapping_rule_id         VARCHAR(50) UNIQUE NOT NULL,
    field_code              VARCHAR(100) REFERENCES field_dictionary(field_code),
    output_classes          JSONB,
    primary_source_app      VARCHAR(100),
    primary_source_filetype VARCHAR(50),
    primary_source_location TEXT,
    extraction_method       TEXT,
    normalization_method    TEXT,
    secondary_source        VARCHAR(100),
    cross_check_source      VARCHAR(100),
    prohibited_source       VARCHAR(100),
    confidence_level        DECIMAL(4,2),
    fallback_rule           TEXT,
    block_condition         TEXT,
    notes                   TEXT
);

-- validation_rules
CREATE TABLE validation_rules (
    rule_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code           VARCHAR(50) UNIQUE NOT NULL,
    rule_name           VARCHAR(200),
    rule_category       VARCHAR(100),     -- completeness | consistency | geometry | etc.
    applies_to          JSONB,
    input_fields        JSONB,
    validation_logic    TEXT NOT NULL,
    severity            VARCHAR(20),      -- CRITICAL | MAJOR | MINOR | INFORMATIONAL
    pass_condition      TEXT,
    fail_condition      TEXT,
    warn_condition      TEXT,
    action_outcome      VARCHAR(10),      -- BLOCK | WARN | ALLOW
    escalation_required BOOLEAN DEFAULT FALSE,
    is_active           BOOLEAN DEFAULT TRUE,
    version             INTEGER DEFAULT 1,
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- override_rules
CREATE TABLE override_rules (
    override_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    override_rule_id    VARCHAR(50) UNIQUE NOT NULL,
    conflict_type       VARCHAR(100),
    higher_priority_src VARCHAR(100),
    lower_priority_src  VARCHAR(100),
    governing_decision  TEXT,
    block_condition     TEXT,
    warn_condition      TEXT,
    human_review_required BOOLEAN DEFAULT FALSE,
    notes               TEXT
);
```

---

## 7. Vector DB Setup — ChromaDB

ChromaDB runs embedded (no separate server). It persists to disk at the path in `.env`.

```python
# app/vector/chroma_client.py
import chromadb
from app.config.settings import settings

def get_chroma_client():
    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return client

def get_project_profiles_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION_PROJECT_PROFILES,
        metadata={"hnsw:space": "cosine"}
    )
```

**Collections:**
- `project_profiles` — one embedding per approved project. Metadata: `project_uuid`, `project_type`, `bay_count`, `member_types`, `template_family`
- `template_patterns` — embeddings from Phase 1 template analysis for Level 2 suggestions

---

## 8. LLM Setup — Ollama

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull models (choose one or both)
ollama pull llama3
ollama pull mistral

# Verify
ollama list
curl http://localhost:11434/api/tags
```

**LangChain connection:**
```python
from langchain_community.llms import Ollama
from app.config.settings import settings

llm = Ollama(
    base_url=settings.OLLAMA_BASE_URL,
    model=settings.OLLAMA_MODEL,
    timeout=settings.OLLAMA_TIMEOUT
)
```

**Critical agent instruction** (embedded in every agent system prompt):
```
You must never guess or invent missing engineering values.
If a required engineering value is absent, stop and return:
  { "status": "BLOCKED", "reason": "FIELD_MISSING", "field": "<field_code>" }
```

---

## 9. ODA File Converter Setup

The ODA File Converter is a free tool from the Open Design Alliance that converts DXF ↔ DWG.

**Windows:**
1. Download from https://www.opendesign.com/guestfiles/oda_file_converter
2. Install to default path: `C:\Program Files\ODA\ODAFileConverter\`
3. Set `ODA_CONVERTER_PATH` in `.env`

**Linux:**
```bash
# Download AppImage
chmod a+x ~/Apps/ODAFileConverter.AppImage
# Set in .env: ODA_CONVERTER_PATH=/home/user/Apps/ODAFileConverter.AppImage
```

**Python wrapper:**
```python
# app/cad/oda_converter.py
from ezdxf.addons import odafc
import ezdxf

def export_to_dwg(dxf_path: str, output_dwg_path: str, version: str = "R2018"):
    doc = ezdxf.readfile(dxf_path)
    odafc.export_dwg(doc, output_dwg_path, version=version)

def read_dwg(dwg_path: str):
    return odafc.readfile(dwg_path)
```

---

## 10. Agent Architecture — LangGraph

Each phase is a LangGraph `StateGraph`. The state carries the project context, handoff packages, and validation results between nodes.

```python
# Example: Phase 2 graph structure
from langgraph.graph import StateGraph, END
from app.orchestrator.status_model import StageStatus

def build_phase2_graph():
    workflow = StateGraph(Phase2State)

    # Add nodes
    workflow.add_node("p2_01_ingestion",    p2_01_ingestion_agent)
    workflow.add_node("p2_02_completeness", p2_02_completeness_agent)
    workflow.add_node("p2_03_ab_gen",       p2_03_ab_generation_agent)
    workflow.add_node("p2_04_ga_gen",       p2_04_ga_generation_agent)
    workflow.add_node("p2_05_validation",   p2_05_abga_validation_agent)
    workflow.add_node("validator",          validator_agent)
    workflow.add_node("fallback",           fallback_agent)
    workflow.add_node("orchestrator",       orchestrator_decision)

    # Entry point
    workflow.set_entry_point("p2_01_ingestion")

    # Conditional edges (orchestrator decides next step)
    workflow.add_conditional_edges("validator", route_by_status, {
        "pass":      "orchestrator",
        "fail":      "fallback",
        "escalate":  END
    })
    workflow.add_conditional_edges("fallback", route_after_fallback, {
        "retry_pass": "orchestrator",
        "escalate":   END
    })

    return workflow.compile()
```

**State schema:**
```python
from typing import TypedDict, Optional, List
from pydantic import BaseModel

class Phase2State(TypedDict):
    project_uuid: str
    current_stage: str
    stage_status: str                      # PASS | FAIL | BLOCKED | ESCALATE | RE-RUN
    handoff_packages: dict                 # stage_code → handoff package
    validation_results: list
    escalations: list
    warnings: list
    ab_package: Optional[dict]             # structured AB output
    ga_package: Optional[dict]             # structured GA output
    governing_source: Optional[str]
    run_number: int
    rerun_cascade: list                    # stages to invalidate
```

---

## 11. Phase 1 Agents

Runs on 50 reference jobs to build master DB. Run once (then re-run after every 10 new approved projects, triggered manually).

| Agent | Input | Output Table |
|-------|-------|-------------|
| `p1_01_template_extraction` | 50 reference job files | `template_library` |
| `p1_02_field_dictionary` | Template extraction output | `field_dictionary` |
| `p1_03_source_mapping` | Field dictionary | `source_mapping_rules` |
| `p1_04_validation_rules` | Field dict + source mapping | `validation_rules`, `override_rules` |
| `p1_05_db_consolidator` | All above | All tables finalized + cross-referenced |

**Run Phase 1:**
```bash
python scripts/seed_phase1.py \
  --jobs-path ./data/reference_jobs \
  --output-summary ./data/phase1_report.json
```

---

## 12. Phase 2 Agents

**P2-01 — Design File Ingestion**
```
Input:  Project folder path
Tasks:  Scan subfolders → unpack ZIP/RAR → classify each file →
        rank design candidates → detect revision conflicts
Output: file_inventory (DB + handoff)
Human gate: If multiple design candidates with equal confidence → engineer selects
```

**P2-02 — Completeness Check**
```
Input:  Governing design file + master field_dictionary + source_mapping_rules
Tasks:  Map available data against AB-required fields and GA-required fields →
        classify each field: PRESENT | MISSING | SUSPICIOUS | CONFLICTING →
        issue AB readiness and GA readiness decisions
Output: completeness_matrix, blocking_issues, readiness_decision (DB + handoff)
Human gate: If critical fields missing → engineer provides or confirms alternate source
```

**P2-03 — AB Generation** *(Sequential before GA)*
```
Input:  Validated design data, AB readiness confirmation, template_library (AB family)
Tasks:  Extract bolt sizes, quantities, spacing, grid references, base plate refs,
        coordinate/position refs, elevation refs → map to AB template zones →
        generate Plan view data + Section view data + Detail view data →
        build traceability matrix
Output: ab_structured_package (JSON + DB), template_population_map
Human gate: Fallback escalation after two failures
```

**P2-04 — GA Generation** *(Only after P2-03 PASS)*
```
Input:  Approved AB package, validated design data, template_library (GA family)
Tasks:  Extract overall geometry, grid system, bay spacing, frame positions,
        levels/elevations, roof slope, major member refs →
        Plan view uses AB grid references directly →
        Elevation views, Section/detail views
Output: ga_structured_package (JSON + DB), template_population_map
Stop condition: If AB package not approved → BLOCKED
```

**P2-05 — AB/GA Validation** *(Hard gate for all Phase 3)*
```
Input:  Governing design data, AB package, GA package
Tasks:  AB vs design source field-by-field comparison →
        GA vs design source field-by-field comparison →
        AB/GA overlap consistency (shared fields must agree) →
        Classify: PASS | FAIL | WARNING per field
Output: validation_matrix (DB + handoff), final downstream decision
Gate:   ALL Phase 3 agents blocked until this returns PASS or PASS WITH WARNINGS
```

---

## 13. Phase 3 Agents

All Phase 3 agents have the same contract: they only receive approved upstream packages. Any unapproved upstream input causes immediate BLOCKED status.

| Agent | Key Dependencies | Primary Output |
|-------|-----------------|----------------|
| P3-01 Sheeting | P2-05 approved | Sheeting zone table, lengths, quantities, list |
| P3-02 Shop/Detail | P2-05 + P3-01 | Member detail table, assembly grouping, mark consistency |
| P3-03 Shipping | P3-02 approved | Mark-wise shipping table, quantity reconciliation |
| P3-04 Installation | P2-05 + P3-02 + P3-03 | Erection sequence, placement references |
| P3-05 Final Check | All P3-01→P3-04 | Critical failure matrix, warnings, FINAL RELEASE DECISION |

---

## 14. Master Orchestration Agent

The orchestrator is not a LangGraph node — it is a controller that wraps all graph execution and makes routing decisions.

```python
# app/orchestrator/controller.py

class MasterOrchestrator:
    def evaluate_stage(self, stage_code: str, project_uuid: str) -> OrchestratorDecision:
        # 1. Check prerequisite stage approvals
        # 2. Check required handoff package completeness
        # 3. Check for upstream invalidation (re-run cascade)
        # 4. Evaluate stage result + classify issues
        # 5. Decide: PASS | FAIL | BLOCKED | ESCALATE | RE-RUN
        # 6. Decide downstream eligibility
        # 7. Check re-run cascade requirements
        # 8. Return OrchestratorDecision
        ...

    def approve_handoff(self, package_id: str) -> bool:
        # Validates all mandatory handoff fields are present
        # No unresolved CRITICAL issue exists
        # No prohibited source dependency
        # Traceability requirements satisfied
        ...

    def trigger_cascade(self, changed_stage: str, project_uuid: str) -> List[str]:
        # Returns list of stage_codes that must be invalidated
        # and re-run based on cascade_rules
        ...
```

**Cascade rules table** (in `app/orchestrator/cascade_manager.py`):
```python
CASCADE_RULES = {
    "P2-01": ["P2-02", "P2-03", "P2-04", "P2-05", "P3-01", "P3-02", "P3-03", "P3-04", "P3-05"],
    "P2-03": ["P2-04", "P2-05", "P3-01", "P3-02", "P3-03", "P3-04", "P3-05"],   # AB change → GA re-gen
    "P2-04": ["P2-05", "P3-01", "P3-02", "P3-03", "P3-04", "P3-05"],
    "P2-05": ["P3-01", "P3-02", "P3-03", "P3-04", "P3-05"],
    "P3-02": ["P3-03", "P3-04", "P3-05"],
    "P3-03": ["P3-04", "P3-05"],
    "P3-04": ["P3-05"],
}
```

---

## 15. Validator & Fallback Pattern

```python
# app/agents/support/validator.py

class StageValidator:
    def validate(self, stage_code: str, output_package: dict, project_uuid: str) -> ValidationResult:
        rules = self.db.get_active_rules_for_stage(stage_code)
        results = []
        for rule in rules:
            result = self.evaluate_rule(rule, output_package)
            results.append(result)
        return ValidationResult(
            stage_code=stage_code,
            status=self.derive_status(results),   # PASS | FAIL | WARNING
            field_results=results
        )

# app/agents/support/fallback.py

class FallbackAgent:
    MAX_RETRIES = 1   # Hard limit — one attempt only

    def attempt_correction(self, stage_code: str, failures: list, project_uuid: str):
        if self.get_retry_count(stage_code, project_uuid) >= self.MAX_RETRIES:
            return self.escalate(stage_code, failures, project_uuid)
        # Targeted re-extraction for failed fields only
        corrected = self.re_extract_failed_fields(failures)
        self.log_correction_events(corrected, project_uuid, stage_code)
        return corrected
```

---

## 16. Data Extraction Layer (Parsers)

### STAAD Pro Parser (Highest Priority)
```python
# app/parsers/staad_parser.py
# .std files are plain text with a defined grammar
# Sections: JOINT COORDINATES, MEMBER INCIDENCES, MEMBER PROPERTIES, SUPPORTS, etc.

class STAADParser:
    def parse(self, file_path: str) -> STAADData:
        # Read .std file line by line
        # Detect section headers (JOINT, MEMBER, UNIT, LOAD, etc.)
        # Extract: joint coordinates → grid/column positions
        # Extract: member incidences → member connectivity
        # Extract: member properties → section references
        # WARNING: Bolt table often absent — log to correction_events if missing
        ...

    def extract_grid_system(self, joints: dict) -> GridData: ...
    def extract_member_sections(self, members: dict) -> MemberData: ...
    def extract_bolt_table(self, raw_text: str) -> Optional[BoltData]: ...
    # Returns None if missing — triggers Level 1 flag
```

### MBS Parser
```python
# app/parsers/mbs_parser.py
class MBSParser:
    def parse(self, file_path: str) -> MBSData:
        # Detect file format: XML export vs structured text report
        # XML: use xml.etree.ElementTree
        # Text: regex-based section extraction
        ...
```

### ETABS Parser
```python
# app/parsers/etabs_parser.py
import openpyxl, pandas as pd

class ETABSParser:
    def parse(self, excel_path: str) -> ETABSData:
        wb = openpyxl.load_workbook(excel_path)
        # Typical sheets: Story Data, Column Data, Beam Data, Joint Loads
        story_data   = pd.read_excel(excel_path, sheet_name="Story Data")
        column_data  = pd.read_excel(excel_path, sheet_name="Column Data")
        ...
```

### PDF Parsers
```python
# app/parsers/pdf_text_parser.py  — secondary source only
import pdfplumber

class PDFTextParser:
    CONFIDENCE = 0.65   # always flagged as lower confidence

    def extract_tables(self, pdf_path: str) -> List[dict]: ...
    def extract_text_by_region(self, pdf_path: str, bbox: tuple) -> str: ...

# app/parsers/pdf_image_parser.py  — lowest confidence
import fitz, pytesseract

class PDFImageParser:
    CONFIDENCE = 0.40   # always flagged, always requires human verification

    def ocr_page(self, pdf_path: str, page_num: int) -> str: ...
```

---

## 17. Learning Agent

Runs as a Celery background service — not part of the request/response cycle.

```python
# app/tasks/learning_tasks.py
from celery import shared_task

@shared_task
def run_rule_analysis():
    """Level 1: Check correction_events for patterns, propose rule updates"""
    analyser = RuleAnalyser()
    proposals = analyser.find_threshold_violations(threshold=5)
    for p in proposals:
        db.create_rule_proposal(p)
        notification_service.notify_engineer("rule_proposal", p)

@shared_task
def update_vector_index(project_uuid: str):
    """Level 3: Add approved project to ChromaDB"""
    profile = project_profile_builder.build(project_uuid)
    embedding = embedder.embed(profile)
    chroma_collection.add(
        documents=[profile.to_text()],
        embeddings=[embedding],
        ids=[project_uuid],
        metadatas=[profile.to_metadata()]
    )
```

---

## 18. Output Generator Agent

```python
# app/agents/support/output_generator.py

class OutputGeneratorAgent:
    def generate(self, project_uuid: str, output_types: list) -> OutputPackage:
        for output_type in output_types:
            package = self.db.get_structured_package(project_uuid, output_type)
            # Step 1: Build DXF from structured data
            dxf_path = self.dxf_builder.build(package)
            # Step 2: Convert DXF → DWG via ODA
            dwg_path = self.oda_converter.export_to_dwg(dxf_path)
            # Step 3: Render DXF → PDF via matplotlib
            pdf_path = self.pdf_renderer.render(dxf_path)
            self.db.save_output_paths(project_uuid, output_type, dxf_path, dwg_path, pdf_path)
        # Step 4: Package everything into ZIP
        return self.package_builder.create_zip(project_uuid, output_types)
```

---

## 19. FastAPI Endpoints

```
POST   /api/projects/                       Create new project
GET    /api/projects/{uuid}                 Get project detail
GET    /api/projects/                       List all projects

POST   /api/projects/{uuid}/files           Upload project files
GET    /api/projects/{uuid}/files           List files for project

POST   /api/projects/{uuid}/run/phase1      Trigger Phase 1 (admin)
POST   /api/projects/{uuid}/run/phase2      Start Phase 2 pipeline
POST   /api/projects/{uuid}/run/phase3      Start Phase 3 pipeline (requires P2 pass)

GET    /api/projects/{uuid}/stages          Get all stage statuses
GET    /api/projects/{uuid}/stages/{code}   Get specific stage detail
POST   /api/projects/{uuid}/stages/{code}/approve   Engineer approves handoff
POST   /api/projects/{uuid}/stages/{code}/rerun     Trigger re-run

GET    /api/projects/{uuid}/handoffs        Get all handoff packages
GET    /api/projects/{uuid}/escalations     Get open escalations
POST   /api/projects/{uuid}/escalations/{id}/resolve  Resolve escalation

GET    /api/projects/{uuid}/outputs         List generated output files
POST   /api/projects/{uuid}/outputs/generate  Generate outputs (post P3-05 pass)
GET    /api/projects/{uuid}/outputs/download  Download output ZIP

GET    /api/learning/proposals              List pending rule proposals
POST   /api/learning/proposals/{id}/approve  Engineer approves rule update
POST   /api/learning/proposals/{id}/reject   Engineer rejects rule update
GET    /api/learning/suggestions/{project_uuid}  Get Level 2 field suggestions
POST   /api/learning/suggestions/{id}/accept     Accept field suggestion
POST   /api/learning/suggestions/{id}/reject     Reject field suggestion

WS     /ws/{project_uuid}                  WebSocket live tracking feed
```

---

## 20. WebSocket — Live Tracking

```python
# app/api/ws.py
from fastapi import WebSocket
from app.agents.support.notification import notification_service

@router.websocket("/ws/{project_uuid}")
async def websocket_endpoint(websocket: WebSocket, project_uuid: str):
    await websocket.accept()
    notification_service.register(project_uuid, websocket)
    try:
        while True:
            await websocket.receive_text()   # Keep alive
    except:
        notification_service.unregister(project_uuid, websocket)

# Broadcast from any agent:
await notification_service.broadcast(project_uuid, {
    "type": "stage_update",
    "stage_code": "P2-03",
    "status": "PASS",
    "message": "AB Generation complete. 47 fields validated.",
    "timestamp": "2026-04-17T10:32:11Z"
})
```

**Message types:** `stage_update` | `validation_result` | `escalation_raised` | `suggestion_ready` | `handoff_approved` | `output_ready` | `rule_proposal`

---

## 21. Celery — Background Jobs

```python
# app/tasks/celery_app.py
from celery import Celery
from app.config.settings import settings

celery_app = Celery(
    "steel_agent",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.phase1_tasks", "app.tasks.phase2_tasks",
             "app.tasks.phase3_tasks", "app.tasks.learning_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    task_track_started=True,
    task_acks_late=True,           # Ack only after success (safe for agent tasks)
    worker_prefetch_multiplier=1,  # One task at a time per worker (agent safety)
)
```

**Start workers:**
```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Celery worker
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4

# Terminal 3: Celery beat (for scheduled learning tasks)
celery -A app.tasks.celery_app beat --loglevel=info
```

---

## 22. Running the Backend

```bash
# Start PostgreSQL and Redis first, then:

cd backend
source venv/bin/activate

# Initialise DB (first time only)
python scripts/init_db.py

# Start FastAPI
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Start Celery (separate terminal)
celery -A app.tasks.celery_app worker --loglevel=info

# API docs available at:
# http://localhost:8000/docs   (Swagger UI)
# http://localhost:8000/redoc  (ReDoc)
```

---

## 23. Testing Strategy

```bash
# Run all tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration (requires running PostgreSQL + Redis)
pytest tests/integration/ -v

# Specific parser test
pytest tests/unit/test_parsers.py::test_staad_bolt_extraction -v

# Coverage report
pytest --cov=app --cov-report=html tests/
```

---

## 24. Deployment Notes

- **Desktop deployment:** Package as executable with PyInstaller + bundled PostgreSQL portable + Redis portable
- **ODA File Converter** must be installed separately on each desktop — it cannot be bundled
- **Ollama** runs as a background service — include in startup scripts
- **ChromaDB** persists to disk at `CHROMA_PERSIST_DIR` — back up with project data
- **No internet required** once Ollama models are pulled and ODA is installed

---

*Infiniti Solutions — Steel Detailing Multi-Agent System | Backend Developer Reference | v1.0 April 2026*
