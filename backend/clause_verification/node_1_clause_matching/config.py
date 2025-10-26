"""
Configuration settings for Contract Clause Verification System
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration class for clause verification system"""
    
    # Azure OpenAI Settings
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_ENDPOINT: str = os.getenv("AZURE_ENDPOINT", "")
    AZURE_EMBEDDING_DEPLOYMENT: str = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
    AZURE_LLM_DEPLOYMENT: str = os.getenv("AZURE_LLM_DEPLOYMENT", "gpt-4o")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
    
    # Model Settings
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o")
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    
    # Verification Settings
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))
    BM25_WEIGHT: float = float(os.getenv("BM25_WEIGHT", "0.2"))
    FAISS_WEIGHT: float = float(os.getenv("FAISS_WEIGHT", "0.8"))
    TOP_K_CANDIDATES: int = int(os.getenv("TOP_K_CANDIDATES", "5"))
    
    # Path Settings
    DATA_PATH: Path = Path(os.getenv("DATA_PATH", "./data"))
    CHUNKED_PATH: Path = Path(os.getenv("CHUNKED_PATH", "./data/chunked_documents"))
    VECTORSTORE_PATH: Path = Path(os.getenv("VECTORSTORE_PATH", "./data/search_indexes"))
    REPORTS_PATH: Path = Path(os.getenv("REPORTS_PATH", "./data/reports"))
    
    # Standard Contract Path (fixed)
    # 조문 비교용: provide_std_contract_chunks.json (항 단위 청킹)
    # 해설용: parsed_43_73_table_5_structured.json
    STANDARD_CONTRACT_PATH: Path = CHUNKED_PATH / "provide_std_contract_chunks.json"
    COMMENTARY_PATH: Path = CHUNKED_PATH / "parsed_43_73_table_5_structured.json"
    
    # FAISS Index Settings
    FAISS_INDEX_NAME: str = os.getenv("FAISS_INDEX_NAME", "contract_clauses")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info").upper()
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration settings"""
        required_fields = [
            ("AZURE_OPENAI_API_KEY", cls.AZURE_OPENAI_API_KEY),
            ("AZURE_ENDPOINT", cls.AZURE_ENDPOINT),
        ]
        
        missing_fields = [field for field, value in required_fields if not value]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration: {', '.join(missing_fields)}")
        
        return True
    
    @classmethod
    def ensure_directories(cls) -> None:
        """Ensure all required directories exist"""
        directories = [
            cls.DATA_PATH,
            cls.CHUNKED_PATH,
            cls.VECTORSTORE_PATH,
            cls.REPORTS_PATH,
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


# Create a singleton instance
config = Config()
