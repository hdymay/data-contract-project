"""
Embedding loader service

Provides helper functions to read stored embeddings for contracts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.shared.database import SessionLocal, ContractDocument

logger = logging.getLogger(__name__)


class EmbeddingLoader:
    """Loads persisted embeddings from contract documents."""

    def __init__(self):
        self._session_factory = SessionLocal

    def load_embeddings(self, contract_id: str) -> Optional[Dict[str, Any]]:
        """Return the full embedding payload stored for the contract."""
        session = self._session_factory()
        try:
            document = (
                session.query(ContractDocument)
                .filter(ContractDocument.contract_id == contract_id)
                .first()
            )
            if not document:
                logger.warning("계약서를 찾을 수 없습니다: %s", contract_id)
                return None
            parsed = document.parsed_data or {}
            embeddings = parsed.get("embeddings")
            if embeddings:
                return embeddings
            return None
        except Exception as exc:
            logger.error("임베딩 로드 실패: %s", exc)
            return None
        finally:
            session.close()

    def load_article_embedding(
        self,
        contract_id: str,
        article_no: int,
        sub_item_index: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Load embedding for a specific article or sub-item.

        Args:
            contract_id: Contract identifier.
            article_no: Target article number.
            sub_item_index: Optional sub-item index (1-based). If omitted, returns the article entry.
        """
        embeddings = self.load_embeddings(contract_id)
        if not embeddings:
            return None

        article_entries = embeddings.get("article_embeddings", [])
        for entry in article_entries:
            if entry.get("article_no") != article_no:
                continue
            if sub_item_index is None:
                return entry
            for sub_item in entry.get("sub_items", []):
                if sub_item.get("index") == sub_item_index:
                    return sub_item
            return None
        return None

    def validate_model_compatibility(
        self,
        embeddings: Optional[Dict[str, Any]],
        current_model: str,
        current_version: str,
    ) -> bool:
        """Check whether the stored embeddings match the expected model and version."""
        if not embeddings:
            return False
        metadata = embeddings.get("metadata", {})
        return (
            metadata.get("model") == current_model
            and metadata.get("embedding_version") == current_version
        )

