"""
Report Agent Module

보고서 생성 에이전트 및 Celery 태스크를 제공합니다.

이 모듈은 report-worker 컨테이너에서만 사용됩니다.
다른 worker에서는 import하지 마세요.
"""

# Empty init to avoid importing dependencies in other workers
__all__ = []
