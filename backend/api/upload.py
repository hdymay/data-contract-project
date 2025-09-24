"""
파일 업로드 API
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from services.pdf_processor import PDFProcessor
from models.schemas import UploadResponse

router = APIRouter()

@router.post("/", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """파일 업로드"""
    try:
        # 파일 검증
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")
        
        # PDF 처리
        processor = PDFProcessor()
        result = await processor.process_file(file)
        
        return UploadResponse(
            success=True,
            message="파일 업로드 성공",
            file_id=result.get("file_id"),
            extracted_text=result.get("extracted_text")
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
