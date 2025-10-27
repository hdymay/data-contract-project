"""
Data models for Contract Clause Verification System

이 모듈은 backend.shared.models의 공통 모델을 재export합니다.
하위 호환성을 위해 유지됩니다.
"""

# Import from shared models
from backend.shared.models import (
    ClauseData,
    VerificationDecision,
    MatchResult,
    VerificationResult,
    ContractDocument,
    ClassificationResult
)

# Re-export for backward compatibility
__all__ = [
    "ClauseData",
    "VerificationDecision",
    "MatchResult",
    "VerificationResult",
    "ContractDocument",
    "ClassificationResult"
]
