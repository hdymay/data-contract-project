# Design Document

## Overview

본 문서는 데이터 표준계약 검증 시스템의 전체 아키텍처와 각 컴포넌트의 상세 설계를 정의합니다. 시스템은 마이크로서비스 아키텍처를 기반으로 하며, RAG(Retrieval-Augmented Generation)를 활용한 맥락 기반 검증을 핵심으로 합니다.

## Architecture

### High-Level Architecture

```
┌─────────────────┐
│   Streamlit     │  ← 사용자 인터페이스
│   Frontend      │
└────────┬────────┘
         │ HTTP
         ↓
┌─────────────────┐
│    FastAPI      │  ← API Gateway
│    Backend      │
└────────┬────────┘
         │ Redis Queue
         ↓
┌─────────────────────────────────────────┐
│         Agent Workers (Celery)          │
│  ┌──────────┐  ┌──────────┐  ┌────────┐│
│  │Classifi- │→ │Consisten-│→ │ Report ││
│  │cation    │  │cy        │  │ Agent  ││
│  └──────────┘  └──────────┘  └────────┘│
└─────────────────────────────────────────┘
         ↓ Query
┌─────────────────────────────────────────┐
│      Knowledge Base (RAG System)        │
│  ┌──────────────┐  ┌──────────────┐    │
│  │ Standard     │  │ Guidebook    │    │
│  │ Contracts    │  │ Index        │    │
│  │ Index        │  │              │    │
│  └──────────────┘  └──────────────┘    │
│  FAISS + Whoosh (Hybrid Search)        │
└─────────────────────────────────────────┘
```

### Data Flow

1. **Upload Phase**: 사용자 → Frontend → FastAPI → Redis Queue
2. **Classification Phase**: Classification Agent → RAG Query → Type Detection
3. **Validation Phase**: Consistency Agent → RAG Query → Validation Results
4. **Report Phase**: Report Agent → Quality Check → Final Report
5. **Display Phase**: FastAPI → Frontend → User


## Components and Interfaces

### 1. Ingestion Pipeline (지식베이스 구축)

#### 1.1 Guidebook Parser

**Purpose**: 활용안내서 DOCX를 구조화된 JSON으로 파싱

**Input**: 
- `guidebook.docx` (활용안내서 원본)

**Output**:
- `guidebook_structured.json` (구조화된 데이터)

**Structure** (임시 초안 - 실제 활용안내서 구조 분석 후 변경 가능):
```json
{
  "commentary": [
    {
      "contract_type": "provide",
      "article_no": 1,
      "article_title": "목적",
      "content": "본 조는..."
    }
  ],
  "comparison_table": [
    {
      "article_title": "목적",
      "provide": "제1조(목적)...",
      "create": "제1조(목적)...",
      "process": "제1조(목적)...",
      "brokerage_provider": "제1조(목적)...",
      "brokerage_user": "제1조(목적)..."
    }
  ],
  "checklist": [
    {
      "contract_type": "provide",
      "category": "계약 당사자",
      "items": [
        "데이터 제공자와 이용자가 명확히 정의되어 있는가?",
        "..."
      ]
    }
  ]
}
```

**Implementation Notes**:
- python-docx를 사용하여 문단 및 표 추출
- 제목 패턴 매칭으로 섹션 구분 (조문별 해설, 조문비교표, 체크리스트)
- 표 구조 분석하여 계약 유형별로 데이터 분리
- **주의**: 위 JSON 구조는 임시 초안이며, 실제 활용안내서 문서 구조 분석 후 조정 필요


#### 1.2 Guidebook Chunker

**Purpose**: 활용안내서를 검색 가능한 청크로 분할

**Input**:
- `guidebook_structured.json`

**Output**:
- `guidebook_chunks.json`

**Chunk Types** (임시 초안 - 실제 구현 시 조정 가능):

1. **Commentary Chunk** (조문별 해설)
```json
{
  "id": "GB-COM-provide-001",
  "global_id": "urn:guidebook:commentary:provide:art:001",
  "doc_type": "guidebook",
  "chunk_type": "commentary",
  "contract_type": "provide",
  "article_no": 1,
  "article_title": "목적",
  "text_raw": "본 조는 데이터 제공 계약의 목적을...",
  "text_norm": "데이터 제공 계약 목적...",
  "source_file": "guidebook.docx"
}
```

