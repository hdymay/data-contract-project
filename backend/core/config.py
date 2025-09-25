"""
설정 관리
"""
import os
from typing import Optional

class Settings:
    """애플리케이션 설정"""
    
    # API 설정
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "데이터 표준계약 검증 API"
    
    # 데이터베이스 설정
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/database/contracts.db")
    
    # Redis 설정
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # OpenAI 설정
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    
    # 파일 설정
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./data/uploads")
    REPORT_DIR: str = os.getenv("REPORT_DIR", "./data/reports")
    
    # 검색 설정
    FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", "./data/embeddings/faiss_index")
    WHOOSH_INDEX_PATH: str = os.getenv("WHOOSH_INDEX_PATH", "./data/embeddings/whoosh_index")
    
    # 개발 환경 설정
    DEBUG: bool = True

settings = Settings()
