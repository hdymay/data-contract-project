"""공통 서비스 모듈"""

from backend.shared.services.knowledge_base_loader import (
    KnowledgeBaseLoader,
    get_knowledge_base_loader
)

__all__ = [
    'KnowledgeBaseLoader',
    'get_knowledge_base_loader'
]
