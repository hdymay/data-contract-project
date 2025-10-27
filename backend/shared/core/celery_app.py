from celery import Celery
import os

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

# 환경 변수로 어떤 agent를 로드할지 결정
worker_type = os.getenv('WORKER_TYPE', 'all')

# Worker 타입별로 include 설정
include_modules = []
if worker_type == 'classification':
    include_modules = ['backend.classification_agent.agent']
elif worker_type == 'consistency':
    include_modules = ['backend.consistency_agent.agent']
elif worker_type == 'report':
    include_modules = ['backend.report_agent.agent']
else:
    # 기본값: 모든 agent 포함 (FastAPI 등)
    include_modules = [
        'backend.classification_agent.agent',
        'backend.consistency_agent.agent',
        'backend.report_agent.agent'
    ]

celery_app = Celery(
    'data_contract_validation',
    broker=redis_url,
    backend=redis_url,
    include=include_modules
)

# Celery 설정
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Seoul',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30분
    task_soft_time_limit=25 * 60,  # 25분
)
