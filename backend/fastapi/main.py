import sys
from pathlib import Path
sys.path.append('/app')

from fastapi import FastAPI, UploadFile, File, HTTPException
import logging
logger = logging.getLogger("uvicorn.error")

from backend.fastapi.pdf_parser import (
    parse_pdf_with_pymupdf
)

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "FastAPI 서버 실행 중"}


def _temp_file_path(filename: str) -> Path:
    # 메모리에서 바로 파싱할 수 있으면 좋지만, 현재 파서는 파일 경로 필요
    # 컨테이너 내 임시 경로 사용 후 즉시 삭제
    base = Path("/tmp/uploads")
    base.mkdir(parents=True, exist_ok=True)
    return base / filename




@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        filename = Path(file.filename).name
        file_ext = filename.lower().split('.')[-1]
        
        # 지원 형식 확인
        if file_ext not in ['pdf', 'docx', 'txt']:
            raise HTTPException(
                status_code=400, 
                detail="지원하지 않는 파일 형식입니다. (지원: PDF, DOCX, TXT)"
            )

        temp_path = _temp_file_path(filename)
        content = await file.read()
        
        # 파일 저장
        with open(temp_path, 'wb') as f:
            f.write(content)

        # 파일 형식에 따라 처리
        result = {}
        
        if file_ext == 'pdf':
            # PyMuPDF 파싱
            result["pymupdf"] = parse_pdf_with_pymupdf(temp_path)
            result["text"] = result["pymupdf"].get("text", "")
        
        elif file_ext == 'docx':
            # DOCX 텍스트 추출
            try:
                from docx import Document
                doc = Document(str(temp_path))
                text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
                result["text"] = text
                result["paragraphs"] = len([p for p in doc.paragraphs if p.text.strip()])
            except ImportError:
                raise HTTPException(
                    status_code=500, 
                    detail="DOCX 처리를 위해 python-docx가 필요합니다."
                )
        
        elif file_ext == 'txt':
            # TXT 파일 읽기 (여러 인코딩 시도)
            encodings = ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']
            text = None
            used_encoding = None
            
            for encoding in encodings:
                try:
                    with open(temp_path, 'r', encoding=encoding) as f:
                        text = f.read()
                    used_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue
            
            if text is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"파일을 읽을 수 없습니다. 시도한 인코딩: {', '.join(encodings)}"
                )
            
            result["text"] = text
            result["lines"] = len(text.split('\n'))
            result["encoding"] = used_encoding

        return {
            "success": True,
            "filename": filename,
            "file_type": file_ext,
            "size_bytes": len(content),
            **result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"파일 처리 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/verify")
async def verify_contract(file: UploadFile = File(...)):
    """
    계약서 업로드 및 자동 검증
    
    Args:
        file: 업로드된 계약서 파일 (TXT, DOCX, PDF)
    
    Returns:
        검증 결과 요약 및 리포트 경로
    """
    import time
    from datetime import datetime
    
    try:
        start_time = time.time()
        
        filename = Path(file.filename).name
        file_ext = filename.lower().split('.')[-1]
        
        # 지원 형식 확인
        if file_ext not in ['txt', 'docx', 'pdf']:
            raise HTTPException(
                status_code=400,
                detail="지원하지 않는 파일 형식입니다. (지원: TXT, DOCX, PDF)"
            )
        
        logger.info(f"[Verify] 파일 업로드: {filename}")
        
        # 파일 저장
        save_dir = Path("/app/data/source_documents")
        save_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_filename = f"user_contract_{timestamp}.{file_ext}"
        saved_path = save_dir / saved_filename
        
        content = await file.read()
        with open(saved_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"[Verify] 파일 저장: {saved_path}")
        
        # 검증 실행
        logger.info("[Verify] 검증 시작...")
        result = _run_verification_api(str(saved_path))
        
        execution_time = time.time() - start_time
        
        logger.info(f"[Verify] 검증 완료 ({execution_time:.2f}s)")
        
        return {
            "success": True,
            "filename": filename,
            "report_id": result["report_id"],
            "report_path": result["report_path"],
            "verification_summary": {
                "total_standard_clauses": result["total_standard_clauses"],
                "total_user_clauses": result["total_user_clauses"],
                "matched_clauses": result["matched_clauses"],
                "missing_clauses": result["missing_count"],
                "compliance_rate": result["verification_rate"]
            },
            "execution_time": execution_time
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Verify] 검증 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"검증 실패: {str(e)}")


