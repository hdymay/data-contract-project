import sys
from pathlib import Path
sys.path.append('/app')

from fastapi import FastAPI, UploadFile, File, HTTPException
import logging
logger = logging.getLogger("uvicorn.error")

try:
    import fitz
except Exception:
    fitz = None

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "FastAPI 서버 실행 중"}


def get_upload_dir() -> Path:

    base = Path("/app/data/uploads")
    base.mkdir(parents=True, exist_ok=True)
    return base


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        filename = Path(file.filename).name
        if not filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="PDF 파일만 허용됩니다.")

        target_dir = get_upload_dir()
        target_path = target_dir / filename

        content = await file.read()
        with open(target_path, 'wb') as f:
            f.write(content)

        # 첫 페이지 텍스트 추출 (PyMuPDF)
        extracted = None
        if fitz is None:
            logger.warning("PyMuPDF 미설치")
        else:
            try:
                with fitz.open(target_path) as doc:
                    if doc.page_count > 0:
                        page = doc.load_page(0)
                        extracted = page.get_text("text") or ""
                        # 1000자 컷
                        preview = extracted[:1000]
                        logger.info("[PDF first page extract] %s\n%s", filename, preview)
                    else:
                        logger.info("PDF에 페이지가 없습니다: %s", filename)
            except Exception as e:
                logger.exception("PyMuPDF 처리 중 오류: %s", e)

        return {
            "success": True,
            "filename": filename,
            "path": str(target_path),
            "extracted_preview": (extracted[:200] if extracted else None)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)