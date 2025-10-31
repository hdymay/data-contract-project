# 요구사항 문서

## 소개

A1 노드(완전성 검증)에서 사용자 계약서 조항과 표준계약서 조항 간의 매칭 결과를 구조화된 JSON 형태로 저장하는 기능을 구현합니다. 매칭 성공한 조항은 ContractDocument의 parsed_data["matching_map"]에 저장되고, 누락된 표준 조항은 ValidationResult.completeness_check에 저장됩니다.

## 용어 정의

- **매칭 맵 (Matching Map)**: 사용자 조항과 표준 조항 간의 매칭 관계를 나타내는 JSON 데이터 구조 (매칭 성공한 것만 포함)
- **사용자 조항 (User Clause)**: 사용자가 업로드한 계약서의 조항
  - parsed_data에서 article_id: "user_article_{number:03d}" 형식 (예: "user_article_001", "user_article_014")
  - 매칭 맵에서 user_clause_id: "urn:user:{contract_id}:art:{number:03d}" 형식 (예: "urn:user:contract_123:art:001")
- **표준 조항 (Standard Clause)**: 표준계약서의 조항
  - 지식베이스에서 parent_id: "제n조" 형식 (예: "제1조", "제25조")
  - 지식베이스에서 global_id: "urn:std:{contract_type}:art:{number:03d}" 형식 (예: "urn:std:brokerage_provider:art:025")
  - 매칭 맵에서 std_id: global_id를 그대로 사용
- **M:N 관계**: 사용자 조항 1개가 표준 조항 N개와 매칭 가능하고, 표준 조항 1개가 사용자 조항 M개와 매칭 가능한 관계
- **ArticleMatcher**: RAG 검색(FAISS + Whoosh)을 수행하여 유사한 표준 조항을 찾는 컴포넌트
- **MatchingVerifier**: LLM을 사용하여 RAG 검색 결과 중 실제로 관련있는 조항을 검증하는 컴포넌트
- **CompletenessCheckNode**: A1 노드의 메인 클래스로, ArticleMatcher와 MatchingVerifier를 조율하여 완전성 검증을 수행
- **누락된 표준 조항 (Missing Standard Clauses)**: 어떤 사용자 조항과도 매칭되지 않은 표준 조항

## 현재 A1 노드 구조

### 파일 구성
- `a1_node.py`: CompletenessCheckNode 클래스 (메인 오케스트레이터)
- `article_matcher.py`: ArticleMatcher 클래스 (RAG 검색)
- `matching_verifier.py`: MatchingVerifier 클래스 (LLM 검증)

### 현재 프로세스
1. 사용자 조항 순회
2. ArticleMatcher로 RAG 검색 (FAISS + Whoosh) → 후보 조항 추출
3. MatchingVerifier로 LLM 검증 → 실제 관련 조항 선택
4. 매칭 결과를 메모리에 보관 (현재는 DB 저장 안 함)

### 현재 매칭 스키마 (A1 노드 구현됨, A3가 사용 중)

#### 현재 매칭 스키마 구조
A3 노드가 `ValidationResult.completeness_check`에서 로드하여 사용하는 구조:

```python
# 단일 매칭 항목 (matching_details의 각 요소)
{
    "user_article_no": 1,              # 사용자 조항 번호
    "user_article_title": "목적",       # 사용자 조항 제목
    "matched": True,                   # 매칭 성공 여부
    "matched_articles": ["제1조", "제2조"],  # 매칭된 표준 조항 parent_id 리스트
    "verification_details": []         # LLM 검증 상세 (현재 비어있음)
}
```

#### 현재 매칭 스키마 + Global ID 추가 (A3 호환성 유지)
기존 구조를 유지하면서 global_id 필드만 추가:

```python
# 단일 매칭 항목 (global_id 추가)
{
    "user_article_no": 1,              # 사용자 조항 번호
    "user_article_title": "목적",       # 사용자 조항 제목
    "matched": True,                   # 매칭 성공 여부
    "matched_articles": ["제1조", "제2조"],  # 매칭된 표준 조항 parent_id 리스트 (기존, A3 호환)
    "matched_articles_global_ids": [   # 매칭된 표준 조항 global_id 리스트 (추가)
        "urn:std:brokerage_provider:art:001",
        "urn:std:brokerage_provider:art:002"
    ],
    "match_scores": [0.92, 0.85],      # 각 매칭 조항의 점수 (추가, matched_articles와 순서 동일)
    "verification_details": []         # LLM 검증 상세
}
```

