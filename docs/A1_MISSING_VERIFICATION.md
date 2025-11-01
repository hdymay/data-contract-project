# A1 누락 조문 재검증 구현

## 개요

A1 노드의 누락 조문 재검증 기능을 현재 프로젝트 구조에 맞춰 조 단위로 재구현했습니다.
A1 브랜치의 프롬프트 스타일과 검증 로직을 반영하여 구현했습니다.

## 구현 내용

### 1. ArticleMatcher - 역방향 검색

**메서드**: `find_matching_user_articles()`

**기능**:
- 표준 조문을 쿼리로 사용하여 사용자 계약서 검색
- 표준 조문의 각 청크를 사용자 조문의 하위항목과 임베딩 기반 비교
- 조 단위로 점수 집계 및 Top-K 반환

**특징**:
- **임베딩 기반 코사인 유사도 계산**
- **사용자 조문 임베딩 캐싱** (EmbeddingLoader 사용)
- **조별 최고 점수 및 평균 점수 계산**
- **임계값 0.5** (코사인 유사도 기준)

### 2. MatchingVerifier - 역방향 LLM 검증

**메서드**: `verify_missing_article_forward()`

**기능**:
- 누락 의심 조문이 실제로 누락되었는지 LLM으로 정밀 판단
- Top-3 후보 조문에 대한 상세 분석
- 증거, 위험도, 권고사항 생성

**LLM 프롬프트 특징** (A1 브랜치 스타일 반영):
- **상세한 판단 기준**: 부분 일치(표현 차이) vs 무관
- **구체적인 작성 가이드**: 각 필드별 2-3문장 등
- **시나리오 형식**: "해당 조항이 없으면..." 형식의 위험도 평가
- **JSON response_format 사용**: 구조화된 응답 보장
- **match_type 필드**: 부분 일치/표현 차이 vs 무관 구분
- **낮은 temperature (0.1)**: 일관성 있는 판단
- **실제 내용 인용 요구**: 후보 조항의 실제 문구를 직접 인용하여 비교

**출력 구조**:
```python
{
    "candidates": [
        {
            "candidate_id": "제3조",
            "is_match": False,
            "confidence": 0.4,
            "match_type": "부분 일치(표현 차이)",
            "reasoning": "후보는 \"데이터 제공 범위는 별도 합의\"라고 명시하여...",
            "risk": "해당 조항이 없으면 데이터 범위 불명확으로 분쟁 발생 가능...",
            "recommendation": "데이터 제공 범위를 명확히 규정하는 조항을 추가할 것을 권장합니다"
        },
        ...
    ],
    "summary": "Top-3 후보 종합 분석...",
    "overall_risk": "해당 조항이 없으면 계약 이행 시..."
}
```

### 3. CompletenessCheckNode - 통합 워크플로우

**메서드**: `_verify_missing_articles()`

**워크플로우**:
```
1. 누락 조문 리스트 입력
   ↓
2. 각 누락 조문에 대해:
   a. ArticleMatcher로 역방향 검색 (Top-3)
   b. MatchingVerifier로 LLM 재검증
   c. 결과 저장
   ↓
3. 통계 집계 및 반환
   - 실제 누락 조문 개수
   - 오탐지 (false positive) 개수
```

## A1 브랜치와의 차이점

| 항목 | A1 브랜치 | 현재 구현 |
|------|----------|----------|
| **검색 단위** | 청크 레벨 | 조 레벨 (청크 취합) |
| **데이터 구조** | ClauseData 객체 | Dict 구조 |
| **임베딩 처리** | 실시간 생성 | 사전 저장 로드 (EmbeddingLoader) |
| **검색 방식** | FAISS 직접 사용 | 임베딩 기반 직접 비교 |
| **유사도 계산** | L2 거리 | 코사인 유사도 |
| **프롬프트** | A1 스타일 | **A1 스타일 반영 ✅** |
| **temperature** | 0.1 | **0.1 ✅** |
| **response_format** | json_object | **json_object ✅** |

