"""
데이터베이스 모델
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Contract(Base):
    """계약서 모델"""
    __tablename__ = "contracts"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(String, unique=True, index=True)
    filename = Column(String)
    contract_type = Column(String)
    extracted_text = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Analysis(Base):
    """분석 결과 모델"""
    __tablename__ = "analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(String, unique=True, index=True)
    contract_id = Column(String, index=True)
    status = Column(String)
    classification_result = Column(Text)  # JSON
    validation_result = Column(Text)  # JSON
    report_path = Column(String)
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime)

class Embedding(Base):
    """임베딩 모델"""
    __tablename__ = "embeddings"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, index=True)
    chunk_id = Column(String, index=True)
    text = Column(Text)
    embedding = Column(Text)  # JSON array
    metadata = Column(Text)  # JSON
    created_at = Column(DateTime, default=func.now())
