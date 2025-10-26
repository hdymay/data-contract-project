# Product Overview

## 데이터 표준계약 검증 시스템

This is a Korean document analysis system that validates data contracts against standard contract templates using AI-powered analysis.

### Core Functionality
- **Document Upload**: Users upload DOCX contracts through a Streamlit web interface
- **AI Classification**: Automatically classifies user contracts into one of 5 standard contract types using RAG + LLM
- **Standard Compliance**: Validates contracts against predefined standard contract templates (Phase 2)
- **Report Generation**: Provides detailed analysis reports highlighting compliance issues and recommendations (Phase 2)

### Key Features

#### Phase 1 (현재 구현됨)
- DOCX document parsing and structure extraction
- AI-powered contract type classification (5 types)
- RAG-based similarity matching with standard contracts
- Real-time classification results with confidence scores
- User classification review and modification interface
- Asynchronous processing with Celery + Redis

#### Phase 2 (계획됨)
- Comprehensive contract validation (completeness, checklist, content analysis)
- Context-aware flexible validation (not overly rigid)
- Guidebook integration for enhanced validation
- Detailed compliance reports with improvement suggestions
- PDF/DOCX report download functionality

### Target Users
Legal professionals, contract managers, and organizations needing to:
- Classify data contracts into standard types
- Validate contract compliance against standard templates
- Receive detailed analysis and improvement recommendations

### Current Limitations (Phase 1)
- Only supports structured DOCX files with "제n조" format
- Classification only (no validation reports yet)
- Requires Azure OpenAI credentials for AI functionality