"""
Pydantic 스키마
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class UploadResponse(BaseModel):
    """파일 업로드 응답"""
    success: bool
    message: str
    file_id: Optional[str] = None
    extracted_text: Optional[str] = None

class AnalysisRequest(BaseModel):
    """분석 요청"""
    contract_text: str
    contract_type: str
    contract_id: str

class AnalysisResponse(BaseModel):
    """분석 응답"""
    analysis_id: str
    status: str
    message: str

class ClassificationRequest(BaseModel):
    """분류 요청"""
    contract_text: str
    contract_id: str

class ClassificationResponse(BaseModel):
    """분류 응답"""
    contract_id: str
    predicted_type: str
    confidence: float
    reasoning: str

class ValidationRequest(BaseModel):
    """검증 요청"""
    contract_data: Dict[str, Any]
    contract_id: str

class ValidationResponse(BaseModel):
    """검증 응답"""
    contract_id: str
    validation_results: Dict[str, Any]
    status: str

class ReportRequest(BaseModel):
    """리포트 요청"""
    validation_results: Dict[str, Any]
    contract_id: str

class ReportResponse(BaseModel):
    """리포트 응답"""
    contract_id: str
    report_path: str
    status: str
