"""
사용자 계약서 DOCX 파서
Phase 1: 간단한 조 단위 파싱 (계층 구조 무시)
Phase 2: VLM 기반 유연한 파싱으로 전환 예정
"""

from pathlib import Path
from typing import Dict, Any, List
import logging
import re
import json

logger = logging.getLogger(__name__)

try:
    from docx import Document
except ImportError:
    Document = None
    logger.warning("python-docx가 설치되지 않았습니다. pip install python-docx")


class UserContractParser:
    """
    사용자 계약서 DOCX 파서
    
    Phase 1: 간단한 조 단위 파싱
    - "제n조"로 시작하는 문단만 감지
    - 조의 하위 항목들은 계층 구조 없이 평면적으로 수집
    - 간단한 JSON 구조로 저장
    
    Phase 2: VLM 기반 유연한 파싱 (추후 구현)
    - 다양한 형식의 계약서 지원
    - 비정형 구조 인식
    - 이미지 기반 레이아웃 분석
    """
    
    def __init__(self):
        """초기화"""
        if Document is None:
            raise ImportError("python-docx가 필요합니다: pip install python-docx")
    
    def parse_simple_structure(self, docx_path: Path) -> Dict[str, Any]:
        """
        표준 파서와 동일한 structured.json 형식으로 파싱
        
        Args:
            docx_path: DOCX 파일 경로
            
        Returns:
            {
                "articles": [
                    {
                        "type": "조",
                        "number": int,
                        "text": str,  # "제n조(제목)"
                        "content": [
                            {"type": "조 본문", "text": str},
                            {"type": "호", "number": int, "text": str},
                            ...
                        ]
                    }
                ]
            }
        """
        doc = Document(str(docx_path))
        articles = []
        current_article = None
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            
            # "제n조"로 시작하는지 확인
            article_match = re.match(r'^제(\d+)조', text)
            
            if article_match:
                # 이전 조 저장
                if current_article is not None:
                    articles.append(current_article)
                
                # 새로운 조 시작
                article_num = int(article_match.group(1))
                current_article = {
                    "type": "조",
                    "number": article_num,
                    "text": text,
                    "content": []
                }
            else:
                if current_article is not None:
                    # 호 패턴 확인 (1., 2., 3. 등)
                    ho_match = re.match(r'^\s*(\d+)\.\s+', text)
                    
                    if ho_match:
                        # 호로 인식
                        ho_num = int(ho_match.group(1))
                        current_article["content"].append({
                            "type": "호",
                            "number": ho_num,
                            "text": text
                        })
                    else:
                        # 조 본문으로 인식
                        current_article["content"].append({
                            "type": "조 본문",
                            "text": text
                        })
        
        # 마지막 조 저장
        if current_article is not None:
            articles.append(current_article)
        
        return {
            "articles": articles
        }
    
    def _extract_title(self, text: str) -> str:
        """
        조 텍스트에서 제목 추출
        
        Args:
            text: 조 텍스트 (예: "제1조(목적)")
            
        Returns:
            제목 (예: "목적") 또는 전체 텍스트
        """
        match = re.search(r'제\d+조\((.*?)\)', text)
        if match:
            return match.group(1)
        return text
    
    def parse(self, docx_path: Path, output_dir: Path) -> Dict[str, Any]:
        """
        사용자 계약서 DOCX 파싱 및 structured.json 저장
        
        Args:
            docx_path: DOCX 파일 경로
            output_dir: 출력 디렉토리
            
        Returns:
            파싱 결과 딕셔너리
        """
        try:
            logger.info(f"사용자 계약서 파싱 시작: {docx_path.name}")
            
            # 표준 파서와 동일한 구조로 파싱
            structured_data = self.parse_simple_structure(docx_path)
            
            # 출력 디렉토리 생성
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # structured.json 저장
            base_name = docx_path.stem
            output_file = output_dir / f"{base_name}_structured.json"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(structured_data, f, ensure_ascii=False, indent=2)
            
            # 파싱 메타데이터 생성
            total_articles = len(structured_data.get('articles', []))

            parsed_metadata = {
                "total_articles": total_articles,
                "recognized_articles": total_articles,
                "unrecognized_sections": 0,
                "confidence": 1.0 if total_articles > 0 else 0.0,
                "parser_version": "phase1_structured"
            }

            logger.info(f"파싱 완료: {total_articles}개 조 인식")
            
            return {
                "success": True,
                "structured_path": output_file,
                "structured_data": structured_data,
                "parsed_metadata": parsed_metadata
            }
            
        except Exception as e:
            logger.error(f"파싱 실패: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "error": str(e),
                "parsed_metadata": {
                    "total_articles": 0,
                    "recognized_articles": 0,
                    "unrecognized_sections": 0,
                    "confidence": 0.0,
                    "parser_version": "phase1_structured"
                }
            }
    
    def parse_to_dict(self, docx_path: Path) -> Dict[str, Any]:
        """
        사용자 계약서 파싱 (파일 저장 없이 딕셔너리 반환)
        
        Args:
            docx_path: DOCX 파일 경로
            
        Returns:
            파싱 결과 딕셔너리
        """
        try:
            logger.info(f"사용자 계약서 파싱 시작 (메모리): {docx_path.name}")
            
            # 표준 파서와 동일한 구조로 파싱
            structured_data = self.parse_simple_structure(docx_path)
            
            # 파싱 메타데이터 생성
            total_articles = len(structured_data.get('articles', []))

            parsed_metadata = {
                "total_articles": total_articles,
                "recognized_articles": total_articles,
                "unrecognized_sections": 0,
                "confidence": 1.0 if total_articles > 0 else 0.0,
                "parser_version": "phase1_structured"
            }

            logger.info(f"파싱 완료: {total_articles}개 조 인식")
            
            return {
                "success": True,
                "structured_data": structured_data,
                "parsed_metadata": parsed_metadata
            }
            
        except Exception as e:
            logger.error(f"파싱 실패: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "error": str(e),
                "parsed_metadata": {
                    "total_articles": 0,
                    "recognized_articles": 0,
                    "unrecognized_sections": 0,
                    "confidence": 0.0,
                    "parser_version": "phase1_structured"
                }
            }
