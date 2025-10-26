import sys
from pathlib import Path
sys.path.append('/app')

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import logging
import json
logger = logging.getLogger("uvicorn.error")

from backend.fastapi.user_contract_parser import UserContractParser
from backend.shared.database import init_db, get_db, ContractDocument, ClassificationResult, ValidationResult
from backend.classification_agent.agent import classify_contract_task
from backend.consistency_agent.agent import validate_contract_task

app = FastAPI()


# 시작 시 DB 초기화
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 실행"""
    logger.info("데이터베이스 초기화 중...")
    init_db()
    logger.info("데이터베이스 초기화 완료")
    
    # 지식베이스 상태 확인
    try:
        from backend.shared.services import get_knowledge_base_loader
        loader = get_knowledge_base_loader()
        status = loader.verify_knowledge_base()
        
        logger.info(f"지식베이스 상태: {status['status']}")
        logger.info(f"사용 가능한 계약 유형: {status['available_types']}")
        
        if status['missing_types']:
            logger.warning(f"누락된 계약 유형: {status['missing_types']}")
            logger.warning("ingestion CLI를 실행하여 지식베이스를 구축하세요.")
    except Exception as e:
        logger.error(f"지식베이스 상태 확인 실패: {e}")


@app.get("/")
async def root():
    return {"message": "FastAPI 서버 실행 중"}


@app.get("/api/knowledge-base/status")
async def knowledge_base_status():
    """
    지식베이스 상태 확인
    
    Returns:
        {
            "status": "ok" | "incomplete" | "missing",
            "available_types": [...],
            "missing_types": [...],
            "details": {...}
        }
    """
    try:
        from backend.shared.services import get_knowledge_base_loader
        
        loader = get_knowledge_base_loader()
        status = loader.verify_knowledge_base()
        
        return status
        
    except Exception as e:
        logger.exception(f"지식베이스 상태 확인 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _temp_file_path(filename: str) -> Path:
    """임시 파일 경로 생성"""
    base = Path("/tmp/uploads")
    base.mkdir(parents=True, exist_ok=True)
    return base / filename


@app.post("/upload")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    사용자 계약서 DOCX 업로드 및 파싱
    
    Args:
        file: 업로드된 DOCX 파일
        db: 데이터베이스 세션
        
    Returns:
        {
            "success": bool,
            "filename": str,
            "contract_id": str,
            "structured_data": dict,
            "parsed_metadata": dict
        }
    """
    try:
        filename = Path(file.filename).name
        
        # DOCX 파일만 허용
        if not filename.lower().endswith('.docx'):
            raise HTTPException(status_code=400, detail="DOCX 파일만 허용됩니다.")

        # 임시 파일 저장
        temp_path = _temp_file_path(filename)
        content = await file.read()
        with open(temp_path, 'wb') as f:
            f.write(content)

        # 사용자 계약서 파싱
        parser = UserContractParser()
        result = parser.parse_to_dict(temp_path)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500, 
                detail=f"파싱 실패: {result.get('error', 'Unknown error')}"
            )
        
        # contract_id 생성
        import uuid
        contract_id = f"contract_{uuid.uuid4().hex[:12]}"
        
        # DB에 저장
        contract_doc = ContractDocument(
            contract_id=contract_id,
            filename=filename,
            file_path=str(temp_path),
            parsed_data=result["structured_data"],
            parsed_metadata=result["parsed_metadata"],
            status="parsed"
        )
        db.add(contract_doc)
        db.commit()
        
        logger.info(f"계약서 저장 완료: {contract_id}")

        # 임시 파일 삭제
        try:
            temp_path.unlink()
        except Exception as e:
            logger.warning(f"임시 파일 삭제 실패: {e}")

        # Celery를 통해 분류 작업을 큐에 전송
        try:
            task = classify_contract_task.delay(contract_id)
            logger.info(f"분류 작업 큐에 전송: {contract_id}, Task ID: {task.id}")

            # 계약서 상태를 classifying으로 업데이트
            contract_doc.status = "classifying"
            db.commit()

        except Exception as e:
            logger.error(f"분류 작업 큐 전송 실패: {e}")

        return JSONResponse(
            content={
                "success": True,
                "filename": filename,
                "contract_id": contract_id,
                "structured_data": result["structured_data"],
                "parsed_metadata": result["parsed_metadata"],
                "message": "파싱 완료. 분류 작업이 백그라운드에서 진행 중입니다."
            },
            media_type="application/json; charset=utf-8"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"업로드 처리 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/classification/{contract_id}/start")
async def start_classification(contract_id: str, db: Session = Depends(get_db)):
    """
    계약서 분류 시작 (수동 트리거)

    Args:
        contract_id: 계약서 ID
        db: 데이터베이스 세션

    Returns:
        {
            "success": bool,
            "contract_id": str,
            "task_id": str,
            "message": str
        }
    """
    try:
        # 계약서 조회
        contract = db.query(ContractDocument).filter(
            ContractDocument.contract_id == contract_id
        ).first()

        if not contract:
            raise HTTPException(status_code=404, detail="계약서를 찾을 수 없습니다")

        if not contract.parsed_data:
            raise HTTPException(status_code=400, detail="파싱된 데이터가 없습니다")

        # Celery Task 큐에 전송
        task = classify_contract_task.delay(contract_id)

        # 계약서 상태 업데이트
        contract.status = "classifying"
        db.commit()

        logger.info(f"분류 작업 큐에 전송: {contract_id}, Task ID: {task.id}")

        return {
            "success": True,
            "contract_id": contract_id,
            "task_id": task.id,
            "message": "분류 작업이 시작되었습니다. /api/classification/{contract_id}로 결과를 조회하세요."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"분류 시작 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/classification/{contract_id}")
