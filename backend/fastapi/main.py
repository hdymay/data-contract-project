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
        if not filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="PDF 파일만 허용됩니다.")

        temp_path = _temp_file_path(filename)
        content = await file.read()
        with open(temp_path, 'wb') as f:
            f.write(content)

        # PyMuPDF 파싱만 사용
        pymupdf_result = parse_pdf_with_pymupdf(temp_path)

        return {
            "success": True,
            "filename": filename,
            # 서버 영구 저장 경로는 제공하지 않음
            "pymupdf": pymupdf_result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)