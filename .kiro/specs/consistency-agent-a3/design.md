# Design Document - Consistency Agent A3 Node

## Overview

A3 노드(Content Analysis)는 사용자 계약서의 각 조항 내용을 표준계약서와 비교하여 충실도를 평가하고, 누락된 요소 및 개선 제안을 생성합니다. RAG 기반 검색과 LLM 분석을 결합하여 맥락 기반 유연한 검증을 수행합니다.

## Architecture

### High-Level Flow

```
사용자 계약서 조항
    ↓
[1] RAG 검색 (표준계약서에서 대응 조항 찾기)
    ↓
[2] LLM 내용 비교 (완전성, 명확성, 실무성 평가)
    ↓
[3] 누락 요소 추출 및 개선 제안 생성
    ↓
[4] 결과 구조화 및 저장
    ↓
ValidationResult DB 저장
```

### Component Diagram

```
┌─────────────────────────────────────────┐
│         ContentAnalysisNode             │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │  ArticleMatcher                   │ │
│  │  - RAG 검색으로 대응 조항 찾기      │ │
│  │  - 유사도 기반 매칭                │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │  ContentComparator                │ │
│  │  - LLM 기반 내용 비교              │ │
│  │  - 완전성/명확성/실무성 평가        │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │  SuggestionGenerator              │ │
│  │  - 누락 요소 추출                  │ │
│  │  - 개선 제안 생성                  │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │  SpecialArticleHandler            │ │
│  │  - 특수 조항 감지 및 처리          │ │
│  └───────────────────────────────────┘ │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│      External Dependencies              │
│  - KnowledgeBaseLoader (RAG 검색)       │
│  - AzureOpenAI (LLM 분석)               │
│  - ValidationResult (DB 저장)           │
└─────────────────────────────────────────┘
```

## Components and Interfaces

### 1. ContentAnalysisNode (Main Class)

**Purpose**: A3 노드의 메인 클래스, 전체 분석 프로세스 조율

**Interface**:
```python
class ContentAnalysisNode:
    def __init__(
        self,
        knowledge_base_loader: KnowledgeBaseLoader,
        azure_client: AzureOpenAI,
        similarity_threshold: float = 0.7
    ):
        """
        Args:
            knowledge_base_loader: 지식베이스 로더
            azure_client: Azure OpenAI 클라이언트
            similarity_threshold: 대응 조항 매칭 임계값
        """
        
    def analyze_contract(
        self,
        contract_id: str,
        user_contract: Dict[str, Any],
        contract_type: str
    ) -> Dict[str, Any]:
        """
        계약서 전체 분석
        
        Args:
            contract_id: 계약서 ID
            user_contract: 사용자 계약서 파싱 결과
            contract_type: 분류된 계약 유형
            
        Returns:
            {
                "contract_id": str,
                "contract_type": str,
                "article_analysis": List[ArticleAnalysis],
                "overall_scores": {
                    "completeness": float,
                    "clarity": float,
                    "practicality": float
                },
                "total_articles": int,
                "analyzed_articles": int,
                "special_articles": int
            }
        """
        
    def analyze_article(
        self,
        user_article: Dict[str, Any],
        contract_type: str
    ) -> Dict[str, Any]:
        """
        단일 조항 분석
        
        Args:
            user_article: 사용자 계약서 조항
            contract_type: 계약 유형
            
        Returns:
            ArticleAnalysis 딕셔너리
        """
```

### 2. ArticleMatcher

**Purpose**: RAG 검색으로 표준계약서에서 대응 조항 찾기