async def get_classification(contract_id: str, db: Session = Depends(get_db)):
    """
    분류 결과 조회

    Args:
        contract_id: 계약서 ID
        db: 데이터베이스 세션

    Returns:
        분류 결과
    """
    try:
        classification = db.query(ClassificationResult).filter(
            ClassificationResult.contract_id == contract_id
        ).first()

        if not classification:
            raise HTTPException(status_code=404, detail="분류 결과를 찾을 수 없습니다")

        return {
            "contract_id": classification.contract_id,
            "predicted_type": classification.predicted_type,
            "confidence": classification.confidence,
            "scores": classification.scores,
            "confirmed_type": classification.confirmed_type,
            "user_override": classification.user_override
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"분류 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/classification/{contract_id}/confirm")
async def confirm_classification(
    contract_id: str,
    confirmed_type: str,
    db: Session = Depends(get_db)
):
    """
    사용자가 분류 유형 확인/수정

    Args:
        contract_id: 계약서 ID
        confirmed_type: 사용자가 확인한 유형
        db: 데이터베이스 세션

    Returns:
        {
            "success": bool,
            "contract_id": str,
            "confirmed_type": str
        }
    """
    try:
        classification = db.query(ClassificationResult).filter(
            ClassificationResult.contract_id == contract_id
        ).first()

        if not classification:
            raise HTTPException(status_code=404, detail="분류 결과를 찾을 수 없습니다")

        # 사용자가 변경한 경우 기록
        if confirmed_type != classification.predicted_type:
            classification.user_override = confirmed_type

        classification.confirmed_type = confirmed_type

        # 계약서 상태 업데이트
        contract = db.query(ContractDocument).filter(
            ContractDocument.contract_id == contract_id
        ).first()

        if contract:
            contract.status = "classified_confirmed"

        db.commit()

        logger.info(f"분류 확인: {contract_id} -> {confirmed_type}")

        return {
            "success": True,
            "contract_id": contract_id,
            "confirmed_type": confirmed_type
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"분류 확인 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/validation/{contract_id}/start")
async def start_validation(contract_id: str, db: Session = Depends(get_db)):
    """
    계약서 검증 시작 (A3 노드)
    
    Args:
        contract_id: 계약서 ID
        db: 데이터베이스 세션
        
    Returns:
        {
            "message": str,
            "contract_id": str,
            "task_id": str,
            "status": str
        }
    """
    try:
        # 계약서 존재 확인
        contract = db.query(ContractDocument).filter(
            ContractDocument.contract_id == contract_id
        ).first()
        
        if not contract:
            raise HTTPException(status_code=404, detail="계약서를 찾을 수 없습니다")
        
        # 분류 완료 확인
        classification = db.query(ClassificationResult).filter(
            ClassificationResult.contract_id == contract_id
        ).first()
        
        if not classification:
            raise HTTPException(status_code=400, detail="계약서 분류가 완료되지 않았습니다")
        
        # 검증 작업 큐에 전송
        task = validate_contract_task.delay(contract_id)
        
        logger.info(f"검증 작업 시작: {contract_id}, task_id: {task.id}")
        
        return {
            "message": "검증이 시작되었습니다",
            "contract_id": contract_id,
            "task_id": task.id,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"검증 시작 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/validation/{contract_id}")
async def get_validation_result(contract_id: str, db: Session = Depends(get_db)):
    """
    검증 결과 조회
    
    Args:
        contract_id: 계약서 ID
        db: 데이터베이스 세션
        
    Returns:
        검증 결과
    """
    try:
        # 검증 결과 조회
        validation = db.query(ValidationResult).filter(
            ValidationResult.contract_id == contract_id
        ).first()
        
        if not validation:
            return {
                "contract_id": contract_id,
                "status": "not_started",
                "message": "검증이 시작되지 않았습니다"
            }
        
        # A3 결과 확인
        content_analysis = validation.content_analysis
        
        if not content_analysis or content_analysis.get('status') == 'pending':
            return {
                "contract_id": contract_id,
                "status": "processing",
                "message": "검증이 진행 중입니다"
            }
        
        return {
            "contract_id": contract_id,
            "status": "completed",
            "validation_result": {
                "id": validation.id,
                "overall_score": validation.overall_score,
                "content_analysis": content_analysis,
                "completeness_check": validation.completeness_check,
                "checklist_validation": validation.checklist_validation,
                "recommendations": validation.recommendations,
                "created_at": validation.created_at.isoformat() if validation.created_at else None
            }
        }
        
    except Exception as e:
        logger.error(f"검증 결과 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)