**변경 사항**:
- `matched_articles` 유지 (A3 호환성)
- `matched_articles_global_ids` 추가 (global_id 리스트)
- `match_scores` 추가 (점수 리스트)
- 세 배열의 인덱스가 동일한 조항을 가리킴

### 목표 데이터 구조

#### parsed_data["matching_map"] (매칭 성공한 것에 대한 json도 만들기, 이거 스키마 기반 a1, a2 코드 생성 예정중, 이 스키마 기반으로 활용안내문 체크리스트 json 재구조화 함 , 왠만해서는 지켜줬으면함요 ㅠ)
```python
{
    "contract_type": "brokerage_provider",
    "mappings": [
        {
            "user_clause_id": "urn:user:contract_123:art:001",
            "user_clause_number": 1,
            "matched_std_clauses": [
                {
                    "std_id": "urn:std:brokerage_provider:art:001",
                    "match_score": 0.92
                }
            ]
        },
        {
            "user_clause_id": "urn:user:contract_123:art:014",
            "user_clause_number": 14,
            "matched_std_clauses": [
                {
                    "std_id": "urn:std:brokerage_provider:art:025",
                    "match_score": 0.85
                },
                {
                    "std_id": "urn:std:brokerage_provider:art:026",
                    "match_score": 0.78
                },
                {
                    "std_id": "urn:std:brokerage_provider:art:027",
                    "match_score": 0.72
                }
            ]
        }
    ],
    "created_at": "2025-01-01T00:00:00Z",
    "matching_version": "v1.0"
}
```

#### ValidationResult.completeness_check (누락된 표준 조항)
```python
{
    "total_user_articles": 15,
    "matched_user_articles": 12,
    "total_standard_articles": 20,
    "matched_standard_articles": 14,
    "missing_standard_articles": [
        {
            "std_id": "urn:std:brokerage_provider:art:018",
            "std_title": "손해배상"
        },
        {
            "std_id": "urn:std:brokerage_provider:art:019",
            "std_title": "비밀유지"
        }
    ],
    "processing_time": 5.2,
    "verification_date": "2025-01-01T00:00:00Z"
}
```

## 요구사항

### 요구사항 1: parsed_data에 matching_map 추가

**사용자 스토리:** 개발자로서, 사용자 계약서 데이터에 매칭 맵을 포함시켜야 합니다. 이를 통해 원본 데이터와 매칭 정보를 함께 관리하고 A3 노드에서 재사용할 수 있습니다.

#### 인수 기준

1. A1 노드가 매칭을 완료할 때, 시스템은 ContractDocument.parsed_data에 "matching_map" 키를 추가해야 합니다
2. matching_map이 추가될 때, 시스템은 기존 parsed_data의 다른 필드(articles, embeddings)를 유지해야 합니다
3. matching_map이 저장될 때, 시스템은 contract_type, mappings, created_at, matching_version을 포함해야 합니다
4. parsed_data가 업데이트될 때, 시스템은 DB에 변경사항을 커밋해야 합니다
5. matching_map이 이미 존재할 때, 시스템은 기존 matching_map을 덮어써야 합니다

### 요구사항 2: 매칭 맵 데이터 구조 정의

**사용자 스토리:** 개발자로서, 매칭 맵을 위한 표준화된 JSON 구조가 필요합니다. 이를 통해 모든 컴포넌트가 일관되게 매칭 데이터를 읽고 쓸 수 있습니다.

#### 인수 기준

1. 매칭 맵이 생성될 때, 시스템은 "mappings" 배열에 매칭 성공한 사용자 조항만 포함해야 합니다
2. 사용자 조항이 매칭될 때, 시스템은 user_clause_id, user_clause_number, matched_std_clauses 배열을 포함해야 합니다
3. user_clause_id를 생성할 때, 시스템은 parsed_data의 article_id("user_article_{number:03d}")를 URN 형식("urn:user:{contract_id}:art:{number:03d}")으로 변환해야 합니다
4. user_clause_id 변환 시, 시스템은 contract_id와 article number를 사용하여 고유한 URN을 생성해야 합니다
5. 표준 조항이 매칭될 때, 시스템은 std_id(URN 형식), match_score를 포함해야 합니다
6. std_id를 포함할 때, 시스템은 지식베이스 청크의 global_id 값을 그대로 사용해야 합니다
7. 하나의 사용자 조항이 여러 표준 조항과 매칭될 때, 시스템은 matched_std_clauses 배열에 모든 매칭된 표준 조항을 저장해야 합니다
8. 사용자 조항이 어떤 표준 조항과도 매칭되지 않을 때, 시스템은 해당 사용자 조항을 mappings 배열에서 제외해야 합니다

