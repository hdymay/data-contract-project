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
from backend.shared.database import init_db, get_db, ContractDocument

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

        return JSONResponse(
            content={
                "success": True,
                "filename": filename,
                "contract_id": contract_id,
                "structured_data": result["structured_data"],
                "parsed_metadata": result["parsed_metadata"]
            },
            media_type="application/json; charset=utf-8"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"업로드 처리 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)