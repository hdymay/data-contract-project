from celery import Celery
from backend.shared.core.celery_app import celery_app
from backend.shared.database import get_db, ValidationResult, ContractDocument, ClassificationResult
from backend.shared.services.knowledge_base_loader import KnowledgeBaseLoader
from .nodes.a3_node import ContentAnalysisNode
import logging
import os
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="consistency.validate_contract", queue="consistency_validation")
def validate_contract_task(self, contract_id: str):
    """
    계약서 정합성 검증 작업 (A3 노드)
    
    Args:
        contract_id: 검증할 계약서 ID
    """
    logger.info(f"A3 노드 정합성 검증 시작: {contract_id}")
    
    db = None
    try:
        # 데이터베이스 세션 생성
        db = next(get_db())
        
        # 계약서 데이터 로드
        contract = db.query(ContractDocument).filter(
            ContractDocument.contract_id == contract_id
        ).first()
        
        if not contract:
            raise ValueError(f"계약서를 찾을 수 없습니다: {contract_id}")
        
        # 분류 결과 확인 (ClassificationResult 테이블에서 조회)
        classification = db.query(ClassificationResult).filter(
            ClassificationResult.contract_id == contract_id
        ).first()
        
        if not classification:
            raise ValueError(f"계약서 분류가 완료되지 않았습니다: {contract_id}")
        
        # 사용자가 확인한 유형 또는 예측된 유형 사용
        contract_type = classification.confirmed_type or classification.predicted_type
        if not contract_type:
            raise ValueError(f"계약서 유형을 확인할 수 없습니다: {contract_id}")
        
        logger.info(f"  계약서 유형: {contract_type}")
        
        # 기존 검증 결과 확인
        existing_result = db.query(ValidationResult).filter(
            ValidationResult.contract_id == contract_id
        ).first()
        
        # A3 노드 초기화
        kb_loader = KnowledgeBaseLoader()
        azure_client = _init_azure_client()
        
        if not azure_client:
            raise ValueError("Azure OpenAI 클라이언트 초기화 실패")
        
        a3_node = ContentAnalysisNode(
            knowledge_base_loader=kb_loader,
            azure_client=azure_client
        )
        
        # A3 분석 수행
        analysis_result = a3_node.analyze_contract(
            contract_id=contract_id,
            user_contract=contract.parsed_data,
            contract_type=contract_type
        )
        
        # 검증 결과 저장
        if existing_result:
            # 기존 결과 업데이트
            existing_result.content_analysis = analysis_result.to_dict()
            existing_result.overall_score = 0.0  # 점수 제거
            db.commit()
            result_id = existing_result.id
        else:
            # 새 결과 생성
            validation_result = ValidationResult(
                contract_id=contract_id,
                contract_type=contract_type,
                completeness_check={"status": "pending"},  # A1 노드용
                checklist_validation={"status": "pending"},  # A2 노드용
                content_analysis=analysis_result.to_dict(),  # A3 노드 결과
                overall_score=0.0,  # 점수 제거
                recommendations=[]
            )
            
            db.add(validation_result)
            db.commit()
            db.refresh(validation_result)
            result_id = validation_result.id
        
        logger.info(f"A3 노드 검증 완료: {contract_id} (분석: {analysis_result.analyzed_articles}/{analysis_result.total_articles}개 조항)")
        
        return {
            "status": "completed",
            "contract_id": contract_id,
            "result_id": result_id,
            "analysis_summary": {
                "total_articles": analysis_result.total_articles,
                "analyzed_articles": analysis_result.analyzed_articles,
                "special_articles": analysis_result.special_articles,
                "processing_time": analysis_result.processing_time
            }
        }
        
    except Exception as e:
        logger.error(f"A3 노드 검증 실패: {contract_id}, 오류: {e}")
        return {
            "status": "failed",
            "contract_id": contract_id,
            "error": str(e)
        }
    
    finally:
        if db:
            db.close()


def _init_azure_client():
    """
    Azure OpenAI 클라이언트 초기화
    
    Returns:
        AzureOpenAI 클라이언트 또는 None
    """
    try:
        api_key = os.getenv('AZURE_OPENAI_API_KEY')
        endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        
        if not api_key or not endpoint:
            logger.error("Azure OpenAI 환경 변수가 설정되지 않음")
            return None
        
        client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version="2024-02-01"
        )
        
        return client
        
    except Exception as e:
        logger.error(f"Azure OpenAI 클라이언트 초기화 실패: {e}")
        return None