### 요구사항 3: A1 노드에서 매칭 맵 생성

**사용자 스토리:** A1 노드로서, 조항 매칭 완료 후 매칭 맵을 생성해야 합니다. 이를 통해 매칭 결과를 영구 저장하고 다른 컴포넌트에서 재사용할 수 있습니다.

#### 인수 기준

1. A1 노드가 모든 사용자 조항에 대한 매칭을 완료할 때, 시스템은 matching_details를 매칭 맵 형식으로 변환해야 합니다
2. 매칭 맵이 생성될 때, 시스템은 matched=True인 조항만 mappings 배열에 포함해야 합니다
3. 매칭 맵이 생성될 때, 시스템은 user_article_no를 user_clause_number로 사용해야 합니다
4. 매칭 맵이 생성될 때, 시스템은 matched_articles 리스트를 matched_std_clauses 배열로 변환해야 합니다 (match_score 포함)
5. 매칭 맵이 완성될 때, 시스템은 parsed_data["matching_map"]에 저장하고 DB를 업데이트해야 합니다

### 요구사항 4: 매칭 맵 조회 및 재사용

**사용자 스토리:** A3 노드로서, 저장된 매칭 맵을 조회하여 재사용해야 합니다. 이를 통해 중복 RAG 검색 없이 매칭 결과를 활용할 수 있습니다.

#### 인수 기준

1. A3 노드가 실행될 때, 시스템은 ContractDocument.parsed_data에서 matching_map을 조회할 수 있어야 합니다
2. matching_map이 존재할 때, 시스템은 mappings 배열을 순회하여 매칭된 조항을 처리할 수 있어야 합니다
3. matching_map이 존재하지 않을 때, 시스템은 None을 반환하거나 빈 딕셔너리를 반환해야 합니다
4. matching_map을 조회할 때, 시스템은 user_clause_number로 사용자 조항을 식별할 수 있어야 합니다
5. matching_map을 조회할 때, 시스템은 matched_std_clauses에서 std_id, global_id, match_score를 추출할 수 있어야 합니다
6. global_id를 사용할 때, 시스템은 URN 형식의 global_id를 파싱하여 계약 유형과 조항 번호를 추출할 수 있어야 합니다

### 요구사항 5: M:N 관계 지원

**사용자 스토리:** 매칭 시스템으로서, 사용자 조항과 표준 조항 간의 M:N 관계를 지원해야 합니다. 이를 통해 복잡한 매칭 시나리오를 정확하게 표현할 수 있습니다.

#### 인수 기준

1. 사용자 조항이 여러 표준 조항과 매칭될 때, 시스템은 matched_std_clauses 배열에 모든 매칭된 표준 조항을 저장해야 합니다
2. 여러 사용자 조항이 동일한 표준 조항과 매칭될 때, 시스템은 동일한 std_id가 여러 매핑 항목에 나타나는 것을 허용해야 합니다
3. 사용자 조항에 대해 매칭된 표준 조항을 조회할 때, 시스템은 모든 매칭된 표준 조항 ID를 반환해야 합니다
4. 표준 조항에 매칭된 사용자 조항을 조회할 때, 시스템은 mappings 배열을 순회하여 역방향 조회를 지원해야 합니다
5. 통계를 계산할 때, 시스템은 각 사용자 조항을 매칭된 표준 조항 개수와 관계없이 한 번만 카운트해야 합니다

### 요구사항 6: 매칭 점수 및 Global ID 저장

**사용자 스토리:** 분석가로서, 각 매칭된 표준 조항과 함께 매칭 점수와 전역 식별자가 저장되어야 합니다. 이를 통해 각 매칭의 신뢰도 수준을 이해하고 조항을 고유하게 식별할 수 있습니다.

#### 인수 기준