2. **Comparison Chunk** (조문비교표)
```json
{
  "id": "GB-CMP-001",
  "global_id": "urn:guidebook:comparison:art:001",
  "doc_type": "guidebook",
  "chunk_type": "comparison",
  "article_title": "목적",
  "contracts": {
    "provide": "제1조(목적)...",
    "create": "제1조(목적)...",
    "process": "제1조(목적)...",
    "brokerage_provider": "제1조(목적)...",
    "brokerage_user": "제1조(목적)..."
  },
  "text_raw": "목적\n제공형: ...\n창출형: ...",
  "text_norm": "목적 제공형 창출형...",
  "source_file": "guidebook.docx"
}
```

3. **Checklist Chunk** (체크리스트)
```json
{
  "id": "GB-CHK-provide-001",
  "global_id": "urn:guidebook:checklist:provide:001",
  "doc_type": "guidebook",
  "chunk_type": "checklist",
  "contract_type": "provide",
  "category": "계약 당사자",
  "items": [
    "데이터 제공자와 이용자가 명확히 정의되어 있는가?",
    "..."
  ],
  "text_raw": "계약 당사자\n- 데이터 제공자와...",
  "text_norm": "계약 당사자 데이터 제공자...",
  "source_file": "guidebook.docx"
}
```

**Implementation Notes**:
- 각 섹션(commentary, comparison, checklist)을 독립적으로 청킹
- text_norm은 검색 최적화를 위해 불필요한 기호 제거
- contract_type별로 필터링 가능하도록 메타데이터 구성
- **주의**: 위 청크 구조는 임시 초안이며, 실제 활용안내서 분석 후 필드 추가/삭제 가능


#### 1.3 Guidebook Embedder & Indexer

**Purpose**: 활용안내서 청크를 임베딩하고 검색 인덱스 생성

**Input**:
- `guidebook_chunks.json`

**Output**:
- `search_indexes/faiss/guidebook.faiss` (벡터 인덱스)
- `search_indexes/whoosh/guidebook/` (키워드 인덱스)

**Implementation Notes**:
- 기존 TextEmbedder 및 WhooshIndexer 재사용
- 표준계약서와 동일한 임베딩 모델 사용 (text-embedding-3-large)
- 인덱스는 표준계약서와 독립적으로 관리

### 2. User Contract Processing

#### 2.1 User Contract Parser

**Purpose**: 사용자 업로드 DOCX 계약서를 구조화

**Input**:
- 사용자 업로드 DOCX 파일

**Output**:
- 구조화된 JSON (표준계약서 파서와 유사한 형식)

**Key Differences from Standard Contract Parser**:
- 더 유연한 패턴 매칭 (제목, 번호 형식이 다를 수 있음)
- 인식 실패 시 fallback 로직 (일반 텍스트로 처리)
- 메타데이터에 파싱 신뢰도 포함

**Example Output**:
```json
{
  "articles": [
    {
      "type": "조",
      "number": 1,
      "text": "제1조(목적)",
      "confidence": 0.95,
      "content": [...]
    }
  ],
  "parsing_metadata": {
    "total_articles": 15,
    "recognized_articles": 14,
    "unrecognized_sections": 1
  }
}
```


### 3. Classification Agent

#### 3.1 Architecture

**Purpose**: 사용자 계약서의 유형을 5종 중 하나로 분류

**Input**:
- 사용자 계약서 구조화 JSON

**Output**:
```json
{
  "contract_id": "user_contract_12345",
  "classification_result": {
    "predicted_type": "provide",
    "confidence": 0.87,
    "scores": {
      "provide": 0.87,
      "create": 0.45,
      "process": 0.32,
      "brokerage_provider": 0.21,
      "brokerage_user": 0.18
    }
  },
  "reasoning": "계약서에 '데이터 제공자', '데이터 이용자' 등의 용어가 빈번하게 등장하며...",
  "user_override": null
}
```

#### 3.2 Classification Strategy

**Two-Stage Classification** (키워드 기반 휴리스틱 제외):

1. **RAG-Based Semantic Matching** (의미적 유사도)
   - 사용자 계약서의 주요 조항(목적, 정의, 권리의무 등)을 쿼리로 사용
   - 5종 표준계약서 인덱스에서 각각 검색
   - 검색 결과의 평균 유사도를 유형별 점수로 계산
   - 각 유형별로 상위 10개 청크의 유사도 평균 산출

2. **LLM-Based Final Decision** (최종 판단)
   - 사용자 계약서 요약 + 5종 표준계약서 요약을 LLM에 입력
   - Few-shot prompting으로 분류 수행
   - RAG 검색 결과를 컨텍스트로 제공
   - 분류 이유(reasoning) 생성 (내부 모니터링 용도)

