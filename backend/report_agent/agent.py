import logging
from pathlib import Path
from celery import Celery

logger = logging.getLogger(__name__)

app = Celery('report_worker')

# Lazy import to avoid dependency issues in other workers
def _get_report_generator():
    from backend.report_agent.generator import ReportGenerator
    return ReportGenerator

def _get_verification_result():
    from backend.shared.models import VerificationResult
    return VerificationResult

@app.task
def generate_report(contract_id: str, verification_result_dict: dict):
    """
    검증 결과를 기반으로 보고서 생성
    
    Args:
        contract_id: 계약서 ID
        verification_result_dict: VerificationResult 객체의 딕셔너리 표현
    
    Returns:
        생성된 보고서 파일 경로들
    """
    try:
        logger.info(f"보고서 생성 시작: {contract_id}")
        
        # Lazy import
        VerificationResult = _get_verification_result()
        ReportGenerator = _get_report_generator()
        
        # VerificationResult 객체 복원
        result = VerificationResult.from_dict(verification_result_dict)
        
        # ReportGenerator 초기화
        output_dir = Path("data/reports") / contract_id
        generator = ReportGenerator(output_dir=output_dir)
        
        # 텍스트 보고서 생성
        text_report_path = generator.generate_text_report(result)
        logger.info(f"텍스트 보고서 생성 완료: {text_report_path}")
        
        return {
            "status": "success",
            "contract_id": contract_id,
            "text_report": text_report_path
        }
        
    except Exception as e:
        logger.error(f"보고서 생성 실패: {contract_id}, 오류: {e}", exc_info=True)
        return {
            "status": "error",
            "contract_id": contract_id,
            "error": str(e)
        }
