# Design 문서

## 개요

A1 노드의 매칭 결과를 구조화된 JSON 형태로 저장하는 기능을 설계합니다. 현재 메모리에만 존재하는 매칭 결과를 DB에 영구 저장하고, A3 노드와의 호환성을 유지하면서 global_id 기반의 새로운 매칭 맵 구조를 추가합니다.

## 아키텍처

### 전체 플로우

```
1. A1 노드 실행
   ↓
2. 매칭 수행 (ArticleMatcher + MatchingVerifier)
   ↓
3. 매칭 결과 생성 (현재 스키마)
   ↓
4. Global ID 조회 및 추가 (지식베이스)
   ↓
5. 매칭 맵 생성 (목표 스키마)
   ↓
6. DB 저장
   ├─ ValidationResult.completeness_check (현재 스키마 + global_id)
   └─ ContractDocument.parsed_data["matching_map"] (목표 스키마)
   ↓
7. 별도 JSON 파일 생성 (선택적)
```

### 컴포넌트 구조

```
CompletenessCheckNode (a1_node.py)
├─ check_completeness()
│  ├─ _check_article() → 현재 매칭 스키마 생성
│  ├─ _enrich_with_global_ids() → global_id 추가 (신규)
│  ├─ _build_matching_map() → 목표 스키마 변환 (신규)
│  ├─ _save_to_db() → DB 저장 (신규)
│  └─ _export_to_json() → JSON 파일 생성 (신규)
│
├─ ArticleMatcher
│  └─ find_matching_article()
│
└─ MatchingVerifier
   └─ verify_matching()
```

## 데이터 변환 로직

### 1단계: 현재 매칭 스키마 생성 (기존)

```python
# _check_article() 반환값
{
    "user_article_no": 1,
    "user_article_title": "목적",
    "matched": True,
    "matched_articles": ["제1조", "제2조"],
    "verification_details": []
}
```

### 2단계: Global ID 추가 (신규)

```python
def _enrich_with_global_ids(
    self,
    matching_details: List[Dict],
    contract_type: str
) -> List[Dict]:
    """
    매칭 결과에 global_id와 match_score 추가
    
    Args:
        matching_details: 현재 매칭 스키마 리스트
        contract_type: 계약 유형
        
    Returns:
        global_id가 추가된 매칭 스키마 리스트
    """
    enriched_details = []
    
    for detail in matching_details:
        if not detail['matched']:
            enriched_details.append(detail)
            continue
            
        # parent_id → global_id 매핑
        matched_articles = detail['matched_articles']
        global_ids = []
        match_scores = []
        
        for parent_id in matched_articles:
            # 지식베이스에서 global_id 조회
            global_id = self._get_global_id(parent_id, contract_type)
            global_ids.append(global_id)
            
            # ArticleMatcher 결과에서 점수 추출
            score = self._get_match_score(parent_id, detail)
            match_scores.append(score)
        
        # 필드 추가
        enriched_detail = dict(detail)
        enriched_detail['matched_articles_global_ids'] = global_ids
        enriched_detail['match_scores'] = match_scores
        enriched_details.append(enriched_detail)
    
    return enriched_details
```

### 3단계: 매칭 맵 생성 (신규)

```python
def _build_matching_map(
    self,
    enriched_details: List[Dict],
    contract_id: str,
    contract_type: str
) -> Dict:
    """
    목표 스키마로 변환
    
    Returns:
        {
            "contract_type": str,
            "mappings": [...],
            "created_at": str,
            "matching_version": str
        }
    """
    mappings = []
    
    for detail in enriched_details:
        if not detail['matched']:
            continue
            
        user_clause_number = detail['user_article_no']
        
        # user_clause_id 생성
        user_clause_id = f"urn:user:{contract_id}:art:{user_clause_number:03d}"
        
        # matched_std_clauses 생성
        matched_std_clauses = []
        global_ids = detail['matched_articles_global_ids']
        scores = detail['match_scores']
        
        for global_id, score in zip(global_ids, scores):
            matched_std_clauses.append({
                "std_id": global_id,
                "match_score": score
            })
        
        mappings.append({
            "user_clause_id": user_clause_id,
            "user_clause_number": user_clause_number,
            "matched_std_clauses": matched_std_clauses
        })
    
    return {
        "contract_type": contract_type,
        "mappings": mappings,
        "created_at": datetime.now().isoformat(),
        "matching_version": "v1.0"
    }
```