def _run_verification_api(user_contract_path: str):
    """
    API용 검증 실행 함수 (ingestion/ingest.py의 _run_verification 로직 재사용)
    
    Args:
        user_contract_path: 사용자 계약서 파일 경로
    
    Returns:
        검증 결과 딕셔너리
    """
    from backend.clause_verification.node_1_clause_matching.data_loader import ContractDataLoader
    from backend.clause_verification.node_1_clause_matching.verification_engine import ContractVerificationEngine
    from backend.clause_verification.node_1_clause_matching.embedding_service import EmbeddingService
    from backend.clause_verification.node_1_clause_matching.hybrid_search import HybridSearchEngine
    from backend.clause_verification.node_1_clause_matching.llm_verification import LLMVerificationService
    from datetime import datetime
    
    # 표준 계약서 경로
    standard_contract_path = "/app/data/chunked_documents/provide_std_contract_chunks.json"
    
    if not Path(standard_contract_path).exists():
        raise FileNotFoundError(f"표준 계약서를 찾을 수 없습니다: {standard_contract_path}")
    
    if not Path(user_contract_path).exists():
        raise FileNotFoundError(f"사용자 계약서를 찾을 수 없습니다: {user_contract_path}")
    
    logger.info("[Verify] 1단계: 데이터 로드")
    
    # 데이터 로더 초기화
    loader = ContractDataLoader()
    
    # 표준 계약서 로드
    standard_clauses = loader.load_standard_contract()
    logger.info(f"[Verify] 표준 계약서 로드: {len(standard_clauses)}개 조문")
    
    # 사용자 계약서 로드 (파일 형식에 따라 처리)
    file_ext = Path(user_contract_path).suffix.lower()
    
    if file_ext == '.txt':
        # TXT 파일: 여러 인코딩 시도
        encodings = ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig', 'latin-1']
        user_text = None
        for encoding in encodings:
            try:
                with open(user_contract_path, 'r', encoding=encoding) as f:
                    user_text = f.read()
                logger.info(f"[Verify] 파일 인코딩 감지: {encoding}")
                break
            except (UnicodeDecodeError, LookupError):
                continue
        
        if user_text is None:
            raise ValueError(f"파일을 읽을 수 없습니다. 시도한 인코딩: {', '.join(encodings)}")
    
    elif file_ext == '.docx':
        # DOCX 파일: python-docx 사용
        try:
            from docx import Document
            doc = Document(user_contract_path)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            user_text = "\n".join(paragraphs)
            logger.info(f"[Verify] DOCX 파일 처리: {len(paragraphs)}개 문단")
        except ImportError:
            raise ImportError("DOCX 처리를 위해 python-docx가 필요합니다")
    
    elif file_ext == '.pdf':
        # PDF 파일: PyMuPDF 사용
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(user_contract_path)
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            user_text = "\n".join(text_parts)
            doc.close()
            logger.info(f"[Verify] PDF 파일 처리: {len(doc)}페이지")
        except ImportError:
            raise ImportError("PDF 처리를 위해 PyMuPDF가 필요합니다")
    
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {file_ext}")
    
    if not user_text or not user_text.strip():
        raise ValueError("파일에서 텍스트를 추출할 수 없습니다")
    
    user_clauses = loader.load_user_contract_chunked(user_text)
    logger.info(f"[Verify] 사용자 계약서 로드: {len(user_clauses)}개 청크")
    
    logger.info("[Verify] 2단계: 검증 엔진 초기화")
    
    # 서비스 초기화
    embedding_service = EmbeddingService()
    hybrid_search = HybridSearchEngine()  # 역방향 검증에서는 사용 안 함
    llm_verification = LLMVerificationService()
    
    # 검증 엔진 초기화
    engine = ContractVerificationEngine(
        embedding_service=embedding_service,
        hybrid_search=hybrid_search,
        llm_verification=llm_verification
    )
    
    logger.info("[Verify] 3단계: 계약서 검증 수행")
    
    # 검증 수행
    result = engine.verify_contract_reverse(
        standard_clauses=standard_clauses,
        user_clauses=user_clauses,
        top_k_candidates=10,
        top_k_titles=5,
        min_confidence=0.5
    )
    
    logger.info(f"[Verify] 검증 완료 - 매칭: {result.matched_clauses}/{result.total_user_clauses}")
    
    logger.info("[Verify] 4단계: 보고서 생성")
    
    # 보고서 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path(f"/app/data/reports/verification_report_{timestamp}.txt")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 간단한 보고서 생성
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("="*100 + "\n")
        f.write("계약서 검증 보고서\n")
        f.write("="*100 + "\n\n")
        f.write(f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("📊 검증 결과 요약\n")
        f.write("-" * 50 + "\n")
        f.write(f"표준 조문 수: {result.total_standard_clauses}개\n")
        f.write(f"사용자 청크 수: {result.total_user_clauses}개\n")
        f.write(f"매칭된 청크: {result.matched_clauses}개\n")
        f.write(f"누락된 조문: {result.missing_count}개\n")
        f.write(f"검증 완료율: {result.verification_rate:.1f}%\n\n")
        
        # 매칭된 조문
        if result.match_results:
            f.write("✅ 매칭된 조문\n")
            f.write("-" * 50 + "\n")
            for match in [m for m in result.match_results if m.is_matched]:
                f.write(f"[{match.standard_clause.id}] {match.standard_clause.title}\n")
                f.write(f"  ← {match.matched_clause.title}\n")
                if match.llm_decision:
                    f.write(f"  신뢰도: {match.llm_decision.confidence:.0%}\n")
                f.write("\n")
        
        # 누락된 조문
        if result.missing_clauses:
            f.write("\n❌ 누락된 조문\n")
            f.write("-" * 50 + "\n")
            for clause in result.missing_clauses:
                f.write(f"[{clause.id}] {clause.title}\n")
                f.write(f"  {clause.text[:100]}...\n\n")
    
    logger.info(f"[Verify] 보고서 저장: {report_path}")
    
    return {
        "report_id": timestamp,
        "report_path": str(report_path),
        "total_standard_clauses": result.total_standard_clauses,
        "total_user_clauses": result.total_user_clauses,
        "matched_clauses": result.matched_clauses,
        "missing_count": result.missing_count,
        "verification_rate": result.verification_rate
    }


@app.get("/report/{report_id}")
async def download_report(report_id: str):
    """
    검증 리포트 다운로드
    
    Args:
        report_id: 리포트 ID (타임스탬프)
    
    Returns:
        FileResponse: 리포트 파일
    """
    from fastapi.responses import FileResponse
    
    try:
        report_path = Path(f"/app/data/reports/verification_report_{report_id}.txt")
        
        if not report_path.exists():
            raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다")
        
        return FileResponse(
            path=str(report_path),
            media_type="text/plain",
            filename=f"verification_report_{report_id}.txt"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리포트 다운로드 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)