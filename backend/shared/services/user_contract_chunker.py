"""
사용자 계약서 청킹 서비스
ingestion/processors/chunker.py 기반
"""

import logging
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class UserContractChunker:
    """
    사용자 계약서 청킹 (항 단위 + 세그먼트 기법)
    ingestion/processors/chunker.py의 ClauseChunker 로직 사용
    """
    
    def __init__(self, segment_threshold: int = 1000, segment_size: int = 800):
        """
        초기화
        
        Args:
            segment_threshold: 세그먼트 분할 임계값 (기본 1000자)
            segment_size: 목표 세그먼트 크기 (기본 800자)
        """
        if segment_size >= segment_threshold:
            raise ValueError(f"segment_size({segment_size})는 segment_threshold({segment_threshold})보다 작아야 합니다")
        
        self.segment_threshold = segment_threshold
        self.segment_size = segment_size
        self.segment_counter = 0
        self.contract_type = "user"  # 사용자 계약서
    
    def chunk_structured_data(self, structured_data: Dict[str, Any], source_filename: str) -> List[Dict[str, Any]]:
        """
        structured.json 데이터를 청킹
        
        Args:
            structured_data: 파싱된 structured 데이터
            source_filename: 원본 파일명
            
        Returns:
            청크 리스트
        """
        if 'articles' not in structured_data:
            raise ValueError("'articles' 키가 없습니다")
        
        chunks = []
        order_index = 0
        
        # 조 처리
        for article in structured_data['articles']:
            article_type = article.get('type', '')
            
            if article_type == '조':
                article_no = article.get('number', 0)
                article_text = article.get('text', '')
                title = self._extract_title_from_article_text(article_text)
                parent_id = f"제{article_no}조"
                
                # 조의 하위 항목 처리
                if 'content' in article and isinstance(article['content'], list):
                    for item in article['content']:
                        order_index += 1
                        result = self._process_top_level_item(
                            item,
                            article_no,
                            parent_id,
                            title,
                            source_filename,
                            order_index
                        )
                        if result:
                            # 리스트인 경우 (여러 항으로 분할된 경우)
                            if isinstance(result, list):
                                for chunk in result:
                                    chunk['order_index'] = order_index
                                    chunks.append(chunk)
                                    order_index += 1
                                order_index -= 1
                            else:
                                # 단일 청크인 경우
                                chunks.append(result)
        
        return chunks
    
    def _extract_title_from_article_text(self, text: str) -> str:
        """조 text에서 title 추출"""
        import re
        match = re.search(r'제\d+조\((.*?)\)', text)
        if match:
            return match.group(1)
        return text
    
    def _process_top_level_item(
        self,
        item: Dict,
        article_no: int,
        parent_id: str,
        title: str,
        source_file: str,
        order_index: int
    ):
        """조의 최상위 하위항목 처리"""
        item_type = item.get('type', '')
        
        if item_type == '조 본문':
            return self._process_article_text(
                item, article_no, parent_id, title, source_file, order_index
            )
        elif item_type == '호':
            return self._process_subclause(
                item, article_no, parent_id, title, source_file, order_index
            )
        
        return None
    
    def _process_article_text(
        self,
        item: Dict,
        article_no: int,
        parent_id: str,
        title: str,
        source_file: str,
        order_index: int
    ):
        """조 본문 처리 - 항 번호 파싱하여 개별 chunk로 분할"""
        import re
        
        item_text = item.get('text', '')
        
        # 항 번호 매핑
        clause_num_map = {
            '①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5,
            '⑥': 6, '⑦': 7, '⑧': 8, '⑨': 9, '⑩': 10,
            '⑪': 11, '⑫': 12, '⑬': 13, '⑭': 14, '⑮': 15,
            '⑯': 16, '⑰': 17, '⑱': 18, '⑲': 19, '⑳': 20
        }
        
        # 항 번호로 텍스트 분할 (①, ②, ③ 등)
        # 패턴: 원형 숫자로 시작하는 부분을 찾음
        clause_pattern = r'([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])'
        parts = re.split(clause_pattern, item_text)
        
        # 분할된 부분을 재조합하여 각 항 추출
        clauses = []
        current_clause_num = None
        current_clause_text = ""
        
        for part in parts:
            if part in clause_num_map:
                # 이전 항 저장
                if current_clause_num is not None:
                    clauses.append((current_clause_num, current_clause_text.strip()))
                # 새 항 시작
                current_clause_num = clause_num_map[part]
                current_clause_text = part
            else:
                current_clause_text += part
        
        # 마지막 항 저장
        if current_clause_num is not None:
            clauses.append((current_clause_num, current_clause_text.strip()))
        
        # 항이 없는 경우 (조 본문만 있는 경우)
        if not clauses:
            chunk_id = f"제{article_no}조 조본문"
            global_id = f"urn:user:{self.contract_type}:art:{article_no:03d}:att"
            unit_type = "articleText"
            
            text_raw = item_text
            text_norm = self._normalize_text(item_text, '조 본문')
            
            chunk = {
                "id": chunk_id,
                "global_id": global_id,
                "unit_type": unit_type,
                "parent_id": parent_id,
                "title": title,
                "order_index": order_index,
                "text_raw": text_raw,
                "text_norm": text_norm,
                "anchors": [],
                "source_file": source_file
            }
            
            return chunk
        
        # 여러 항이 있는 경우 - 각 항을 별도 chunk로 반환
        chunks = []
        for clause_num, clause_text in clauses:
            text_raw = clause_text
            text_norm = self._normalize_text(clause_text, '조 본문')
            
            # text_norm에 // 구분자가 있으면 세그먼트별로 청크 분할
            if '//' in text_norm:
                segments = [seg.strip() for seg in text_norm.split('//') if seg.strip()]
                
                # 각 세그먼트를 별도 청크로 생성
                for seg_idx, segment in enumerate(segments):
                    if seg_idx == 0:
                        # 첫 번째 세그먼트는 항 본문
                        chunk_id = f"제{article_no}조 제{clause_num}항"
                        global_id = f"urn:user:{self.contract_type}:art:{article_no:03d}:clause:{clause_num:03d}"
                    else:
                        # 나머지는 호 단위
                        chunk_id = f"제{article_no}조 제{clause_num}항 제{seg_idx}호"
                        global_id = f"urn:user:{self.contract_type}:art:{article_no:03d}:clause:{clause_num:03d}:sub:{seg_idx:03d}"
                    
                    chunk = {
                        "id": chunk_id,
                        "global_id": global_id,
                        "unit_type": "clause" if seg_idx == 0 else "subClause",
                        "parent_id": parent_id,
                        "title": title,
                        "order_index": order_index,
                        "text_raw": segment,  # 세그먼트 원문
                        "text_norm": segment,  # 세그먼트 정규화 (이미 정규화됨)
                        "anchors": [],
                        "source_file": source_file
                    }
                    chunks.append(chunk)
            else:
                # 세그먼트가 없으면 기존 방식
                chunk_id = f"제{article_no}조 제{clause_num}항"
                global_id = f"urn:user:{self.contract_type}:art:{article_no:03d}:clause:{clause_num:03d}"
                unit_type = "clause"
                
                chunk = {
                    "id": chunk_id,
                    "global_id": global_id,
                    "unit_type": unit_type,
                    "parent_id": parent_id,
                    "title": title,
                    "order_index": order_index,
                    "text_raw": text_raw,
                    "text_norm": text_norm,
                    "anchors": [],
                    "source_file": source_file
                }
                
                chunks.append(chunk)
        
        return chunks
    
    def _process_subclause(
        self,
        item: Dict,
        article_no: int,
        parent_id: str,
        title: str,
        source_file: str,
        order_index: int
    ):
        """호 처리 (조의 직접 하위항목)"""
        item_number = item.get('number', 0)
        item_text = item.get('text', '')
        
        chunk_id = f"제{article_no}조 제{item_number}호"
        global_id = f"urn:user:{self.contract_type}:art:{article_no:03d}:sub:{item_number:03d}"
        
        text_raw = item_text
        text_norm = self._normalize_text(item_text, '호')
        
        # 길이 체크 - 세그먼트 분할 필요한지
        if len(text_raw) > self.segment_threshold:
            # 세그먼트로 분할 (단순화: 호는 분할하지 않고 그대로)
            # 실제로는 더 복잡한 로직 필요
            pass
        
        chunk = {
            "id": chunk_id,
            "global_id": global_id,
            "unit_type": "subClause",
            "parent_id": parent_id,
            "title": title,
            "order_index": order_index,
            "text_raw": text_raw,
            "text_norm": text_norm,
            "anchors": [],
            "source_file": source_file
        }
        
        return chunk
    
    def _normalize_text(self, text: str, item_type: str) -> str:
        """
        텍스트 정규화 및 세그먼트 분할
        - 구체적 용어를 추상화하여 표준 계약서와 매칭률 향상
        - 하위 항목((가), (나) 등)을 // 구분자로 분리
        """
        import re
        
        normalized = text.strip()
        
        # 호 번호 제거
        if item_type == '호':
            normalized = re.sub(r'^\s*\d+\.\s*', '', normalized)
        
        # 하위 항목 분할
        # 1) 숫자 호: "1.", "2.", "3." 등
        # 2) 한글 호: "(가)", "(나)", "(다)" 등
        # 예: "1. 지급 불이행: ... 2. 무단 이용: ..." → ["1. 지급 불이행: ...", "2. 무단 이용: ..."]
        
        # 먼저 숫자 호로 분할 시도
        number_pattern = r'(\d+\.)'
        number_parts = re.split(number_pattern, normalized)
        
        # 숫자 호가 있으면 숫자 호로 분할
        if len(number_parts) > 1:
            segments = []
            current_segment = ""
            for part in number_parts:
                if re.match(number_pattern, part):  # 숫자 호 발견
                    if current_segment:  # 이전 세그먼트 저장
                        segments.append(current_segment.strip())
                    current_segment = part  # 새 세그먼트 시작
                else:
                    current_segment += part
            
            if current_segment:  # 마지막 세그먼트 저장
                segments.append(current_segment.strip())
        else:
            # 숫자 호가 없으면 한글 호로 분할 시도
            hangul_pattern = r'(\([가-힣]\))'
            hangul_parts = re.split(hangul_pattern, normalized)
            
            segments = []
            current_segment = ""
            for part in hangul_parts:
                if re.match(hangul_pattern, part):  # 한글 호 발견
                    if current_segment:  # 이전 세그먼트 저장
                        segments.append(current_segment.strip())
                    current_segment = part  # 새 세그먼트 시작
                else:
                    current_segment += part
            
            if current_segment:  # 마지막 세그먼트 저장
                segments.append(current_segment.strip())
        
        # 각 세그먼트 정규화
        normalized_segments = []
        for segment in segments:
            seg = segment
            
            # 원형 숫자 제거 (①, ②, ③ 등)
            seg = re.sub(r'[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]', '', seg)
            
            # 구체적 데이터 유형을 "데이터"로 추상화
            # 패턴을 더 유연하게 수정 (괄호, 별칭 등 포함)
            data_patterns = [
                (r'이동통신\s*서비스\s*이용\s*과정에서\s*발생하는\s*사용자\s*로그\s*데이터(?:\([^)]*\))?', '제공데이터'),
                (r'사용자\s*로그\s*데이터(?:\([^)]*\))?', '제공데이터'),
                (r'제공데이터(?:\([^)]*\))?', '제공데이터'),  # 이미 제공데이터로 명명된 경우 유지
                (r'이동통신\s*가입자의\s*서비스\s*이용\s*로그', '데이터'),
            ]
            for pattern, replacement in data_patterns:
                seg = re.sub(pattern, replacement, seg, flags=re.IGNORECASE)
            
            # AI/인공지능 모델을 "모델"로 추상화 (괄호 포함)
            seg = re.sub(r'인공지능\s*모델(?:\([^)]*\))?', 'AI모델', seg, flags=re.IGNORECASE)
            seg = re.sub(r'AI\s*모델(?:\([^)]*\))?', 'AI모델', seg, flags=re.IGNORECASE)
            
            # 구체적 당사자 명칭을 추상화
            seg = re.sub(r'갑이\s*을에게', '데이터제공자가 데이터이용자에게', seg)
            seg = re.sub(r'갑은\s*을에게', '데이터제공자는 데이터이용자에게', seg)
            seg = re.sub(r'을은', '데이터이용자는', seg)
            
            # 괄호 안의 별칭 제거 (이하 "XXX")
            seg = re.sub(r'\(이하\s*["\']?[^)]+["\']?\)', '', seg)
            
            # 특수 문장부호 제거 (콜론, 세미콜론 등)
            seg = re.sub(r'[:;]', '', seg)
            
            # 개행을 공백으로 변환
            seg = re.sub(r'\n+', ' ', seg)
            
            # 중복 공백 제거
            seg = re.sub(r'\s+', ' ', seg)
            
            normalized_segments.append(seg.strip())
        
        # 세그먼트를 // 구분자로 연결
        if len(normalized_segments) > 1:
            return '//'.join(normalized_segments)
        else:
            return normalized_segments[0] if normalized_segments else ""