## DB 저장 전략  -> 이거는 키로가 지맘대로 만든것 

### ValidationResult.completeness_check

**저장 내용**: 현재 스키마 + global_id (A3 호환성 유지)

```python
{
    "total_user_articles": 15,
    "matched_user_articles": 12,
    "total_standard_articles": 20,
    "matched_standard_articles": 14,
    "matching_details": [  # enriched_details
        {
            "user_article_no": 1,
            "user_article_title": "목적",
            "matched": True,
            "matched_articles": ["제1조", "제2조"],
            "matched_articles_global_ids": ["urn:std:...:001", "urn:std:...:002"],
            "match_scores": [0.92, 0.85],
            "verification_details": []
        }
    ],
    "missing_standard_articles": [
        {
            "std_id": "urn:std:brokerage_provider:art:018",
            "std_title": "손해배상"
        }
    ],
    "processing_time": 5.2,
    "verification_date": "2025-01-01T00:00:00Z"
}
```

### ContractDocument.parsed_data["matching_map"]

**저장 내용**: 목표 스키마 (새로운 매칭 맵)

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
        }
    ],
    "created_at": "2025-01-01T00:00:00Z",
    "matching_version": "v1.0"
}
```

## Global ID 조회 로직

### 지식베이스에서 Global ID 조회

```python
def _get_global_id(
    self,
    parent_id: str,
    contract_type: str
) -> str:
    """
    parent_id로 global_id 조회
    
    Args:
        parent_id: "제1조" 형식
        contract_type: 계약 유형
        
    Returns:
        "urn:std:{contract_type}:art:{number:03d}" 형식
    """
    # 지식베이스 청크 로드
    chunks = self.kb_loader.load_chunks(contract_type)
    
    # parent_id가 일치하는 청크 찾기
    for chunk in chunks:
        if chunk.get('parent_id') == parent_id:
            global_id = chunk.get('global_id')
            if global_id:
                return global_id
    
    # 찾지 못한 경우 parent_id에서 번호 추출하여 생성
    article_number = self._extract_article_number(parent_id)
    return f"urn:std:{contract_type}:art:{article_number:03d}"
```

### 매칭 점수 추출

```python
def _get_match_score(
    self,
    parent_id: str,
    detail: Dict
) -> float:
    """
    ArticleMatcher 결과에서 점수 추출
    
    현재 ArticleMatcher는 조 단위 점수를 제공하지 않으므로
    임시로 기본값 사용 (추후 ArticleMatcher 수정 필요)
    """
    # TODO: ArticleMatcher에서 조 단위 점수 반환하도록 수정
    # 현재는 matched_articles 배열의 순서를 점수로 사용
    matched_articles = detail['matched_articles']
    
    try:
        index = matched_articles.index(parent_id)
        # 첫 번째: 0.9, 두 번째: 0.8, ...
        return max(0.5, 0.9 - (index * 0.1))
    except ValueError:
        return 0.7  # 기본값
```

## A3 호환성 유지

### A3 노드 수정 최소화

A3는 기존대로 `matched_articles` 배열을 사용:

```python
# A3 노드 (_load_a1_matching_results)
matching_details = completeness_check.get('matching_details', [])

for detail in matching_details:
    matched_articles = detail['matched_articles']  # 기존 필드 사용
    # global_id가 필요한 경우에만 추가 필드 사용
    global_ids = detail.get('matched_articles_global_ids', [])
```

### 점진적 마이그레이션

1. **Phase 1**: A1 노드만 수정 (현재 스펙)
   - global_id 필드 추가
   - matching_map 생성
   - A3는 기존 필드 사용

2. **Phase 2**: A3 노드 수정 (향후)
   - global_id 활용
   - matching_map 직접 사용

## 에러 처리

### Global ID 조회 실패

```python
try:
    global_id = self._get_global_id(parent_id, contract_type)
