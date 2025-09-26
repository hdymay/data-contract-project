from celery import Celery
import os

redis_url = os.getenv('REDIS_URL')

celery_app = Celery('data_contract_validation', broker=redis_url, backend=redis_url)
