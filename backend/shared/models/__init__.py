"""
Shared data models for contract verification system
"""

from .contract_models import (
    ClauseData,
    VerificationDecision,
    MatchResult,
    VerificationResult,
    UnmatchedUserClause,
    MissingClauseAnalysis,
    ContractDocument,
    ClassificationResult
)

__all__ = [
    "ClauseData",
    "VerificationDecision",
    "MatchResult",
    "VerificationResult",
    "UnmatchedUserClause",
    "MissingClauseAnalysis",
    "ContractDocument",
    "ClassificationResult"
]
