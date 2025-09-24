"""
데이터 표준계약 검증 API - FastAPI 메인 앱
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import upload, analysis, classification, report
from core.config import settings

# FastAPI 앱 생성
app = FastAPI(
    title="데이터 표준계약 검증 API",
    description="AI 기반 데이터 계약서 분석 및 검증 시스템",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(classification.router, prefix="/api/classification", tags=["classification"])
app.include_router(report.router, prefix="/api/report", tags=["report"])

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {"message": "데이터 표준계약 검증 API 서버가 실행 중입니다."}

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