**Keyword-Based Heuristic 제외 이유**:
- 계약 유형 간 키워드 중복 가능성 (예: "데이터제공자"가 제공형과 중개거래형 모두 등장)
- 실제 표준계약서 분석 결과, 명확한 구분 키워드 부족
- RAG 기반 검색이 더 정확하고 유연한 분류 가능

**Implementation Notes**:
- Celery task로 구현
- Redis에서 작업 수신, 결과 저장
- 분류 결과는 프론트엔드로 전달되어 사용자 확인/수정 가능
- reasoning은 사용자에게 표시하지 않고 내부 로그로만 기록


### 4. Hybrid Search System

#### 4.1 Multi-Vector Retrieval Architecture

**Purpose**: 항 단위 청크를 조 단위로 집계하는 멀티벡터 검색

**Current State**:
- 표준계약서는 항(조의 하위항목 중 최상위) 단위로 청킹됨
- 기존 청크 구조: `parent_id`로 조 번호 참조 (예: "제1조")
- 각 청크는 독립적으로 임베딩되어 FAISS 인덱스에 저장됨

**Multi-Vector Strategy**:

1. **Chunk-Level Search** (항 단위 검색)
   - 사용자 쿼리로 FAISS + Whoosh 하이브리드 검색
   - Top-K * 3 개의 청크 수집 (조 단위 집계를 위한 여유)

2. **Article-Level Aggregation** (조 단위 집계)
   - `parent_id`로 청크를 조 단위로 그룹화
   - 각 조에 대해 집계 전략 적용:
     - **MaxPooling**: 조 내 최고 점수 청크의 점수 사용
     - **AveragePooling**: 조 내 모든 청크의 평균 점수 사용
     - **WeightedPooling**: 상위 N개 청크의 가중 평균 (기본 전략)
   
3. **Flexible Matching** (유연한 매칭)
   - 사용자 계약서 1개 조 → 표준계약서 여러 조 매칭 가능
   - 여러 조의 내용이 합쳐진 경우: 각 조별로 부분 점수 산출
   - 표준계약서에 없는 조항: 전체 인덱스 대상 검색 후 "특수 조항" 플래그

4. **Special Article Detection** (특수 조항 감지)
   - 검색 점수가 임계값(0.5) 미만인 경우
   - 사용자 계약서 특유의 조항으로 판단
   - 검증 시 "특이사항"으로 분류

**Implementation**:
```python
def multi_vector_search(query: str, contract_type: str, top_k: int = 10):
    # 1. 청크 레벨 검색
    chunk_results = hybrid_search(query, top_k=top_k * 3)
    
    # 2. 조 단위 그룹화
    article_groups = group_by_parent_id(chunk_results)
    
    # 3. 조별 점수 집계 (WeightedPooling)
    article_scores = []
    for article_id, chunks in article_groups.items():
        # 상위 3개 청크의 가중 평균 (0.5, 0.3, 0.2)
        top_chunks = sorted(chunks, key=lambda x: x['score'], reverse=True)[:3]
        weights = [0.5, 0.3, 0.2]
        score = sum(c['score'] * w for c, w in zip(top_chunks, weights))
        
        article_scores.append({
            'article_id': article_id,
            'score': score,
            'top_chunks': top_chunks,
            'all_chunks': chunks
        })
    
    # 4. 점수 순 정렬 및 Top-K 선택
    article_scores.sort(key=lambda x: x['score'], reverse=True)
    return article_scores[:top_k]
```

#### 4.2 Guidebook Integration (추후 구현)

**Note**: 활용안내서 검색은 현재 단계에서 구현하지 않음. 추후 다음 전략으로 구현 예정:

- 계약 유형별로 독립된 활용안내서 인덱스 구축
- Classification 단계에서 확정된 contract_type에 해당하는 인덱스만 로드
- 표준계약서 검색과 별도로 수행 후 결과 통합


### 5. Consistency Validation Agent

#### 5.1 Architecture

**Purpose**: 사용자 계약서의 정합성을 다각도로 검증

**Input**:
```json
{
  "contract_id": "user_contract_12345",
  "contract_type": "provide",
  "user_contract": {...},
  "classification_confidence": 0.87
}
```

**Output**:
```json
{
  "contract_id": "user_contract_12345",
  "validation_results": {
    "completeness_check": {...},
    "checklist_validation": {...},
    "content_analysis": {...}
  },
  "overall_score": 0.78,
  "issues": [...],
  "suggestions": [...]
}
```

#### 5.2 Validation Nodes

