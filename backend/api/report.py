"""
리포트 API
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from services.report_agent import ReportAgent
from models.schemas import ReportRequest, ReportResponse

router = APIRouter()

@router.post("/generate", response_model=ReportResponse)
async def generate_report(request: ReportRequest):
    """검증 보고서 생성"""
    try:
        # 리포트 에이전트
        agent = ReportAgent()
        result = await agent.generate_report(
            validation_results=request.validation_results,
            contract_id=request.contract_id
        )
        
        return ReportResponse(
            contract_id=request.contract_id,
            report_path=result.get("report_path"),
            status=result.get("status")
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{contract_id}/download")
async def download_report(contract_id: str):
    """리포트 다운로드"""
    try:
        # TODO: 리포트 파일 경로 조회
        report_path = f"reports/{contract_id}_report.pdf"
        
        if not os.path.exists(report_path):
            raise HTTPException(status_code=404, detail="리포트 파일을 찾을 수 없습니다.")
        
        return FileResponse(
            path=report_path,
            filename=f"contract_report_{contract_id}.pdf",
            media_type="application/pdf"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
