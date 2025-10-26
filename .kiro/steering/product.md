---
inclusion: always
---

# Product Overview

This is a contract clause verification system (계약서 검증 시스템) that analyzes user contracts against standard contract templates to identify missing clauses and compliance issues.

## Core Functionality

- **Document Ingestion**: Parse and chunk contract documents (DOCX, TXT, PDF)
- **Clause Verification**: Compare user contracts against standard contract templates using hybrid search (BM25 + FAISS vector search) and LLM-based semantic matching
- **Compliance Analysis**: Calculate standard compliance rates and identify missing or non-compliant clauses
- **Report Generation**: Generate detailed verification reports in text and PDF formats

## Key Features

- Multi-agent architecture with specialized workers (classification, consistency validation, report generation)
- Hybrid search combining keyword-based (BM25) and semantic (FAISS embeddings) retrieval
- LLM-powered final verification using Azure OpenAI (GPT-4)
- CLI-based ingestion pipeline for document processing and verification
- Streamlit frontend for contract upload and analysis

## Target Users

Legal teams and contract managers who need to verify that user contracts comply with standard contract templates, particularly for data-related agreements.

## Verification Workflow

1. **Document Ingestion**: Parse contracts into structured JSON format
2. **Chunking**: Split into clause-level chunks (조/항/호/목 hierarchy)
3. **Embedding**: Generate vector embeddings using Azure OpenAI
4. **Hybrid Search**: Combine BM25 (keyword) + FAISS (semantic) search
5. **LLM Verification**: Final semantic matching with confidence scoring
6. **Report Generation**: Detailed compliance reports with missing clauses

## Verification Modes

- **Forward Verification** (표준→사용자): Check if standard clauses exist in user contract
- **Reverse Verification** (사용자→표준, 권장): Check if user clauses match standard, with duplicate detection and article-level grouping for better performance