**Node A1: Completeness Check** (조항 완전성 검증)

**Purpose**: 표준계약서의 권장 조항이 사용자 계약서에 포함되어 있는지 확인

**Process**:
1. 표준계약서의 모든 조 목록 추출
2. 각 조에 대해 사용자 계약서에서 대응 조항 검색
   - 제목 기반 매칭 (정확 일치 또는 유사도)
   - 내용 기반 매칭 (RAG 검색)
3. 매칭 결과 분류:
   - **present**: 명확히 존재
   - **partial**: 일부 내용만 포함
   - **absent**: 존재하지 않음
   - **merged**: 다른 조항에 통합됨

**Output**:
```json
{
  "article_coverage": [
    {
      "std_article_no": 1,
      "std_article_title": "목적",
      "status": "present",
      "user_article_no": 1,
      "user_article_title": "계약의 목적",
      "similarity": 0.92
    },
    {
      "std_article_no": 5,
      "std_article_title": "데이터 제공 범위",
      "status": "merged",
      "user_article_no": 3,
      "user_article_title": "데이터의 범위 및 제공 방법",
      "similarity": 0.75,
      "note": "제공 범위와 방법이 하나의 조항으로 통합됨"
    },
    {
      "std_article_no": 12,
      "std_article_title": "손해배상",
      "status": "absent",
      "suggestion": "손해배상 조항 추가 권장"
    }
  ],
  "coverage_rate": 0.85
}
```


**Node A2: Checklist Validation** (체크리스트 기반 검증)

**Purpose**: 활용안내서의 체크리스트 항목을 기준으로 검증

**Process**:
1. 계약 유형에 해당하는 체크리스트 로드
2. 각 체크리스트 항목에 대해:
   - 사용자 계약서 전체를 대상으로 RAG 검색
   - LLM을 사용하여 항목 충족 여부 판단
   - 충족도 점수 (0~1) 산출

**Output**:
```json
{
  "checklist_results": [
    {
      "category": "계약 당사자",
      "items": [
        {
          "question": "데이터 제공자와 이용자가 명확히 정의되어 있는가?",
          "status": "satisfied",
          "score": 0.95,
          "evidence": "제2조(정의)에서 '데이터 제공자'와 '데이터 이용자'를 명확히 정의함",
          "location": "제2조 제1항, 제2항"
        },
        {
          "question": "계약 당사자의 권리와 의무가 명확히 구분되어 있는가?",
          "status": "partial",
          "score": 0.65,
          "evidence": "제공자의 의무는 명시되어 있으나 이용자의 의무가 불명확함",
          "location": "제4조",
          "suggestion": "이용자의 의무를 별도 조항으로 명시 권장"
        }
      ]
    },
    {
      "category": "데이터 범위",
      "items": [...]
    }
  ],
  "overall_checklist_score": 0.78
}
```

**Node A3: Content Analysis** (내용 충실도 분석)

**Purpose**: 각 조항의 내용이 표준계약서 및 활용안내서 해설 대비 충실한지 평가

**Process**:
1. 사용자 계약서의 각 조항에 대해:
   - 대응하는 표준계약서 조항 검색
   - 활용안내서 해설 검색
2. LLM을 사용하여 내용 비교:
   - 핵심 요소 포함 여부
   - 법적 명확성
   - 실무적 적절성
3. 개선 제안 생성

**Output**:
```json
{
  "article_analysis": [
    {
      "user_article_no": 5,
      "user_article_title": "데이터 제공 방법",
      "std_reference": "제5조(데이터 제공 범위)",
      "guidebook_reference": "조문별 해설 - 제5조",
      "analysis": {
        "completeness": 0.70,
        "clarity": 0.85,
        "practicality": 0.80
      },
      "missing_elements": [
        "데이터 형식 및 포맷 명시 부족",
        "제공 주기 불명확"
      ],
      "suggestions": [
        "데이터 형식(CSV, JSON 등)을 명시하여 명확성 향상",
        "제공 주기(실시간, 일별, 월별 등)를 구체적으로 기재"
      ]
    }
  ]
}
```


#### 5.3 Context-Aware Validation (맥락 기반 검증)

**Purpose**: 단순 형식 비교를 넘어 계약의 맥락을 고려한 검증

**Key Principles**:

1. **Semantic Matching over Structural Matching**
   - 조 제목이 다르더라도 의미적으로 유사하면 대응 조항으로 인정
   - 예: "데이터 제공 범위" ≈ "제공 데이터의 범위 및 내용"

