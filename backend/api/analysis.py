"""
계약서 분석 API
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi import UploadFile, File, Form
from services.workflow_orchestrator import WorkflowOrchestrator
from models.schemas import AnalysisRequest, AnalysisResponse

router = APIRouter()

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_contract(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    contract_type: str = Form(...)
):
    """계약서 분석 시작"""
    try:
        # 워크플로우 오케스트레이터
        orchestrator = WorkflowOrchestrator()
        
        # 분석 작업 시작
        analysis_id = await orchestrator.start_analysis(
            file=file,
            contract_type=contract_type,
            background_tasks=background_tasks
        )
        
        return AnalysisResponse(
            analysis_id=analysis_id,
            status="started",
            message="분석이 시작되었습니다."
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{analysis_id}/status")
async def get_analysis_status(analysis_id: str):
    """분석 상태 조회"""
    try:
        # TODO: 분석 상태 조회 로직
        return {
            "analysis_id": analysis_id,
            "status": "processing",
            "progress": 50
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{analysis_id}/result")
async def get_analysis_result(analysis_id: str):
    """분석 결과 조회"""
    try:
        # TODO: 분석 결과 조회 로직
        return {
            "analysis_id": analysis_id,
            "status": "completed",
            "result": {}
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
