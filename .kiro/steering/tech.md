---
inclusion: always
---

# Technology Stack

## Core Technologies

- **Language**: Python 3.x
- **Backend Framework**: FastAPI with Uvicorn
- **Frontend**: Streamlit
- **Task Queue**: Celery with Redis
- **Database**: SQLite (SQLAlchemy ORM)
- **Containerization**: Docker with docker-compose

## Key Libraries

- **Document Processing**: PyMuPDF (pymupdf), python-docx
- **Search & Retrieval**: 
  - FAISS for vector similarity search
  - BM25 (rank-bm25) for keyword-based search
- **ML/AI**:
  - Azure OpenAI for embeddings (text-embedding-3-large) and LLM (GPT-4o)
  - NumPy for numerical operations
- **Data Processing**: Pandas for data manipulation
- **Configuration**: python-dotenv for environment variables
- **Database**: SQLAlchemy ORM with Alembic migrations

## Project Structure

- `backend/`: Multi-agent backend services
  - `fastapi/`: REST API service
  - `classification_agent/`: Contract classification worker
  - `consistency_agent/`: Consistency validation worker
  - `report_agent/`: Report generation worker
  - `clause_verification/`: Core verification engine and services
  - `shared/`: Shared utilities
- `ingestion/`: Document ingestion pipeline with CLI
  - `parsers/`: Document parsers (DOCX, TXT, PDF)
  - `processors/`: Text chunking and processing
  - `indexers/`: FAISS index management
- `frontend/`: Streamlit web interface
- `data/`: Data storage
  - `source_documents/`: Original uploaded documents
  - `extracted_documents/`: Parsed JSON documents
  - `chunked_documents/`: Chunked clause data (JSONL)
  - `reports/`: Generated verification reports
  - `search_indexes/`: FAISS indexes
- `docker/`: Docker configuration files
- `requirements/`: Modular requirements files per service
- `tests/`: Test suite (unit, integration, e2e)

## Common Commands

### Development

```bash
# Run ingestion CLI
python ingestion/ingest.py

# Start backend services with Docker
docker-compose -f docker/docker-compose.yml up

# Run specific service
docker-compose -f docker/docker-compose.yml up fast-api

# Run ingestion in Docker
docker-compose --profile ingestion run --rm ingestion
```

### Testing

Tests use simple function-based approach (no pytest framework):
```bash
# Run individual test files
python test_verification_simple.py
python backend/clause_verification/test_verification_engine.py

# Tests are organized as standalone scripts with test_ prefix
```

### Verification Workflow

```bash
# Inside ingestion CLI
ingestion> verify -u data/user_contract_sample.txt --format both

# Full pipeline: parse → chunk → embed → verify
ingestion> run --mode full --file all

# Simple embedding (article-level chunking)
ingestion> run --mode s_embedding --file parsed_43_73_table_5_structured.json

# Search test
ingestion> search -i provide_std_contract -q "질의" --top 5
```

## Environment Variables

Required in `.env`:
```
AZURE_OPENAI_API_KEY=your_api_key
AZURE_ENDPOINT=your_endpoint
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_LLM_DEPLOYMENT=gpt-4o
REDIS_URL=redis://redis:6379
DATABASE_URL=sqlite:///./data/database.db
```

## Architecture Patterns

- **Multi-agent system**: Separate workers for classification, consistency, and reporting
- **Service-oriented**: Modular services (embedding, search, LLM verification, data loading)
- **CLI-first**: Ingestion pipeline driven by interactive CLI
- **Dataclass models**: Using Python dataclasses for data models
- **Adapter pattern**: Flatten hierarchical contract structures for verification

## Korean Language Processing

- **Text Normalization**: Remove special characters, normalize whitespace, convert full-width to half-width
- **Encoding**: UTF-8 for all Korean text processing
- **Search**: Both keyword (BM25) and semantic (embeddings) support Korean text
- **LLM Prompts**: Korean prompts for GPT-4o verification with structured output