**Interface**:
```python
class ArticleMatcher:
    def __init__(
        self,
        knowledge_base_loader: KnowledgeBaseLoader,
        similarity_threshold: float = 0.7
    ):
        """
        Args:
            knowledge_base_loader: 지식베이스 로더
            similarity_threshold: 매칭 임계값
        """
        self.kb_loader = knowledge_base_loader
        self.threshold = similarity_threshold
        
        # 조별 청크 개수 캐싱 (정규화 계산용)
        self.article_chunk_counts = {}
        
    def find_matching_article(
        self,
        user_article: Dict[str, Any],
        contract_type: str,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        대응 조항 검색 (멀티벡터 방식)
        
        사용자 조항의 각 하위항목으로 검색 → 조 단위 취합
        
        Args:
            user_article: 사용자 조항 (content 배열 포함)
            contract_type: 계약 유형
            top_k: 청크 레벨 검색 결과 개수 (기본 10)
            
        Returns:
            {
                "matched": bool,
                "similarity": float,
                "std_article_id": str,  # parent_id (예: "제5조")
                "std_article_title": str,
                "matched_chunks": List[Dict],  # 매칭된 청크들
                "is_special": bool
            }
        """
        
    def _search_with_sub_items(
        self,
        user_article: Dict[str, Any],
        contract_type: str,
        top_k: int = 10
    ) -> List[str]:
        """
        사용자 조항의 각 하위항목으로 검색하여 조 ID 리스트 반환
        
        Returns:
            매칭된 표준계약서 조 ID 리스트 (예: ["제5조", "제3조"])
        """
        
    def _build_search_query(
        self,
        sub_item: str,
        article_title: str
    ) -> str:
        """
        검색 쿼리 생성
        
        하위항목 전체 내용 + 조 제목 (제목은 뒤에 배치하여 가중치 과다 방지)
        
        Args:
            sub_item: 정규화된 하위항목 내용 (전체)
            article_title: 조 제목 (예: "데이터 제공 범위 및 방식")
            
        Returns:
            "{sub_item} {article_title}"
        """
        
    def _normalize_sub_item(self, content: str) -> str:
        """
        사용자 계약서 하위항목 정규화
        
        - 앞뒤 공백 제거
        - ①②③ 등의 원문자 제거
        - 1. 2. 3. 등의 번호 제거
        - (가) (나) 등의 괄호 번호 제거
        """
        
    def _aggregate_chunks_to_articles(
        self,
        chunk_results: List[Dict],
        contract_type: str
    ) -> List[Dict]:
        """
        청크 레벨 검색 결과를 조 단위로 취합
        
        정규화된 평균 점수 사용:
        article_score = (avg_chunk_score) / sqrt(total_chunks_in_article)
        
        Returns:
            조 단위 집계 결과 (점수 순 정렬)
            [
                {
                    "parent_id": "제5조",
                    "score": 0.456,
                    "matched_chunks": [...],
                    "num_matched": 3,
                    "total_chunks": 7
                },
                ...
            ]
        """
        
    def _load_full_article_chunks(
        self,
        parent_id: str,
        contract_type: str
    ) -> List[Dict]:
        """
        표준계약서 조의 모든 청크 로드
        
        해당 조에 속한 모든 하위항목 청크 반환
        """
```

**Implementation Notes**:
- **멀티벡터 검색**: 사용자 조항의 각 하위항목(content 배열)으로 개별 검색
- **하이브리드 검색**: FAISS(0.85) + Whoosh(0.15) 가중합
- **검색 쿼리**: `"{sub_item} {article_title}"` (전체 내용 + 제목은 뒤에)
- **Top-K**: 10개 청크 검색 (정규화로 불균형 해소)
- **조 단위 취합**: 정규화된 평균 점수로 집계
- **정규화 공식**: `avg_score / sqrt(total_chunks)`
- **매칭 임계값**: 최종 조 점수가 0.7 이상이면 매칭 성공
- **캐싱**: 조별 청크 개수를 초기화 시 계산하여 캐싱

### 3. ContentComparator

**Purpose**: LLM 기반 내용 비교 및 평가

**Interface**:
```python
class ContentComparator:
    def __init__(self, azure_client: AzureOpenAI):
        """
        Args:
            azure_client: Azure OpenAI 클라이언트
        """
        
    def compare_articles(
        self,
        user_article: Dict[str, Any],
        std_article: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        조항 내용 비교
        
        Args:
            user_article: 사용자 조항
            std_article: 표준 조항
            
        Returns:
            {
                "completeness": float,  # 0~1
                "clarity": float,       # 0~1
                "practicality": float,  # 0~1
                "missing_elements": List[str],
                "unclear_points": List[str],
                "practical_issues": List[str],
                "reasoning": str
            }
        """
        
    def _build_comparison_prompt(
        self,
        user_article: Dict[str, Any],
        std_article: Dict[str, Any]
    ) -> str:
        """
        LLM 프롬프트 생성
        
        맥락 기반 유연한 평가를 위한 프롬프트 구성
        """
```

