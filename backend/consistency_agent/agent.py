﻿from celery import Celery, chain
from backend.shared.core.celery_app import celery_app
from backend.shared.database import get_db, ValidationResult, ContractDocument, ClassificationResult
from backend.shared.services.knowledge_base_loader import KnowledgeBaseLoader
from .a1_node.a1_node import CompletenessCheckNode
from .a3_node.a3_node import ContentAnalysisNode
import logging
import os
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="consistency.check_completeness", queue="consistency_validation")
def check_completeness_task(self, contract_id: str, text_weight: float = 0.7, title_weight: float = 0.3, dense_weight: float = 0.85):
    """
    A1 노드: 완전성 검증 작업

    사용자 계약서 조문이 표준계약서 조문과 매칭되는지 확인하고 누락 조문을 식별

    Args:
        contract_id: 검증할 계약서 ID
        text_weight: 본문 가중치 (기본값 0.7)
        title_weight: 제목 가중치 (기본값 0.3)
        dense_weight: 시멘틱 가중치 (기본값 0.85)

    Returns:
        매칭 결과 (A3에서 사용)
    """
    logger.info(f"A1 노드 완전성 검증 시작: {contract_id}")

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

        # 분류 결과 확인
        classification = db.query(ClassificationResult).filter(
            ClassificationResult.contract_id == contract_id
        ).first()

        if not classification:
            raise ValueError(f"계약서 분류가 완료되지 않았습니다: {contract_id}")

        # 계약 유형
        contract_type = classification.confirmed_type or classification.predicted_type
        if not contract_type:
            raise ValueError(f"계약서 유형을 확인할 수 없습니다: {contract_id}")

        logger.info(f"  계약서 유형: {contract_type}")

        # A1 노드 초기화
        kb_loader = KnowledgeBaseLoader()
        azure_client = _init_azure_client()

        if not azure_client:
            raise ValueError("Azure OpenAI 클라이언트 초기화 실패")

        a1_node = CompletenessCheckNode(
            knowledge_base_loader=kb_loader,
            azure_client=azure_client
        )

        # A1 완전성 검증 수행
        completeness_result = a1_node.check_completeness(
            contract_id=contract_id,
            user_contract=contract.parsed_data,
            contract_type=contract_type,
            text_weight=text_weight,
            title_weight=title_weight,
            dense_weight=dense_weight
        )

        # 기존 검증 결과 확인
        existing_result = db.query(ValidationResult).filter(
            ValidationResult.contract_id == contract_id
        ).first()

        # 검증 결과 저장
        if existing_result:
            # 기존 결과 업데이트
            existing_result.completeness_check = completeness_result
            existing_result.contract_type = contract_type
            db.commit()
            result_id = existing_result.id
        else:
            # 새 결과 생성
            validation_result = ValidationResult(
                contract_id=contract_id,
                contract_type=contract_type,
                completeness_check=completeness_result,
                checklist_validation={"status": "pending"},
                content_analysis={"status": "pending"},
                overall_score=0.0,
                recommendations=[]
            )

            db.add(validation_result)
            db.commit()
            db.refresh(validation_result)
            result_id = validation_result.id

        logger.info(f"A1 노드 검증 완료: {contract_id} "
                   f"(매칭: {completeness_result['matched_user_articles']}/{completeness_result['total_user_articles']}개 조항, "
                   f"누락: {len(completeness_result['missing_standard_articles'])}개)")

        return {
            "status": "completed",
            "contract_id": contract_id,
            "result_id": result_id,
            "completeness_summary": {
                "total_user_articles": completeness_result['total_user_articles'],
                "matched_user_articles": completeness_result['matched_user_articles'],
                "total_standard_articles": completeness_result['total_standard_articles'],
                "matched_standard_articles": completeness_result['matched_standard_articles'],
                "missing_count": len(completeness_result['missing_standard_articles']),
                "processing_time": completeness_result['processing_time']
            }
        }

    except Exception as e:
        logger.error(f"A1 노드 검증 실패: {contract_id}, 오류: {e}")
        return {
            "status": "failed",
            "contract_id": contract_id,
            "error": str(e)
        }

    finally:
        if db:
            db.close()


