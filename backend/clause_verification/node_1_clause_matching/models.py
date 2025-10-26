"""
Data models for Contract Clause Verification System
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class ClauseData:
    """
    계약서의 개별 조문 데이터를 표현하는 모델
    
    Attributes:
        id: 조문 ID (예: "ART-001")
        title: 조문 제목 (예: "목적")
        subtitle: 부제목 (선택적)
        type: 타입 (예: "조", "해설")
        text: 조문 원본 내용 (text_raw)
        text_norm: 정규화된 조문 내용 (검색용)
        breadcrumb: 조문 번호 표시 (예: "제1조")
        embedding: 임베딩 벡터 (캐시용, 선택적)
    """
    id: str
    title: str
    subtitle: Optional[str]
    type: str
    text: str
    text_norm: Optional[str] = None
    breadcrumb: Optional[str] = None
    embedding: Optional[List[float]] = None
    
    def __post_init__(self):
        """Validate data after initialization"""
        if not self.id:
            raise ValueError("Clause ID cannot be empty")
        if not self.text:
            raise ValueError("Clause text cannot be empty")
        # text_norm이 없으면 text를 사용
        if self.text_norm is None:
            self.text_norm = self.text
    
    @property
    def display_title(self) -> str:
        """조문의 표시용 제목 반환"""
        if self.subtitle:
            return f"{self.title} - {self.subtitle}"
        return self.title
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "type": self.type,
            "text": self.text,
            "text_norm": self.text_norm,
        }


@dataclass
class VerificationDecision:
    """
    LLM 검증 결과를 표현하는 모델
    
    Attributes:
        is_match: 매칭 여부
        confidence: 신뢰도 (0.0 ~ 1.0)
        reasoning: 판단 근거
    """
    is_match: bool
    confidence: float
    reasoning: str
    
    def __post_init__(self):
        """Validate confidence score"""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class MatchResult:
    """
    조문 매칭 결과를 표현하는 모델
    
    Attributes:
        standard_clause: 표준 계약서 조문
        matched_clause: 매칭된 사용자 계약서 조문 (선택적)
        bm25_score: BM25 점수 (정규화됨)
        faiss_score: FAISS 유사도 점수 (정규화됨)
        hybrid_score: 결합 점수 (정규화됨)
        bm25_raw_score: BM25 원점수 (정규화 전)
        faiss_raw_distance: FAISS L2 거리 (정규화 전)
        llm_decision: LLM 검증 결과 (선택적)
        is_matched: 최종 매칭 여부
        is_duplicate: 중복 매칭 여부 (이미 매칭된 표준 조문과 재매칭 시도)
        duplicate_reason: 중복 사유
    """
    standard_clause: ClauseData
    matched_clause: Optional[ClauseData]
    bm25_score: float
    faiss_score: float
    hybrid_score: float
    llm_decision: Optional[VerificationDecision]
    is_matched: bool
    bm25_raw_score: Optional[float] = None
    faiss_raw_distance: Optional[float] = None
    is_duplicate: bool = False
    duplicate_reason: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "standard_clause": self.standard_clause.to_dict(),
            "matched_clause": self.matched_clause.to_dict() if self.matched_clause else None,
            "bm25_score": self.bm25_score,
            "faiss_score": self.faiss_score,
            "hybrid_score": self.hybrid_score,
            "llm_decision": {
                "is_match": self.llm_decision.is_match,
                "confidence": self.llm_decision.confidence,
                "reasoning": self.llm_decision.reasoning,
            } if self.llm_decision else None,
            "is_matched": self.is_matched,
        }


@dataclass
class VerificationResult:
    """
    전체 검증 결과를 표현하는 모델
    
    Attributes:
        total_standard_clauses: 표준 계약서 총 조문 수
        matched_clauses: 매칭된 조문 수
        missing_clauses: 누락된 조문 목록
        match_results: 상세 매칭 결과
        duplicate_matches: 중복 매칭 목록
        total_user_clauses: 사용자 계약서 총 조문 수
        verification_date: 검증 수행 일시
        is_complete: 모든 조문 존재 여부
    """
    total_standard_clauses: int
    matched_clauses: int
    missing_clauses: List[ClauseData]
    match_results: List[MatchResult]
    duplicate_matches: List[MatchResult] = field(default_factory=list)
    total_user_clauses: int = 0
    verification_date: datetime = field(default_factory=datetime.now)
    is_complete: bool = field(init=False)
    
    def __post_init__(self):
        """Calculate is_complete after initialization"""
        self.is_complete = self.matched_clauses == self.total_standard_clauses
    

    
    @property
    def verification_rate(self) -> float:
        """검증 완료율 계산 (0.0 ~ 100.0) - 사용자 계약서 기준"""
        if self.total_user_clauses == 0:
            return 0.0
        # 매칭된 사용자 조문 수 계산
        verified_user_clauses = len(set(
            r.matched_clause.id for r in self.match_results 
            if r.is_matched and r.matched_clause
        ))
        return (verified_user_clauses / self.total_user_clauses) * 100
    
    @property
    def missing_count(self) -> int:
        """누락된 조문 개수"""
        return len(self.missing_clauses)
    
    @property
    def duplicate_count(self) -> int:
        """중복 매칭 개수"""
        return len(self.duplicate_matches)
    
    def get_summary(self) -> dict:
        """검증 결과 요약 반환"""
        return {
            "total_standard_clauses": self.total_standard_clauses,
            "total_user_clauses": self.total_user_clauses,
            "matched_clauses": self.matched_clauses,
            "missing_clauses": self.missing_count,
            "duplicate_matches": self.duplicate_count,
            "verification_rate": round(self.verification_rate, 2),
            "is_complete": self.is_complete,
            "verification_date": self.verification_date.isoformat(),
        }
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "summary": self.get_summary(),
            "missing_clauses": [clause.to_dict() for clause in self.missing_clauses],
            "match_results": [result.to_dict() for result in self.match_results],
        }
