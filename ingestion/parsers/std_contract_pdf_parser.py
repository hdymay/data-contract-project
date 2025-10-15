from pathlib import Path
from typing import Dict, Any
import logging
import json

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
    logger.warning("PyMuPDF가 설치되지 않았습니다. pip install pymupdf")


class StdContractPdfParser:
    
    # 지원하는 추출 모드 정의
    SUPPORTED_MODES = ["text", "blocks", "dict", "json", "rawdict", "rawjson", "markdown"]
    
    def __init__(self):
        if fitz is None:
            raise ImportError("PyMuPDF가 필요합니다: pip install pymupdf")
    
    def parse(self, pdf_path: Path, output_dir: Path) -> Dict[str, Path]:
        return self.parse_all_modes(pdf_path, output_dir)
    
    def parse_with_mode(self, pdf_path: Path, mode: str = "rawdict") -> Any:
        if mode not in self.SUPPORTED_MODES:
            raise ValueError(f"지원하지 않는 모드: {mode}. 지원 모드: {self.SUPPORTED_MODES}")
        
        logger.info(f"파싱 시작: {pdf_path.name} (모드: {mode})")
        
        try:
            doc = fitz.open(pdf_path)
            
            # 메타데이터
            metadata = {
                "source_file": pdf_path.name,
                "total_pages": len(doc),
                "metadata": doc.metadata,
                "extraction_mode": mode
            }
            
            # 모드별 추출
            if mode == "text":
                result = self._extract_text_mode(doc, metadata)
            elif mode == "blocks":
                result = self._extract_blocks_mode(doc, metadata)
            elif mode == "dict":
                result = self._extract_dict_mode(doc, metadata)
            elif mode == "json":
                result = self._extract_json_mode(doc, metadata)
            elif mode == "rawdict":
                result = self._extract_rawdict_mode(doc, metadata)
            elif mode == "rawjson":
                result = self._extract_rawjson_mode(doc, metadata)
            elif mode == "markdown":
                result = self._extract_markdown_mode(doc, metadata)
            
            doc.close()
            
            logger.info(f"파싱 완료: {pdf_path.name} ({metadata['total_pages']}페이지, 모드: {mode})")
            return result
            
        except Exception as e:
            logger.error(f"파싱 중 오류 발생: {pdf_path.name} - {e}")
            raise
    
    def parse_all_modes(self, pdf_path: Path, output_dir: Path) -> Dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_files = {}
        
        for mode in self.SUPPORTED_MODES:
            try:
                # 모드별 파싱
                result = self.parse_with_mode(pdf_path, mode)
                
                # 파일명과 확장자 결정
                base_name = pdf_path.stem
                if mode == "text":
                    output_file = output_dir / f"{base_name}_text.txt"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(result)
                elif mode == "markdown":
                    output_file = output_dir / f"{base_name}_markdown.md"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(result)
                elif mode in ["json", "rawjson"]:
                    # 이미 JSON 문자열이므로 그대로 저장
                    output_file = output_dir / f"{base_name}_{mode}.json"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(result)
                else:
                    # blocks, dict, rawdict는 JSON으로 저장
                    output_file = output_dir / f"{base_name}_{mode}.json"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                
                saved_files[mode] = output_file
                logger.info(f"   {mode} 모드 저장 완료: {output_file.name}")
                
            except Exception as e:
                logger.error(f"   {mode} 모드 처리 실패: {e}")
                saved_files[mode] = None
        
        return saved_files
    
    def _extract_text_mode(self, doc, metadata: Dict[str, Any]) -> str:
        """text 모드: 순수 텍스트 추출"""
        pages_text = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            pages_text.append(f"--- Page {page_num + 1} ---\n{text}")
        
        return "\n\n".join(pages_text)
    
    def _extract_blocks_mode(self, doc, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """blocks 모드: 블록 단위 추출 (튜플 → 딕셔너리로 변환)"""
        pages = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            blocks = page.get_text("blocks")
            
            # 튜플을 딕셔너리로 변환 (JSON 직렬화 가능하게)
            blocks_dict = []
            for block in blocks:
                blocks_dict.append({
                    "x0": block[0],
                    "y0": block[1],
                    "x1": block[2],
                    "y1": block[3],
                    "text": block[4],
                    "block_no": block[5],
                    "block_type": block[6]  # 0: text, 1: image
                })
            
            pages.append({
                "page_number": page_num + 1,
                "width": page.rect.width,
                "height": page.rect.height,
                "blocks": blocks_dict
            })
        
        return {**metadata, "pages": pages}
    
    def _extract_dict_mode(self, doc, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """dict 모드: 구조화된 딕셔너리"""
        pages = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_dict = page.get_text("dict")
            
            pages.append({
                "page_number": page_num + 1,
                "data": page_dict
            })
        
        return {**metadata, "pages": pages}
    
    def _extract_json_mode(self, doc, metadata: Dict[str, Any]) -> str:
        """json 모드: dict의 JSON 문자열 버전"""
        pages = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_json = page.get_text("json")
            
            pages.append({
                "page_number": page_num + 1,
                "data": json.loads(page_json)  # JSON 문자열을 파싱
            })
        
        result = {**metadata, "pages": pages}
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    def _extract_rawdict_mode(self, doc, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """rawdict 모드: 가장 상세한 딕셔너리"""
        pages = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            raw_data = page.get_text("rawdict")
            
            pages.append({
                "page_number": page_num + 1,
                "width": page.rect.width,
                "height": page.rect.height,
                "raw_data": raw_data
            })
        
        return {**metadata, "pages": pages}
    
    def _extract_rawjson_mode(self, doc, metadata: Dict[str, Any]) -> str:
        """rawjson 모드: rawdict의 JSON 문자열 버전"""
        pages = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            raw_json = page.get_text("rawjson")
            raw_data = json.loads(raw_json)
            
            pages.append({
                "page_number": page_num + 1,
                "width": page.rect.width,
                "height": page.rect.height,
                "raw_data": raw_data
            })
        
        result = {**metadata, "pages": pages}
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    def _extract_markdown_mode(self, doc, metadata: Dict[str, Any]) -> str:
        """markdown 모드"""
        try:
            pages_text = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text("markdown")
                pages_text.append(f"# Page {page_num + 1}\n\n{text}")
            
            return "\n\n---\n\n".join(pages_text)
        except Exception as e:
            logger.error(f"Markdown 모드 파싱 실패: {e}")
            raise