@celery_app.task(bind=True, name="consistency.analyze_content", queue="consistency_validation")
def analyze_content_task(self, contract_id: str, text_weight: float = 0.7, title_weight: float = 0.3, dense_weight: float = 0.85):
    """
    A3 노드: 내용 분석 작업

    A1의 매칭 결과를 참조하여 매칭된 조문들의 내용을 분석

    Args:
        contract_id: 검증할 계약서 ID
        text_weight: 본문 가중치 (기본값 0.7)
        title_weight: 제목 가중치 (기본값 0.3)
        dense_weight: 시멘틱 가중치 (기본값 0.85)
    """
    logger.info(f"A3 노드 내용 분석 시작: {contract_id}, weights: text={text_weight}, title={title_weight}, dense={dense_weight}")

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

        # 분류 결과 확인
        classification = db.query(ClassificationResult).filter(
            ClassificationResult.contract_id == contract_id
        ).first()

        if not classification:
            raise ValueError(f"계약서 분류가 완료되지 않았습니다: {contract_id}")

        # 계약 유형
        contract_type = classification.confirmed_type or classification.predicted_type
        if not contract_type:
            raise ValueError(f"계약서 유형을 확인할 수 없습니다: {contract_id}")

        logger.info(f"  계약서 유형: {contract_type}")

        # 기존 검증 결과 확인
        existing_result = db.query(ValidationResult).filter(
            ValidationResult.contract_id == contract_id
        ).first()

        if not existing_result:
            raise ValueError(f"A1 결과가 존재하지 않습니다: {contract_id}")

        if not existing_result.completeness_check:
            raise ValueError(f"A1 완전성 검증 결과가 없습니다: {contract_id}")

        completeness_result = existing_result.completeness_check

        # A3 노드 초기화
        kb_loader = KnowledgeBaseLoader()
        azure_client = _init_azure_client()

        if not azure_client:
            raise ValueError("Azure OpenAI 클라이언트 초기화 실패")

        a3_node = ContentAnalysisNode(
            knowledge_base_loader=kb_loader,
            azure_client=azure_client
        )

        # A3 분석 수행 (A1 결과 전달)
        analysis_result = a3_node.analyze_contract(
            contract_id=contract_id,
            user_contract=contract.parsed_data,
            contract_type=contract_type,
            text_weight=text_weight,
            title_weight=title_weight,
            dense_weight=dense_weight
        )

        # 결과 저장
        if existing_result:
            existing_result.content_analysis = analysis_result.to_dict()
            db.commit()
            result_id = existing_result.id
        else:
            validation_result = ValidationResult(
                contract_id=contract_id,
                contract_type=contract_type,
                completeness_check={"status": "pending"},
                checklist_validation={"status": "pending"},
                content_analysis=analysis_result.to_dict(),
                overall_score=0.0,
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


@celery_app.task(bind=True, name="consistency.validate_contract", queue="consistency_validation")
def validate_contract_task(self, contract_id: str, text_weight: float = 0.7, title_weight: float = 0.3, dense_weight: float = 0.85):
    """
    통합 검증 작업: A1 (완전성) → A3 (내용 분석) 순차 실행

    Args:
        contract_id: 검증할 계약서 ID
        text_weight: 본문 가중치 (기본값 0.7)
        title_weight: 제목 가중치 (기본값 0.3)
        dense_weight: 시멘틱 가중치 (기본값 0.85)

    Returns:
        통합 검증 결과
    """
    logger.info(f"통합 검증 시작: {contract_id}")

    try:
        # A1: 완전성 검증
        logger.info(f"  [1/2] A1 완전성 검증 실행 중...")
        a1_result = check_completeness_task(contract_id, text_weight, title_weight, dense_weight)

        if a1_result['status'] != 'completed':
            logger.error(f"  A1 검증 실패: {a1_result.get('error')}")
            return {
                "status": "failed",
                "contract_id": contract_id,
                "error": f"A1 검증 실패: {a1_result.get('error')}",
                "stage": "completeness_check"
            }

        logger.info(f"  [1/2] A1 완전성 검증 완료")

        # A3: 내용 분석 (A1 결과 참조)
        logger.info(f"  [2/2] A3 내용 분석 실행 중...")
        a3_result = analyze_content_task(contract_id, text_weight, title_weight, dense_weight)

        if a3_result['status'] != 'completed':
            logger.error(f"  A3 분석 실패: {a3_result.get('error')}")
            return {
                "status": "partial",
                "contract_id": contract_id,
                "error": f"A3 분석 실패: {a3_result.get('error')}",
                "stage": "content_analysis",
                "a1_result": a1_result
            }

        logger.info(f"  [2/2] A3 내용 분석 완료")

        # 통합 결과 반환
        return {
            "status": "completed",
            "contract_id": contract_id,
            "a1_summary": a1_result.get('completeness_summary'),
            "a3_summary": a3_result.get('analysis_summary'),
            "result_id": a3_result.get('result_id')
        }

    except Exception as e:
        logger.error(f"통합 검증 실패: {contract_id}, 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "status": "failed",
            "contract_id": contract_id,
            "error": str(e)
        }


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
