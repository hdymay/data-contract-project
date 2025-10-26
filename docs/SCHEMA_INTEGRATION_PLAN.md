# 계약서 검증 시스템 - 스키마 통합 계획

## 1. 현재 상황

### 표준 계약서 (DOCX → JSON)
```json
{
  "type": "조",
  "number": 5,
  "text": "제5조(계약의 해지)",
  "content": [
    {
      "type": "항",
      "number": 1,
      "text": "① 갑은 다음 각 호의 사유가 발생한 경우...",
      "content": [
        {
          "type": "호",
          "number": 1,
          "text": "1. 을이 계약을 위반한 경우"
        }
      ]
    }
  ]
}
```

### 사용자 계약서 (TXT → 평문 파싱)
```json
{
  "id": "user-5",
  "title": "제5조(계약의 해지)",
  "type": "조",
  "text": "① 갑은 다음 각 호의 사유가 발생한 경우...\n1. 을이 계약을 위반한 경우"
}
```

## 2. 통합 전략

### Option A: 어댑터 패턴 (단기 - 추천)
```
┌─────────────────┐
│ DOCX Parser     │──→ Structured JSON
└─────────────────┘
         │
         ↓
┌─────────────────┐
│ Flatten Adapter │──→ Flat ClauseData
└─────────────────┘
         │
         ↓
┌─────────────────┐     ┌─────────────────┐
│ TXT Parser      │────→│ ClauseData      │
└─────────────────┘     └─────────────────┘
                                │
                                ↓
                        ┌─────────────────┐
                        │ Verification    │
                        │ Engine          │
                        └─────────────────┘
```

**장점**: 
- 기존 코드 최소 변경
- 빠른 구현
- 점진적 개선 가능

**구현**:
```python
class StructuredToFlatAdapter:
    """계층 구조를 평면 구조로 변환"""
    
    def flatten_article(self, article: dict, level: str = "조") -> List[ClauseData]:
        """
        조 → 항 → 호 → 목 계층을 평면화
        
        level 파라미터로 어느 레벨까지 추출할지 제어:
        - "조": 조 레벨만
        - "항": 조 + 항
        - "호": 조 + 항 + 호
        - "목": 전체
        """
        clauses = []
        
        # 조 레벨
        if level in ["조", "항", "호", "목"]:
            clauses.append(ClauseData(
                id=f"std-{article['number']}",
                title=article['text'],
                type="조",
                text=self._extract_text(article)
            ))
        
        # 항 레벨
        if level in ["항", "호", "목"]:
            for item in article.get('content', []):
                if item['type'] == '항':
                    clauses.append(ClauseData(
                        id=f"std-{article['number']}-{item['number']}",
                        title=f"{article['text']} {item['text'][:20]}",
                        type="항",
                        text=item['text']
                    ))
        
        # 호/목 레벨도 동일하게...
        
        return clauses
```

### Option B: 사용자 계약서 파서 고도화 (중기)
```python
class EnhancedUserContractParser:
    """사용자 계약서에서도 항/호/목 파싱"""
    
    def parse_with_hierarchy(self, text: str) -> List[ClauseData]:
        """
        제N조 → ① → 1. → 가. 패턴 인식
        """
        clauses = []
        
        # 1. 제N조 분리
        articles = self._split_articles(text)
        
        for article in articles:
            # 2. 항(①②③) 분리
            items = self._split_items(article['text'])
            
            for item in items:
                if item['type'] == '항':
                    # 3. 호(1. 2. 3.) 분리
                    subclauses = self._split_subclauses(item['text'])
                    # ...
        
        return clauses
```

### Option C: 통합 데이터 모델 (장기)
```python
@dataclass
class HierarchicalClauseData:
    """계층 구조를 지원하는 통합 모델"""
    id: str
    title: str
    type: Literal["조", "항", "호", "목"]
    text: str
    level: int  # 0=조, 1=항, 2=호, 3=목
    parent_id: Optional[str] = None
    children: List['HierarchicalClauseData'] = field(default_factory=list)
    
    def flatten(self, target_level: str = "조") -> List[ClauseData]:
        """필요시 평면화"""
        pass
    
    def get_full_context(self) -> str:
        """상위 계층 포함 전체 컨텍스트"""
        pass
```

## 3. A2~A4 노드 구현 전략