1. 표준 조항이 매칭될 때, 시스템은 std_id, global_id, match_score를 저장해야 합니다
2. global_id를 저장할 때, 시스템은 지식베이스 청크 데이터에서 해당 조항의 global_id를 조회하여 사용해야 합니다
3. 매칭 점수가 저장될 때, 시스템은 ArticleMatcher의 점수를 사용해야 합니다
4. 매칭 점수가 저장될 때, 시스템은 점수가 0.0과 1.0 사이인지 검증해야 합니다
5. 매칭 데이터를 조회할 때, 시스템은 모든 매칭된 표준 조항에 대한 std_id, global_id, match_score를 포함해야 합니다
6. 매칭된 표준 조항을 정렬할 때, 시스템은 match_score 내림차순 정렬을 지원해야 합니다

### 요구사항 7: 누락된 표준 조항 재검증 및 저장

**사용자 스토리:** 시스템 관리자로서, 누락된 것으로 식별된 표준 조항을 재검증하여 false negative를 줄이고, 최종 누락 조항을 분석 결과로 저장해야 합니다. 이를 통해 정확한 완전성 검증 결과를 제공할 수 있습니다.

#### 인수 기준

1. A1 노드가 1차 매칭을 완료할 때, 시스템은 어떤 사용자 조항과도 매칭되지 않은 표준 조항을 식별해야 합니다
2. 누락 후보 조항이 식별될 때, 시스템은 해당 조항들에 대한 재검증을 수행해야 합니다
3. 재검증을 수행할 때, 시스템은 지식베이스에서 누락 후보 조항의 임베딩 데이터를 조회해야 합니다
4. 재검증을 수행할 때, 시스템은 누락 후보 조항의 임베딩과 사용자 계약서 전체를 비교해야 합니다
5. 재검증 결과 매칭이 발견될 때, 시스템은 해당 조항을 누락 목록에서 제외하고 매칭 맵에 추가해야 합니다
6. 재검증 후에도 매칭되지 않은 조항이 있을 때, 시스템은 ValidationResult.completeness_check에 missing_standard_articles로 저장해야 합니다
7. 누락된 표준 조항이 저장될 때, 시스템은 std_id(URN 형식), std_title을 포함해야 합니다
8. 누락된 표준 조항의 std_id를 포함할 때, 시스템은 지식베이스 청크 데이터에서 해당 조항의 global_id를 조회하여 사용해야 합니다
9. 최종 누락된 표준 조항이 저장될 때, 시스템은 parsed_data["matching_map"]에 포함시키지 않아야 합니다
10. ValidationResult를 조회할 때, 시스템은 completeness_check에서 missing_standard_articles를 추출할 수 있어야 합니다

### 요구사항 8: 누락 조항 재검증 프로세스

**사용자 스토리:** A1 노드로서, 1차 매칭에서 누락된 표준 조항을 사용자 계약서 전체와 재비교하여 false negative를 최소화해야 합니다. 이를 통해 실제로는 존재하지만 놓친 조항을 찾아낼 수 있습니다.

#### 인수 기준

1. 누락 후보 조항이 식별될 때, 시스템은 각 누락 후보에 대해 재검증 프로세스를 시작해야 합니다
2. 재검증을 위해 임베딩을 조회할 때, 시스템은 지식베이스에서 누락 후보 조항의 global_id를 사용하여 해당 조항의 모든 청크 임베딩을 가져와야 합니다
3. 재검증 비교를 수행할 때, 시스템은 누락 후보 조항의 임베딩과 사용자 계약서의 모든 조항 임베딩을 비교해야 합니다
4. 재검증 비교를 수행할 때, 시스템은 1차 매칭보다 낮은 임계값을 사용하여 더 넓은 범위의 유사도를 검토해야 합니다
5. 재검증에서 유사도가 임계값을 초과하는 매칭이 발견될 때, 시스템은 해당 표준 조항과 사용자 조항의 매칭을 기록해야 합니다
6. 재검증에서 매칭이 발견될 때, 시스템은 해당 조항을 누락 목록에서 제거하고 matching_map에 추가해야 합니다
7. 재검증 프로세스가 완료될 때, 시스템은 재검증을 통해 발견된 매칭 개수를 로깅해야 합니다
8. 재검증 후에도 매칭되지 않은 조항만 최종 missing_standard_articles에 포함되어야 합니다

### 요구사항 9: 버전 관리

**사용자 스토리:** 시스템 유지보수자로서, 매칭 결과에 버전 정보가 포함되어야 합니다. 이를 통해 어떤 매칭 알고리즘이 사용되었는지 추적하고 향후 알고리즘 업데이트를 지원할 수 있습니다.

#### 인수 기준