2. **Content-Based Validation**
   - 특정 조항이 명시적으로 없더라도 내용이 다른 조항에 포함되어 있으면 인정
   - 예: "손해배상" 조항이 없지만 "계약 위반 시 책임" 조항에 손해배상 내용 포함

3. **Purpose-Driven Assessment**
   - 계약 당사자의 특수한 목적으로 인한 차이는 문제가 아닌 특이사항으로 분류
   - 예: B2B 계약에서 개인정보 보호 조항이 간소화된 경우

4. **Flexible Interpretation**
   - 표준계약서는 권장사항이지 필수사항이 아님을 고려
   - 누락된 조항이 있어도 계약의 전체 맥락에서 문제가 없으면 경고 수준으로 표시

**Implementation Strategy**:

```python
def validate_with_context(user_article, std_article, guidebook_commentary):
    """
    맥락 기반 검증
    
    Args:
        user_article: 사용자 계약서 조항
        std_article: 표준계약서 대응 조항
        guidebook_commentary: 활용안내서 해설
        
    Returns:
        {
            "validation_result": "pass" | "warning" | "fail",
            "reasoning": "...",
            "severity": "low" | "medium" | "high",
            "is_special_case": bool
        }
    """
    
    # 1. 의미적 유사도 계산
    semantic_similarity = compute_semantic_similarity(
        user_article['text'], 
        std_article['text']
    )
    
    # 2. 핵심 요소 추출 및 비교
    std_key_elements = extract_key_elements(std_article, guidebook_commentary)
    user_key_elements = extract_key_elements(user_article)
    
    coverage = compute_coverage(user_key_elements, std_key_elements)
    
    # 3. 맥락 분석
    context = analyze_contract_context(user_contract_full)
    
    # 4. 특수 목적 감지
    is_special_case = detect_special_purpose(user_article, context)
    
    # 5. 최종 판단
    if is_special_case:
        return {
            "validation_result": "pass",
            "reasoning": "계약 당사자의 특수한 목적으로 인한 차이로 판단됨",
            "severity": "low",
            "is_special_case": True
        }
    elif coverage >= 0.8:
        return {"validation_result": "pass", ...}
    elif coverage >= 0.5:
        return {"validation_result": "warning", "severity": "medium", ...}
    else:
        return {"validation_result": "fail", "severity": "high", ...}
```


### 6. Report Agent

#### 6.1 Architecture

**Purpose**: 검증 결과를 재검토하고 사용자 친화적인 보고서 생성

**Input**:
- Consistency Agent의 검증 결과

**Output**:
- 최종 검증 보고서

#### 6.2 Quality Assurance Process

**Step 1: Over-Standardization Check** (과도한 규격화 검증)

**Purpose**: 검증이 너무 엄격하게 적용되지 않았는지 확인

**Process**:
1. 검증 결과 중 "fail" 또는 "warning" 항목 추출
2. 각 항목에 대해:
   - 사용자 계약서의 전체 맥락 재검토
   - 해당 이슈가 실제로 문제인지 LLM으로 재평가
   - 과도한 규격화로 판단되면 심각도 하향 조정

**Example**:
```python
# Before QA
{
  "issue": "제12조(손해배상) 조항 누락",
  "severity": "high",
  "status": "fail"
}

# After QA (과도한 규격화 감지)
{
  "issue": "제12조(손해배상) 조항 누락",
  "severity": "low",
  "status": "warning",
  "qa_note": "제15조(계약 위반 시 책임)에 손해배상 관련 내용이 포함되어 있어 실질적 문제 없음"
}
```

**Step 2: Missing Issue Detection** (누락된 문제 탐지)

**Purpose**: Consistency Agent가 놓친 문제점 발견

**Process**:
1. 사용자 계약서 전체를 다시 한 번 스캔
2. 법적 리스크가 높은 항목 체크:
   - 계약 당사자 정의 누락
   - 데이터 범위 불명확
   - 책임 소재 불명확
   - 계약 해지 조건 누락
3. 발견된 이슈를 검증 결과에 추가

**Step 3: Report Generation** (보고서 생성)

**Purpose**: 검증 결과를 구조화된 보고서로 변환

