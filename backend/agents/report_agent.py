"""
리포트 에이전트
"""
from celery import Celery
from services.llm_service import LLMService
from utils.report_generator import ReportGenerator

app = Celery('report_worker')

@app.task
def generate_report(validation_results: dict, contract_id: str):
    """검증 보고서 생성"""
    try:
        # LLM 서비스
        llm_service = LLMService()
        
        # 리포트 생성
        report_generator = ReportGenerator()
        report = report_generator.generate_report(validation_results)
        
        # PDF 생성
        pdf_path = report_generator.generate_pdf(report, contract_id)
        
        return {
            "contract_id": contract_id,
            "report_path": pdf_path,
            "status": "completed"
        }
        
    except Exception as e:
        return {
            "contract_id": contract_id,
            "error": str(e),
            "status": "failed"
        }