## 프롬프트 스타일 반영 사항

### A1 브랜치 프롬프트의 핵심 요소

1. **상세한 판단 기준**
   - 부분 일치(표현 차이): 핵심 내용은 같으나 표현·조건·절차가 다름
   - 무관: 내용적으로 관련없음
   - confidence 범위: 0.6 이상 = 유사, 0.3~0.6 = 부분 유사, 0.3 미만 = 무관

2. **구체적인 작성 가이드**
   - reasoning: 2-3문장, 실제 내용 직접 인용
   - risk: 1-2문장, "해당 조항이 없으면..." 시나리오
   - summary: 3-5문장, 종합 비교
   - overall_risk: 2-3문장, 전체 관점 위험도
   - recommendation: 1-2문장, "~를 추가할 것을 권장합니다"

3. **실제 내용 인용 강조**
   - "후보는 \"[실제 문구]\"라고 명시하여..." 형식
   - 추상적 설명이 아닌 구체적 인용 요구

4. **시나리오 기반 위험도 평가**
   - "해당 조항이 없으면 [구체적 문제 상황]이 발생할 수 있습니다"
   - 계약 체결·이행·분쟁 시 발생 가능한 문제 서술

## 사용 예시

```python
# CompletenessCheckNode 초기화
node = CompletenessCheckNode(
    knowledge_base_loader=kb_loader,
    azure_client=azure_client,
    matching_threshold=0.7
)

# 완전성 검증 (누락 재검증 포함)
result = node.check_completeness(
    contract_id="test_contract",
    user_contract=user_contract_data,
    contract_type="provide",
    text_weight=0.7,
    title_weight=0.3,
    dense_weight=0.85
)

# 결과 확인
for analysis in result['missing_article_analysis']:
    print(f"\n{analysis['standard_article_id']}: {analysis['standard_article_title']}")
    print(f"  실제 누락: {analysis['is_truly_missing']}")
    print(f"  신뢰도: {analysis['confidence']:.2f}")
    print(f"  권고: {analysis['recommendation']}")
    
    if not analysis['is_truly_missing']:
        matched_no = analysis['matched_user_article']['number']
        print(f"  → 제{matched_no}조에 포함됨")
```

## 성능 고려사항

### 임베딩 캐싱
- 사용자 조문 임베딩을 한 번만 로드하여 재사용
- 표준 조문 임베딩은 이미 청크에 포함되어 있음

### 임계값 설정
- 역방향 검색 임계값: 0.5 (코사인 유사도)
- LLM confidence 기준: 0.6 이상 = 유사, 0.3~0.6 = 부분 유사

### LLM 호출 최적화
- 누락 조문당 1회 LLM 호출
- Top-3 후보를 한 번에 분석 (배치 효과)
- JSON response_format으로 파싱 간소화
- temperature 0.1로 일관성 확보

## 테스트 체크리스트

- [ ] 역방향 검색이 올바른 사용자 조문을 찾는지 확인
- [ ] LLM 재검증이 정확한 판단을 내리는지 확인
- [ ] 프롬프트 스타일이 A1 브랜치와 일치하는지 확인
- [ ] 오탐지(false positive)가 올바르게 걸러지는지 확인
- [ ] 실제 누락 조문이 정확히 식별되는지 확인
- [ ] 임베딩 로드 및 캐싱이 정상 작동하는지 확인
- [ ] 결과가 DB에 올바르게 저장되는지 확인
- [ ] 전체 워크플로우 통합 테스트

## 참고 자료

- A1 브랜치 원본 구현: `consistency-agent-a1` 브랜치
- 원본 LLM 검증: `backend/consistency_agent/node_1_clause_matching/llm_verification.py`
- 관련 문서: `docs/DATA_SHARING_AND_DB.md`
- 임베딩 로더: `backend/shared/services/embedding_loader.py`