**Report Structure**:
```json
{
  "contract_id": "user_contract_12345",
  "contract_type": "provide",
  "validation_date": "2025-10-24T10:30:00Z",
  "overall_assessment": {
    "score": 0.78,
    "grade": "B",
    "summary": "전반적으로 표준계약서의 주요 내용을 포함하고 있으나, 일부 조항의 명확성 개선이 필요합니다."
  },
  "issues": [
    {
      "id": "issue_001",
      "category": "completeness",
      "severity": "high",
      "title": "데이터 제공 주기 불명확",
      "description": "제5조에서 데이터 제공 방법은 명시되어 있으나, 제공 주기(실시간, 일별, 월별 등)가 명확하지 않습니다.",
      "location": "제5조(데이터 제공 방법)",
      "std_reference": "표준계약서 제5조(데이터 제공 범위) 참조",
      "guidebook_reference": "활용안내서 p.15 - 제5조 해설",
      "suggestion": "데이터 제공 주기를 명시적으로 기재하여 분쟁 소지를 줄이는 것을 권장합니다.",
      "example": "예: '데이터는 매일 오전 9시에 일괄 제공한다' 또는 '데이터는 실시간으로 API를 통해 제공한다'"
    }
  ],
  "positive_points": [
    "계약 당사자의 정의가 명확함",
    "데이터 보안 조항이 상세히 기술됨"
  ],
  "recommendations": [
    "데이터 제공 주기 명시",
    "손해배상 범위 구체화",
    "계약 해지 절차 상세화"
  ]
}
```


#### 6.3 Feedback Loop

**Purpose**: 과도한 규격화나 누락된 문제 발견 시 Consistency Agent로 피드백

**Trigger Conditions**:
1. 과도한 규격화 항목이 전체 이슈의 30% 이상
2. 새로운 high severity 이슈 발견
3. 검증 결과의 일관성 문제 감지

**Feedback Process**:
```python
def feedback_to_consistency_agent(validation_results, qa_findings):
    """
    Consistency Agent로 피드백 전송
    
    Args:
        validation_results: 원본 검증 결과
        qa_findings: QA에서 발견한 문제점
        
    Returns:
        재검증 요청 메시지
    """
    feedback = {
        "action": "revalidate",
        "contract_id": validation_results['contract_id'],
        "issues_to_review": [
            {
                "issue_id": "issue_003",
                "reason": "over_standardization",
                "note": "제12조 누락이 문제로 표시되었으나, 제15조에 관련 내용 포함됨"
            }
        ],
        "additional_checks": [
            {
                "check_type": "legal_risk",
                "focus_area": "계약 해지 조건",
                "reason": "QA에서 해지 조건 불명확성 발견"
            }
        ]
    }
    
    # Redis Queue를 통해 Consistency Agent에 재검증 요청
    send_to_queue("consistency_agent", feedback)
```

**Iteration Limit**: 최대 2회 반복 (무한 루프 방지)

### 7. Frontend Integration

#### 7.1 User Interface Components

**Upload Page**:
- DOCX 파일 업로드
- 진행 상황 표시 (파싱 → 분류 → 검증 → 보고서 생성)

**Classification Review Page**:
- 자동 분류 결과 표시
- 신뢰도 점수 시각화
- 유형 변경 드롭다운
- 확인 버튼

**Report Display Page**:
- 전체 평가 요약 (점수, 등급)
- 이슈 목록 (심각도별 필터링)
- 이슈 상세 보기 (클릭 시 확장)
- 긍정적 평가 항목
- 개선 권장사항
- 보고서 다운로드 버튼 (PDF/DOCX)

#### 7.2 API Endpoints

**POST /api/upload**
- Request: multipart/form-data (DOCX 파일)
- Response: `{"contract_id": "...", "status": "processing"}`

**GET /api/classification/{contract_id}**
- Response: 분류 결과 및 신뢰도

**POST /api/classification/{contract_id}/confirm**
- Request: `{"contract_type": "provide"}`
- Response: `{"status": "confirmed"}`

**GET /api/validation/{contract_id}/status**
- Response: 검증 진행 상황

**GET /api/report/{contract_id}**
- Response: 최종 보고서 JSON

**GET /api/report/{contract_id}/download**
- Query: `?format=pdf|docx`
- Response: 파일 다운로드


## Data Models

### Contract Document
```python
@dataclass
class ContractDocument:
    contract_id: str
    filename: str
    upload_date: datetime
    file_path: str
    parsed_data: Dict
    parsing_metadata: Dict
```

### Classification Result
```python
@dataclass
class ClassificationResult:
    contract_id: str
    predicted_type: str  # provide, create, process, brokerage_provider, brokerage_user
    confidence: float
    scores: Dict[str, float]
    reasoning: str
    user_override: Optional[str]
    confirmed_type: str
```