1. 매칭 맵이 생성될 때, 시스템은 matching_version 필드를 포함해야 합니다 (기본값: "v1.0")
2. 매칭 알고리즘이 업데이트될 때, 시스템은 새로운 버전 문자열을 지정할 수 있어야 합니다
3. 매칭 맵을 조회할 때, 시스템은 matching_version을 포함해야 합니다
4. 매칭 맵을 재생성할 때, 시스템은 새로운 알고리즘 버전을 반영하여 matching_version을 업데이트해야 합니다
5. 매칭 맵에 created_at 타임스탬프를 포함하여 생성 시점을 추적할 수 있어야 합니다


### 요구사항 10: 별도 매칭 결과 JSON 파일 생성

**사용자 스토리:** 분석가로서, 매칭 결과를 별도 JSON 파일로 저장하여 독립적으로 분석하고 공유할 수 있어야 합니다. 이를 통해 DB 없이도 매칭 결과를 확인하고 다른 시스템과 통합할 수 있습니다.

#### 인수 기준

1. A1 노드가 완료될 때, 시스템은 매칭 결과를 별도 JSON 파일로 저장해야 합니다
2. 별도 JSON 파일이 생성될 때, 시스템은 contract_id, contract_type, user_to_std_mapping, missing_std_clauses, metadata를 포함해야 합니다
3. user_to_std_mapping은 parsed_data["matching_map"]["mappings"]와 동일한 구조를 가져야 합니다
4. missing_std_clauses는 ValidationResult.completeness_check["missing_standard_articles"]와 동일한 구조를 가져야 합니다
5. metadata는 created_at, matching_version, total_user_articles, matched_user_articles, total_standard_articles, matched_standard_articles를 포함해야 합니다
6. 별도 JSON 파일은 `data/matching_results/{contract_id}_matching.json` 경로에 저장되어야 합니다
7. 디렉토리가 존재하지 않을 때, 시스템은 자동으로 디렉토리를 생성해야 합니다
8. 파일 저장이 실패할 때, 시스템은 에러를 로깅하되 전체 프로세스는 계속 진행해야 합니다





## 추가 고려사항 (향후 논의 필요)

### 역방향 매칭 시 사용자 조항 추가 문제

**시나리오**: 
1차 매칭에서 표준 조항 "제4조"가 누락된 것으로 식별됨
→ 재검증 과정에서 사용자 조항 "제7조"와 매칭됨
→ 사용자 조항 "제7조"는 이미 다른 표준 조항(예: "제10조")과 매칭되어 있음

**문제점**:
- 사용자 조항 "제7조"의 매칭 맵에 표준 조항 "제4조"를 추가해야 함
- 이는 M:N 관계를 지원하므로 기술적으로 가능
- 하지만 별도 JSON 파일 생성 시점과 재검증 시점의 불일치 문제 발생 가능

**논의 필요 사항**:

1. **재검증 매칭 추가 위치**
   - Option A: parsed_data["matching_map"]에 직접 추가 (DB 업데이트)
   - Option B: 별도 JSON 파일에만 추가 (DB는 그대로)
   - Option C: 재검증 결과를 별도 필드에 저장 (예: parsed_data["reverification_matches"])

2. **별도 JSON 파일 생성 시점**
   - Option A: 1차 매칭 완료 후 즉시 생성 (재검증 전)
   - Option B: 재검증 완료 후 생성 (최종 결과만 포함)
   - Option C: 두 번 생성 (1차 매칭 후, 재검증 후)

3. **재검증 매칭 표시 방법**
   - 재검증을 통해 추가된 매칭을 구분할 필요가 있는가?
   - 구분이 필요하다면 `match_source: "primary" | "reverification"` 필드 추가?

**권장 접근 방식 (초안)**:
```json
{
    "user_clause_id": "urn:user:contract_123:art:007",
    "matched_std_clauses": [
        {
            "std_id": "urn:std:brokerage_provider:art:010",
            "match_score": 0.88,
            "match_source": "primary"
        },
        {
            "std_id": "urn:std:brokerage_provider:art:004",
            "match_score": 0.72,
            "match_source": "reverification"
        }
    ]
}
```

**결정 필요**:
- 재검증 매칭을 기존 매칭 맵에 통합할지, 별도로 관리할지
- 별도 JSON 파일 생성 시점 및 업데이트 전략
- 재검증 매칭의 신뢰도가 1차 매칭보다 낮을 수 있음을 어떻게 표현할지
