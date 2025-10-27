"""
Consistency Validation Agent Module

정합성 검증 에이전트 및 Celery 태스크를 제공합니다.
"""

from backend.consistency_agent.agent import verify_contract_task

__all__ = ["verify_contract_task"]