### Validation Result
```python
@dataclass
class ValidationResult:
    contract_id: str
    contract_type: str
    completeness_check: Dict
    checklist_validation: Dict
    content_analysis: Dict
    overall_score: float
    issues: List[Issue]
    suggestions: List[str]
```

### Issue
```python
@dataclass
class Issue:
    id: str
    category: str  # completeness, clarity, legal_risk
    severity: str  # low, medium, high
    title: str
    description: str
    location: str
    std_reference: Optional[str]
    guidebook_reference: Optional[str]
    suggestion: str
    example: Optional[str]
```

### Report
```python
@dataclass
class Report:
    contract_id: str
    contract_type: str
    validation_date: datetime
    overall_assessment: Dict
    issues: List[Issue]
    positive_points: List[str]
    recommendations: List[str]
```


## Error Handling

### Parsing Errors
- **User Contract Parsing Failure**: 구조 인식 실패 시 일반 텍스트로 처리, 사용자에게 알림
- **Guidebook Parsing Failure**: 시스템 초기화 실패, 관리자 알림

### Classification Errors
- **Low Confidence (<0.5)**: 사용자에게 수동 선택 강제 요청
- **RAG Search Failure**: Fallback to keyword-based heuristic

### Validation Errors
- **Search Index Unavailable**: 에러 메시지 표시, 재시도 옵션 제공
- **LLM API Failure**: 재시도 (최대 3회), 실패 시 부분 결과 반환

### Report Generation Errors
- **QA Process Failure**: 원본 검증 결과 그대로 사용
- **PDF/DOCX Generation Failure**: JSON 다운로드 옵션 제공

### Redis Queue Errors
- **Message Loss**: Task 상태를 DB에 저장하여 복구 가능
- **Worker Failure**: Celery의 자동 재시도 메커니즘 활용

## Testing Strategy

### Unit Tests
- Parser 모듈: 다양한 DOCX 형식 테스트
- Chunker 모듈: 청킹 로직 정확성 검증
- Searcher 모듈: 검색 결과 정확도 테스트

### Integration Tests
- Ingestion Pipeline: 전체 파이프라인 end-to-end 테스트
- Agent Communication: Redis Queue를 통한 메시지 전달 테스트
- API Endpoints: FastAPI 엔드포인트 응답 검증

### System Tests
- 실제 계약서 샘플로 전체 시스템 테스트
- 다양한 계약 유형 및 형식 커버리지 확인
- 성능 테스트 (검증 시간, 메모리 사용량)

### Test Data
- 표준계약서 5종 (기본 테스트 데이터)
- 변형된 계약서 샘플 (구조 변경, 조항 추가/삭제)
- 극단적 케이스 (매우 짧은 계약서, 매우 긴 계약서)


## Implementation Considerations

### LLM Selection
- **Primary**: Azure OpenAI GPT-4 (높은 정확도, 한국어 지원 우수)
- **Fallback**: GPT-3.5-turbo (비용 절감, 빠른 응답)
- **Embedding**: text-embedding-3-large (기존 사용 중)

### Prompt Engineering
- **Few-shot Learning**: 각 태스크별 예시 포함
- **Chain-of-Thought**: 복잡한 판단 시 단계별 추론 유도
- **Structured Output**: JSON 형식 출력 강제

### Performance Optimization
- **Index Caching**: 검색 인덱스를 메모리에 캐싱 (재로드 방지)
- **Batch Processing**: 여러 조항을 한 번에 검증 (API 호출 최소화)
- **Async Processing**: Celery를 통한 비동기 작업 처리

### Scalability Considerations
- **Horizontal Scaling**: Celery worker 수 증가로 처리 용량 확장
- **Index Sharding**: 인덱스 크기 증가 시 샤딩 고려
- **Caching Strategy**: Redis를 활용한 결과 캐싱

### Security
- **File Upload Validation**: DOCX 파일 형식 검증, 악성 파일 차단
- **API Rate Limiting**: 과도한 요청 방지
- **Data Privacy**: 업로드된 계약서는 검증 후 삭제 (또는 암호화 저장)

### Monitoring & Logging
- **Task Monitoring**: Celery Flower를 통한 작업 모니터링
- **Error Tracking**: Sentry 또는 유사 도구로 에러 추적
- **Performance Metrics**: 검증 시간, API 호출 횟수, 성공률 등 기록


## Compatibility with Existing System

### Existing Chunk Structure

현재 표준계약서는 **항/호 단위**(조의 하위항목 중 최상위 항목)로 청킹되어 있으며, 다음 구조를 사용합니다:

**조 본문 청크 예시**:
```json
{
  "id": "제1조 조본문",
  "global_id": "urn:std:provide:art:001:att",
  "unit_type": "articleText",
  "parent_id": "제1조",
  "title": "목적",
  "order_index": 1,
  "text_raw": "  본 계약은 ○○○(이하 "데이터제공자"라 한다)가...",
  "text_norm": "본 계약은 ○○○(이하 "데이터제공자"라 한다)가...",
  "anchors": [],
  "source_file": "provide_std_contract_structured.json"
}
```

**항 청크 예시**:
```json
{
  "id": "제2조 제1항",
  "global_id": "urn:std:provide:art:002:cla:001",
  "unit_type": "clause",
  "parent_id": "제2조",
  "title": "정의",
  "order_index": 3,
  "text_raw": "  ① 본 계약에서 사용하는 용어의 정의는 다음과 같다.\n  1. "데이터"란...\n  2. "대상데이터"는...",
  "text_norm": "본 계약에서 사용하는 용어의 정의는 다음과 같다.//"데이터"란...//"대상데이터"는...",
  "anchors": [
    {
      "unit_type": "subClause",
      "offset_raw": 45,
      "offset_norm": 30,
      "breadcrumb": "제2조 제1항 제1호"
    },
    {
      "unit_type": "subClause",
      "offset_raw": 120,
      "offset_norm": 85,
      "breadcrumb": "제2조 제1항 제2호"
    }
  ],
  "source_file": "provide_std_contract_structured.json"
}
```

**호 청크 예시** (조의 직접 하위항목인 경우):
```json
{
  "id": "제5조 제1호",
  "global_id": "urn:std:provide:art:005:sub:001",
  "unit_type": "subClause",
  "parent_id": "제5조",
  "title": "데이터 제공 범위",
  "order_index": 12,
  "text_raw": "  1. 데이터의 형식 및 포맷\n    가. CSV 형식\n    나. JSON 형식",
  "text_norm": "데이터의 형식 및 포맷//CSV 형식//JSON 형식",
  "anchors": [
    {
      "unit_type": "subSubClause",
      "offset_raw": 20,
      "offset_norm": 15,
      "breadcrumb": "제5조 제1호 제1목"
    }
  ],
  "source_file": "provide_std_contract_structured.json"
}
```

### Design Compatibility Notes

1. **Multi-Vector Retrieval 전략 수정**:
   - 기존 청크는 **항/호 단위**이며, `parent_id`로 조 번호 참조 (예: "제1조")
   - 설계 문서의 Multi-Vector 전략이 정확함: 항/호 단위 검색 → 조 단위 집계
   - `parent_id`로 그룹화하여 조 단위 점수 산출
   - `anchors` 필드에 하위 항목(호, 목, 표) 정보 포함

2. **Guidebook Chunk Structure**:
   - 활용안내서 청크는 기존 표준계약서 청크와 유사한 구조 사용
   - 필수 필드: `id`, `global_id`, `unit_type`, `parent_id`, `title`, `order_index`, `text_raw`, `text_norm`, `anchors`, `source_file`
   - 추가 필드: `doc_type` ("guidebook"), `chunk_type` (commentary, comparison, checklist), `contract_type`

3. **Search Integration**:
   - 기존 HybridSearcher는 항/호 단위 청크를 전제로 구현됨
   - `_aggregate_results_by_article()` 메서드가 이미 `parent_id` 기반 조 단위 집계 수행
   - 활용안내서 검색 시 동일한 HybridSearcher 재사용 가능

### Required Adjustments

1. **Multi-Vector Strategy 확인**:
   - 설계 문서의 Multi-Vector 전략이 기존 구현과 일치함
   - `parent_id`로 그룹화 → WeightedPooling 적용 → Top-K 선택
   - 추가 구현 필요 없음 (기존 `_aggregate_results_by_article()` 활용)

2. **User Contract Chunking**:
   - 사용자 계약서도 항/호 단위로 청킹 (표준계약서와 동일한 ClauseChunker 사용)
   - 각 청크의 `parent_id`로 조 번호 참조
   - `anchors`에 하위 항목 정보 포함
   - 검증 시 항/호 단위 비교 + anchors 기반 세부 비교

3. **Guidebook Index Separation**:
   - 계약 유형별로 별도 인덱스 구축 (5개 인덱스)
   - 파일명: `guidebook_provide.faiss`, `guidebook_create.faiss`, ...
   - Classification 후 해당 유형의 인덱스만 로드
   - 각 인덱스는 해당 유형의 commentary, comparison, checklist 청크 포함