**LLM Prompt Template**:
```
당신은 데이터 계약서 검증 전문가입니다. 사용자 계약서 조항과 표준계약서 조항을 비교하여 평가해주세요.

**평가 원칙**:
1. 단순 형식 비교가 아닌 실질적 내용 충족도를 평가하세요
2. 표현이 다르더라도 의미가 유사하면 긍정적으로 평가하세요
3. 계약 당사자의 특수한 목적으로 인한 차이는 문제가 아닙니다
4. 표준계약서는 권장사항이지 필수사항이 아닙니다
5. 사용자 조항이 표준 조항보다 더 상세하거나 추가 내용이 있어도 긍정적으로 평가하세요

**표준계약서 조항** (참고용):
{std_articles_context}

**사용자 계약서 조항** (평가 대상):
제목: {user_title}
내용:
{user_content_formatted}

**평가 항목**:
1. **완전성 (Completeness)**: 표준 조항의 핵심 요소가 포함되어 있는가?
   - 표준 조항에서 다루는 주요 개념과 내용이 사용자 조항에 실질적으로 포함되어 있는지 평가
   - 표현이 다르더라도 의미가 동일하면 포함된 것으로 간주
   - 점수: 0.0 ~ 1.0

2. **명확성 (Clarity)**: 조항 내용이 명확하고 이해하기 쉬운가?
   - 법적 용어가 정확하고 모호하지 않은지
   - 조항의 의도와 적용 범위가 분명한지
   - 점수: 0.0 ~ 1.0

3. **실무적 적절성 (Practicality)**: 실무적으로 적용 가능하고 적절한가?
   - 실제 계약 이행 시 실행 가능한 내용인지
   - 구체적인 절차나 기준이 명시되어 있는지
   - 점수: 0.0 ~ 1.0

**출력 형식** (JSON):
{
  "completeness": 0.85,
  "clarity": 0.90,
  "practicality": 0.80,
  "missing_elements": [
    "데이터 형식 및 포맷 명시 부족",
    "제공 주기가 불명확함"
  ],
  "unclear_points": [
    "데이터 전달 방식이 구체적이지 않음"
  ],
  "practical_issues": [
    "제공 방법의 실행 절차가 명시되지 않음"
  ],
  "reasoning": "전반적으로 표준 조항의 핵심 내용을 포함하고 있으나, 데이터 형식과 제공 주기에 대한 구체적 명시가 부족합니다. 다만 계약 당사자 간 별도 합의를 통해 보완 가능한 수준입니다."
}
```

**Context 구성 예시**:
```
**표준계약서 조항** (참고용):

[제5조 (데이터 제공 범위)]
- 본 계약에서 사용하는 용어의 정의는 다음과 같다.
- "대상데이터"는 본 계약에 따라 데이터제공자가 데이터이용자에게 제공하는 데이터로서...
- 데이터제공자는 대상데이터를 [제공방식]으로 제공한다.

[제3조 (데이터 제공 방법)]
- 데이터 전달은 암호화된 파일 전송, 보안 API 이용 등 안전한 방식으로 이루어진다.
- 제공 주기는 월 단위, 주 단위 등으로 정한다.
```

### 4. SuggestionGenerator

**Purpose**: 누락 요소 및 개선 제안 생성

**Interface**:
```python
class SuggestionGenerator:
    def __init__(self, azure_client: AzureOpenAI):
        """
        Args:
            azure_client: Azure OpenAI 클라이언트
        """
        
    def generate_suggestions(
        self,
        user_article: Dict[str, Any],
        std_article: Dict[str, Any],
        comparison_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        개선 제안 생성
        
        Args:
            user_article: 사용자 조항
            std_article: 표준 조항
            comparison_result: ContentComparator 결과
            
        Returns:
            [
                {
                    "type": "missing_element" | "clarity" | "practicality",
                    "priority": "high" | "medium" | "low",
                    "description": str,
                    "suggestion": str,
                    "example": str,
                    "std_reference": str,
                    "risk_level": "high" | "medium" | "low" | None
                },
                ...
            ]
        """
        
    def _prioritize_suggestions(
        self,
        suggestions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        제안 우선순위 정렬
        
        risk_level과 type을 기준으로 정렬
        """
```

**Suggestion Generation Prompt**:
```
사용자 계약서 조항에 대한 구체적이고 실행 가능한 개선 제안을 생성해주세요.

**누락 요소**: {missing_elements}
**불명확한 점**: {unclear_points}
**실무적 문제**: {practical_issues}

**표준계약서 참조**:
{std_article_content}

각 문제점에 대해 다음 형식으로 제안을 생성하세요:
1. 문제 설명
2. 구체적 개선 방안
3. 예시 문구 (실제 계약서에 추가할 수 있는 문구)
4. 법적 리스크 수준 (있는 경우)

출력 형식 (JSON 배열):
[
  {
    "type": "missing_element",
    "priority": "high",
    "description": "데이터 형식 및 포맷이 명시되지 않음",
    "suggestion": "데이터 형식(CSV, JSON 등)을 명시하여 분쟁 소지를 줄이세요",
    "example": "제공 데이터는 CSV 형식으로 UTF-8 인코딩을 사용한다.",
    "std_reference": "표준계약서 제5조 제1항 참조",
    "risk_level": "medium"
  },
  ...
]
```

### 5. SpecialArticleHandler

**Purpose**: 표준계약서에 없는 특수 조항 처리

**Interface**:
```python
class SpecialArticleHandler:
    def __init__(self, azure_client: AzureOpenAI):
        """
        Args:
            azure_client: Azure OpenAI 클라이언트
        """
        
    def analyze_special_article(
        self,
        user_article: Dict[str, Any],
        contract_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        특수 조항 분석
        
        Args:
            user_article: 사용자 조항
            contract_context: 계약서 전체 맥락 (다른 조항들)
            
        Returns:
            {
                "is_appropriate": bool,
                "purpose": str,
                "assessment": str,
                "recommendation": "keep" | "modify" | "remove",
                "reasoning": str
            }
        """
```

