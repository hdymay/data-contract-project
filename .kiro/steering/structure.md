---
inclusion: always
---

# Project Structure & Conventions

## Directory Organization

```
project/
├── backend/                    # Multi-agent backend services
│   ├── fastapi/               # REST API (port 8000)
│   ├── classification_agent/  # Contract classification worker
│   ├── consistency_agent/     # Consistency validation worker
│   ├── report_agent/          # Report generation worker
│   ├── clause_verification/   # Core verification engine
│   │   ├── verification_engine.py    # Main verification orchestrator
│   │   ├── hybrid_search.py          # BM25 + FAISS search
│   │   ├── llm_verification.py       # LLM-based semantic matching
│   │   ├── embedding_service.py      # Azure OpenAI embeddings
│   │   ├── data_loader.py            # Contract data loading
│   │   ├── report_generator.py       # Report generation
│   │   ├── models.py                 # Data models (ClauseData, MatchResult, etc.)
│   │   └── config.py                 # Configuration
│   └── shared/                # Shared utilities
├── ingestion/                 # Document ingestion pipeline
│   ├── ingest.py             # CLI entry point (cmd.Cmd based)
│   ├── parsers/              # Document parsers (DOCX, TXT, PDF)
│   ├── processors/           # Chunking and text processing
│   │   └── chunker.py        # Clause-level chunking
│   └── indexers/             # FAISS index management
├── frontend/                  # Streamlit web UI
│   └── app.py                # Main Streamlit app
├── data/                      # Data storage (mounted in Docker)
│   ├── source_documents/     # Original uploads
│   ├── extracted_documents/  # Parsed JSON (*.json)
│   ├── chunked_documents/    # Chunked clauses (*.jsonl)
│   ├── reports/              # Verification reports
│   ├── search_indexes/       # FAISS indexes
│   │   └── faiss/
│   └── database.db           # SQLite database
├── docker/                    # Docker configuration
│   ├── docker-compose.yml
│   └── Dockerfile.*          # Per-service Dockerfiles
├── requirements/              # Modular requirements
│   ├── requirements.txt      # Common dependencies
│   ├── requirements-backend.txt
│   ├── requirements-frontend.txt
│   ├── requirements-ingestion.txt
│   └── requirements-*.txt    # Per-agent requirements
├── tests/                     # Test suite
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/                      # Documentation
└── test_*.py                  # Standalone test scripts (root level)
```

## Code Organization Patterns

### Data Models (dataclasses)

Located in `backend/clause_verification/models.py`:
- `ClauseData`: Individual contract clause with id, title, subtitle, type, text, text_norm, breadcrumb, embedding
- `VerificationDecision`: LLM decision with is_match, confidence (0.0-1.0), reasoning
- `MatchResult`: Search result with standard_clause, matched_clause, bm25_score, faiss_score, hybrid_score, llm_decision, is_matched, is_duplicate
- `VerificationResult`: Final outcome with total counts, matched_clauses, missing_clauses, match_results, duplicate_matches, compliance rates

### Service Layer

Each service is a standalone class with clear responsibilities:
- `EmbeddingService`: Generate embeddings via Azure OpenAI
- `HybridSearchEngine`: Combine BM25 and FAISS search
- `LLMVerificationService`: Final semantic verification with GPT-4
- `ContractDataLoader`: Load and parse contract documents
- `ReportGenerator`: Generate text and PDF reports

### Verification Pipeline

Two verification modes:

**Forward Verification** (표준→사용자):
1. **Hybrid search**: BM25 (30%) + FAISS (70%) combined scoring
2. **LLM verification**: Final decision with confidence and reasoning

**Reverse Verification** (사용자→표준, 권장):
1. **Group by article**: Group standard clauses by title (조 단위)
2. **FAISS search**: Find top-k candidates from user clauses
3. **Title-level filtering**: Select top-k titles for LLM verification
4. **LLM verification**: Final decision with duplicate detection

### File Naming Conventions

- **Test files**: `test_*.py` (standalone scripts, not pytest)
- **Parsed documents**: `parsed_<doc_id>.json` or `*_structured.json`
- **Chunked documents**: `parsed_<doc_id>_chunks.jsonl` or `*_chunks_clause.jsonl`
- **Article-level chunks**: `*_art_chunks.json` (조 단위 청킹)
- **Reports**: `verification_report_YYYYMMDD_HHMMSS.txt|pdf` or `clause_verification_report_*.txt`
- **FAISS indexes**: Stored in `search_indexes/faiss/` with `.index` and `.json` metadata

### Configuration

- Environment variables in `.env` (not committed)
- Service configs in `backend/*/config.py`
- Docker configs in `docker/` directory

## Key Architectural Decisions

1. **Hierarchical contract structure**: Standard contracts use 조(article) → 항(paragraph) → 호(item) → 목(subitem) hierarchy
2. **Flatten adapter pattern**: Convert hierarchical structures to flat ClauseData for verification
3. **CLI-driven ingestion**: Interactive CLI (`ingestion/ingest.py`) using cmd.Cmd for all document processing
4. **Multi-format support**: Handle DOCX (structured), TXT (plain text), PDF documents
5. **Hybrid search**: Combine BM25 (30%) and FAISS (70%) with normalized scoring
6. **LLM as final arbiter**: Use GPT-4o for final verification decisions with confidence and reasoning
7. **Reverse verification**: User→Standard matching with article-level grouping and duplicate detection
8. **Two-level chunking**: Article-level (조) for simple embedding, clause-level (항) for detailed verification

## Import Conventions

- Use absolute imports from project root
- Add parent directory to sys.path in test files (for standalone test scripts)
- Service dependencies injected via constructor (dependency injection pattern)
- Test files are standalone scripts with `if __name__ == "__main__":` blocks

## Logging

- Use Python's `logging` module
- Configure at module level: `logger = logging.getLogger(__name__)`
- Log levels: INFO for pipeline steps, ERROR for failures, DEBUG for detailed traces

## Code Style Guidelines

- **Type hints**: Use type annotations for function parameters and return values
- **Docstrings**: Use for public functions and classes (Korean or English)
- **Error handling**: Use try-except blocks with specific exception types
- **Constants**: Use UPPER_CASE for module-level constants
- **Private methods**: Prefix with underscore `_method_name`
- **Line length**: Keep lines under 100 characters when possible
- **Imports**: Group stdlib, third-party, and local imports separately

## Testing Conventions

- Tests are standalone Python scripts (not pytest framework)
- Each test file has `if __name__ == "__main__":` block
- Test files start with `test_` prefix
- Add parent directory to `sys.path` for imports: `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`
- Use simple assertions and print statements for test output
- Test data located in `data/` directory
