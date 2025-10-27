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
                            # 세그먼트 리스트인 경우
                            if isinstance(result, list):
                                for seg_chunk in result:
                                    seg_chunk['order_index'] = order_index
                                    chunks.append(seg_chunk)
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
    ) -> Dict[str, Any]:
        """조 본문 처리 - 항 번호 파싱하여 개별 ID 부여"""
        import re
        
        item_text = item.get('text', '')
        
        # 항 번호 추출 (①, ②, ③ 또는 1., 2., 3. 형식)
        clause_match = re.match(r'^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]', item_text.strip())
        if not clause_match:
            # 숫자 형식 시도
            clause_match = re.match(r'^(\d+)\.', item_text.strip())
        
        if clause_match:
            # 항 번호가 있는 경우
            clause_symbol = clause_match.group(0)
            # 원형 숫자를 일반 숫자로 변환
            clause_num_map = {
                '①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5,
                '⑥': 6, '⑦': 7, '⑧': 8, '⑨': 9, '⑩': 10,
                '⑪': 11, '⑫': 12, '⑬': 13, '⑭': 14, '⑮': 15,
                '⑯': 16, '⑰': 17, '⑱': 18, '⑲': 19, '⑳': 20
            }
            
            if clause_symbol in clause_num_map:
                clause_num = clause_num_map[clause_symbol]
            else:
                # 숫자 형식인 경우
                clause_num = int(clause_match.group(1))
            
            chunk_id = f"제{article_no}조 제{clause_num}항"
            global_id = f"urn:user:{self.contract_type}:art:{article_no:03d}:clause:{clause_num:03d}"
            unit_type = "clause"
        else:
            # 항 번호가 없는 경우 (조 본문)
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
        
        # 하위 항목 분할 ((가), (나), (다) 등)
        # 예: "(가) 접근 통제: ... (나) 데이터 암호화: ..." → ["(가) 접근 통제: ...", "(나) 데이터 암호화: ..."]
        sub_items = re.split(r'(\([가-힣]\))', normalized)
        
        # 분할된 항목을 재조합 (구분자 포함)
        segments = []
        current_segment = ""
        for i, part in enumerate(sub_items):
            if re.match(r'\([가-힣]\)', part):  # 구분자 발견
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
