"""
Consistency Agent
사용자 계약서와 표준 계약서 간 조항 매칭 및 검증
"""

import logging
from pathlib import Path
from backend.shared.core.celery_app import celery_app
from backend.shared.database import SessionLocal, ContractDocument, ClassificationResult

logger = logging.getLogger(__name__)


@celery_app.task(name="consistency.verify_contract", queue="consistency_validation")
def verify_contract_task(contract_id: str):
    """
    Celery Task: 계약서 검증
    
    Args:
        contract_id: 계약서 ID
        
    Returns:
        검증 결과
    """
    db = SessionLocal()
    try:
        logger.info(f"[Celery Task] 계약서 검증 시작: {contract_id}")
        
        # DB에서 계약서 조회
        contract = db.query(ContractDocument).filter(
            ContractDocument.contract_id == contract_id
        ).first()
        
        if not contract:
            raise ValueError(f"계약서를 찾을 수 없습니다: {contract_id}")
        
        # 분류 결과 조회
        classification = db.query(ClassificationResult).filter(
            ClassificationResult.contract_id == contract_id
        ).first()
        
        if not classification:
            raise ValueError(f"분류 결과가 없습니다: {contract_id}")
        
        contract_type = classification.confirmed_type or classification.predicted_type
        
        # chunks.json 경로 가져오기
        chunks_path = contract.parsed_metadata.get("chunks_path")
        if not chunks_path or not Path(chunks_path).exists():
            raise ValueError(f"chunks.json 파일이 없습니다: {chunks_path}")
        
        logger.info(f"계약 유형: {contract_type}, chunks: {chunks_path}")
        
        # 검증 실행
        from backend.consistency_agent.node_1_clause_matching.data_loader import ContractDataLoader
        from backend.consistency_agent.node_1_clause_matching.verifier import ContractVerificationEngine
        from backend.consistency_agent.node_1_clause_matching.hybrid_search import HybridSearchEngine
        from backend.consistency_agent.node_1_clause_matching.llm_verification import LLMVerificationService
        from backend.shared.services.embedding_service import EmbeddingService
        
        loader = ContractDataLoader()
        embedding_service = EmbeddingService()
        hybrid_search = HybridSearchEngine()
        llm_verification = LLMVerificationService()
        verifier = ContractVerificationEngine(
            embedding_service=embedding_service,
            hybrid_search=hybrid_search,
            llm_verification=llm_verification,
            data_loader=loader
        )
        
        # 표준 계약서 로드
        standard_clauses = loader.load_standard_contract(
            contract_type=contract_type,
            use_knowledge_base=True
        )
        
        # 사용자 계약서 로드 (chunks.json)
        import json
        with open(chunks_path, 'r', encoding='utf-8') as f:
            user_chunks = json.load(f)
        
        # ClauseData로 변환
        from backend.consistency_agent.node_1_clause_matching.models import ClauseData
        user_clauses = [
            ClauseData(
                id=chunk['id'],
                title=chunk.get('title', ''),
                subtitle=None,
                type=chunk.get('unit_type', 'article'),
                text=chunk.get('text_raw', ''),
                text_norm=chunk.get('text_norm', ''),
                breadcrumb=chunk.get('title', ''),
                embedding=chunk.get('embedding')
            )
            for chunk in user_chunks
        ]
        
        logger.info(f"표준: {len(standard_clauses)}개, 사용자: {len(user_clauses)}개")
        
        # 검증 수행 (top_k_titles를 3으로 줄여서 속도 개선)
        result = verifier.verify_contract_reverse(
            standard_clauses=standard_clauses,
            user_clauses=user_clauses,
            top_k_titles=3  # 5 → 3으로 줄임
        )
        
        logger.info(f"검증 완료: 매칭 {result.matched_clauses}/{result.total_standard_clauses}")
        
        # 계약서 상태 업데이트
        contract.status = "verified"
        db.commit()
        
        # 보고서 생성 작업 큐에 전송 (import 없이 send_task 사용)
        try:
            from backend.shared.core.celery_app import celery_app
            result_dict = result.to_dict()
            
            # send_task를 사용하면 import 없이 작업 전송 가능
            report_task = celery_app.send_task(
                'backend.report_agent.agent.generate_report',
                args=[contract_id, result_dict],
                queue='report'
            )
            logger.info(f"보고서 생성 작업 큐에 전송: {contract_id}, Task ID: {report_task.id}")
        except Exception as e:
            logger.error(f"보고서 생성 작업 전송 실패: {e}", exc_info=True)
        
        logger.info(f"[Celery Task] 검증 완료: {contract_id}")
        
        return {
            "success": True,
            "contract_id": contract_id,
            "matched_clauses": result.matched_clauses,
            "missing_clauses": len(result.missing_clauses),
            "verification_rate": result.verification_rate
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"[Celery Task] 검증 실패: {contract_id} - {e}")
        
        # 계약서 상태를 error로 업데이트
        contract = db.query(ContractDocument).filter(
            ContractDocument.contract_id == contract_id
        ).first()
        if contract:
            contract.status = "verification_error"
            db.commit()
        
        raise
        
    finally:
        db.close()