except Exception as e:
    logger.warning(f"Global ID 조회 실패: {parent_id}, 기본값 사용")
    # parent_id에서 번호 추출하여 생성
    article_number = self._extract_article_number(parent_id)
    global_id = f"urn:std:{contract_type}:art:{article_number:03d}"
```

### DB 저장 실패

```python
try:
    # ValidationResult 저장
    self._save_completeness_check(...)
except Exception as e:
    logger.error(f"ValidationResult 저장 실패: {e}")
    # 계속 진행 (matching_map 저장 시도)

try:
    # matching_map 저장
    self._save_matching_map(...)
except Exception as e:
    logger.error(f"matching_map 저장 실패: {e}")
    # 계속 진행 (JSON 파일 생성 시도)
```

### JSON 파일 생성 실패

```python
try:
    self._export_to_json(...)
except Exception as e:
    logger.error(f"JSON 파일 생성 실패: {e}")
    # 에러 로깅만 하고 전체 프로세스는 성공으로 처리
```

## 테스트 전략

### 단위 테스트

1. **_enrich_with_global_ids()**
   - parent_id → global_id 변환 검증
   - 매칭 점수 추출 검증
   - 빈 배열 처리

2. **_build_matching_map()**
   - user_clause_id 생성 검증
   - matched_std_clauses 구조 검증
   - 매칭 안 된 조항 제외 검증

3. **_get_global_id()**
   - 지식베이스 조회 성공
   - 조회 실패 시 fallback
   - 잘못된 parent_id 처리

### 통합 테스트

1. **A1 노드 전체 플로우**
   - 매칭 수행 → DB 저장 → JSON 생성
   - ValidationResult 구조 검증
   - parsed_data["matching_map"] 구조 검증

2. **A3 호환성 테스트**
   - A3가 enriched matching_details 로드
   - 기존 필드로 정상 동작
   - global_id 필드 무시해도 동작

### E2E 테스트

1. **전체 시나리오**
   - 계약서 업로드
   - A1 노드 실행
   - A3 노드 실행
   - 결과 확인

## 성능 고려사항

### Global ID 조회 최적화

```python
# 계약 유형별 parent_id → global_id 매핑 캐싱
self._global_id_cache = {}

def _get_global_id_cached(self, parent_id: str, contract_type: str) -> str:
    cache_key = f"{contract_type}:{parent_id}"
    
    if cache_key not in self._global_id_cache:
        self._global_id_cache[cache_key] = self._get_global_id(parent_id, contract_type)
    
    return self._global_id_cache[cache_key]
```

### 배치 처리

```python
# 모든 parent_id를 한 번에 조회
def _get_global_ids_batch(
    self,
    parent_ids: List[str],
    contract_type: str
) -> Dict[str, str]:
    """
    여러 parent_id의 global_id를 한 번에 조회
    """
    chunks = self.kb_loader.load_chunks(contract_type)
    
    mapping = {}
    for chunk in chunks:
        parent_id = chunk.get('parent_id')
        global_id = chunk.get('global_id')
        if parent_id and global_id:
            mapping[parent_id] = global_id
    
    return mapping
```

## 마이그레이션 계획

### 기존 데이터 마이그레이션

현재 시스템에는 A1 결과가 저장되지 않으므로 마이그레이션 불필요.

### 향후 스키마 변경

1. **matching_version 활용**
   - v1.0: 현재 스키마
   - v2.0: 향후 개선 사항 반영

2. **하위 호환성 유지**
   - 이전 버전 데이터도 읽을 수 있도록 처리
   - version 필드로 분기

```python
def _load_matching_map(self, parsed_data: Dict) -> Dict:
    matching_map = parsed_data.get('matching_map')
    if not matching_map:
        return None
    
    version = matching_map.get('matching_version', 'v1.0')
    
    if version == 'v1.0':
        return matching_map
    elif version == 'v2.0':
        # 향후 버전 처리
        return self._migrate_v2_to_v1(matching_map)
    else:
        logger.warning(f"Unknown matching_version: {version}")
        return matching_map
```