### A2. Checklist Node
```python
class ChecklistVerifier:
    """체크리스트 기반 검증"""
    
    REQUIRED_CLAUSES = {
        "목적": {"level": "조", "keywords": ["목적", "계약"]},
        "정의": {"level": "조", "keywords": ["정의", "용어"]},
        "데이터제공": {"level": "조", "keywords": ["제공", "전달"]},
        "대가지급": {"level": "항", "keywords": ["대가", "지급", "금액"]},  # 항 레벨!
        "비밀유지": {"level": "호", "keywords": ["비밀", "유지"]},  # 호 레벨!
    }
    
    def verify(self, user_clauses: List[ClauseData]) -> ChecklistResult:
        """
        레벨별로 체크리스트 검증
        - 조 레벨: 필수 조항 존재 여부
        - 항 레벨: 세부 내용 충족도
        - 호 레벨: 구체적 조건 명시 여부
        """
        pass
```

### A3. Completeness Node
```python
class CompletenessVerifier:
    """충실도 검증 - 표준 대비 얼마나 상세한가"""
    
    def verify(self, user_clause: ClauseData, std_clause: ClauseData) -> float:
        """
        표준 계약서의 항/호/목 구조를 기준으로
        사용자 계약서가 얼마나 상세히 작성되었는지 점수화
        
        예: 표준에 3개 항이 있는데 사용자는 1개만 → 33% 충실도
        """
        pass
```

### A4. Explicit Violation Node
```python
class ViolationDetector:
    """비권장 문구/조건 탐지"""
    
    VIOLATION_PATTERNS = {
        "과도한_면책": {
            "level": "항",
            "patterns": ["일체의 책임을 지지 않는다", "모든 책임은 을에게"],
            "severity": "high"
        },
        "불공정조항": {
            "level": "호",
            "patterns": ["갑의 단독 판단", "을의 동의 없이"],
            "severity": "medium"
        }
    }
```

## 4. 단계별 구현 로드맵

### Phase 1: 현재 (조 레벨만)
- [x] 조 레벨 매칭
- [x] 기본 검증 보고서
- [ ] A2 Checklist (조 레벨만)

### Phase 2: 항 레벨 추가 (2-3주)
- [ ] 사용자 계약서 항 파싱 추가
- [ ] Flatten Adapter 구현
- [ ] A2 Checklist (조+항)
- [ ] A3 Completeness (항 레벨)

### Phase 3: 호/목 + 고급 검증 (1-2개월)
- [ ] 전체 계층 파싱
- [ ] HierarchicalClauseData 모델
- [ ] A4 Violation Detector
- [ ] 고급 보고서 (계층별 분석)

## 5. 즉시 적용 가능한 개선

### 5.1 사용자 계약서 파서에 항 파싱 추가
```python
def load_user_contract_from_text(self, text: str) -> List[ClauseData]:
    """항(①②③) 레벨까지 파싱"""
    
    # 1. 제N조 분리 (기존)
    articles = self._split_by_article(text)
    
    clauses = []
    for article in articles:
        # 2. 항 분리 (신규)
        items = re.split(r'([①②③④⑤⑥⑦⑧⑨⑩])', article['text'])
        
        for i, item_text in enumerate(items):
            if re.match(r'[①②③④⑤⑥⑦⑧⑨⑩]', item_text):
                clauses.append(ClauseData(
                    id=f"{article['id']}-{i}",
                    title=f"{article['title']} 항{i}",
                    type="항",
                    text=item_text + items[i+1] if i+1 < len(items) else item_text
                ))
    
    return clauses
```

### 5.2 검증 엔진에 레벨 선택 기능 추가
```python
class VerificationEngine:
    def verify(
        self, 
        user_contract_path: Path,
        verification_level: Literal["조", "항", "호", "목"] = "조"
    ):
        """검증 레벨을 선택 가능하게"""
        
        # 표준 계약서 로드 및 평면화
        std_clauses = self.adapter.flatten(level=verification_level)
        
        # 사용자 계약서 로드 (동일 레벨)
        user_clauses = self.loader.load_user_contract(
            file_path=user_contract_path,
            parse_level=verification_level
        )
        
        # 검증 수행
        results = self._verify_clauses(user_clauses, std_clauses)
        return results
```

## 6. 권장 사항

1. **지금 당장**: Option A (어댑터 패턴) 구현
   - 기존 시스템 유지하면서 확장 가능
   - 1-2일 작업

2. **다음 스프린트**: 사용자 계약서 항 파싱 추가
   - 검증 정확도 크게 향상
   - 1주일 작업

3. **장기 계획**: HierarchicalClauseData 모델로 전환
   - A2~A4 노드 구현 준비
   - 2-3주 작업

이렇게 하면 기존 시스템을 깨지 않으면서 점진적으로 고도화할 수 있습니다!