**Special Article Analysis Prompt**:
```
표준계약서에 없는 특수 조항을 분석해주세요.

**특수 조항**:
제목: {title}
내용: {content}

**계약서 맥락**:
- 계약 유형: {contract_type}
- 다른 주요 조항: {other_articles_summary}

**분석 항목**:
1. 조항의 목적이 무엇인가?
2. 계약 맥락에서 적절한가?
3. 법적 리스크가 있는가?
4. 권장 조치는 무엇인가? (유지/수정/제거)

출력 형식 (JSON):
{
  "is_appropriate": true,
  "purpose": "데이터 품질 보증을 위한 조항",
  "assessment": "계약 목적에 부합하며 당사자 간 합의된 특수 조건으로 판단됨",
  "recommendation": "keep",
  "reasoning": "데이터 품질은 계약 이행의 핵심 요소이므로..."
}
```

## Data Models

### ArticleAnalysis

```python
@dataclass
class ArticleAnalysis:
    """단일 조항 분석 결과"""
    user_article_no: int
    user_article_title: str
    
    # 매칭 정보
    matched: bool
    similarity: float
    std_article_no: Optional[int]
    std_article_title: Optional[str]
    is_special: bool
    
    # 평가 점수
    completeness: float
    clarity: float
    practicality: float
    
    # 분석 결과
    missing_elements: List[str]
    unclear_points: List[str]
    practical_issues: List[str]
    
    # 제안
    suggestions: List[Dict[str, Any]]
    
    # 특수 조항 (해당 시)
    special_analysis: Optional[Dict[str, Any]]
    
    # 메타데이터
    reasoning: str
    analysis_timestamp: datetime
```

### ContentAnalysisResult

```python
@dataclass
class ContentAnalysisResult:
    """전체 계약서 분석 결과"""
    contract_id: str
    contract_type: str
    
    # 조항별 분석
    article_analysis: List[ArticleAnalysis]
    
    # 전체 평가
    overall_scores: Dict[str, float]  # completeness, clarity, practicality
    
    # 통계
    total_articles: int
    analyzed_articles: int
    special_articles: int
    
    # 메타데이터
    analysis_timestamp: datetime
    processing_time: float
```

## Error Handling

### RAG 검색 실패
- **원인**: 인덱스 로드 실패, 검색 오류
- **처리**: 
  1. 로그 기록
  2. 해당 조항을 "분석 불가"로 표시
  3. 다음 조항 계속 처리

### LLM API 호출 실패
- **원인**: API 오류, 타임아웃, 할당량 초과
- **처리**:
  1. 지수 백오프로 재시도 (최대 3회)
  2. 재시도 실패 시 기본값 사용 (모든 점수 0.5)
  3. 에러 로그 및 알림

### 메모리 부족
- **원인**: 대용량 계약서, 인덱스 캐싱
- **처리**:
  1. 캐시 정리
  2. 배치 크기 축소
  3. 경고 로그

## Testing Strategy

### Unit Tests
- ArticleMatcher: 다양한 유사도 케이스 테스트
- ContentComparator: LLM 응답 파싱 테스트
- SuggestionGenerator: 제안 생성 로직 테스트
- SpecialArticleHandler: 특수 조항 분류 테스트

### Integration Tests
- 전체 분석 플로우 (RAG → LLM → 제안 생성)
- 지식베이스 로더 연동
- DB 저장 및 조회

### E2E Tests
- 실제 계약서 샘플로 전체 분석
- 다양한 계약 유형 테스트
- 성능 측정 (20개 조항 < 5분)

## Performance Considerations

### 캐싱 전략
- 지식베이스 인덱스: 메모리 캐싱 (재로드 방지)
- 표준계약서 원본: 첫 로드 시 캐싱
- LLM 응답: 동일 쿼리 캐싱 (선택적)

### 배치 처리
- 가능한 경우 여러 조항을 한 번에 LLM에 전송
- API 호출 횟수 최소화

### 병렬 처리
- 조항별 분석은 독립적이므로 병렬 처리 가능 (Phase 2)
- 현재는 순차 처리로 구현

## Implementation Notes

### Phase 1 범위
- A3 노드 단독 구현 (A1, A2 제외)
- 활용안내서 제외 (표준계약서만 사용)
- 순차 처리 (병렬 처리 제외)
- 기본 에러 처리

### Phase 2 확장
- A1, A2 노드 통합
- 활용안내서 참조
- 병렬 처리 최적화
- 고급 에러 처리 및 모니터링
