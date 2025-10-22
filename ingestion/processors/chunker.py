"""
항/호 단위 청킹 모듈
표준계약서의 조의 하위항목 중 최상위 항목을 기준으로 청킹
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple


class ClauseChunker:
    """
    항/호 단위 청커 (Clause-level Chunker)
    표준계약서의 structured.json 파일을 읽어서 조의 최상위 하위항목 단위로 청킹
    """
    
    def __init__(self):
        """초기화"""
        self.contract_type_map = {
            'provide': 'provide',
            'create': 'create',
            'process': 'process',
            'brokerage_provider': 'brokerage_provider',
            'brokerage_user': 'brokerage_user'
        }
    
    def chunk_file(self, input_path: Path) -> List[Dict[str, Any]]:
        """
        structured.json 파일을 청킹
        
        Args:
            input_path: 입력 structured.json 파일 경로
            
        Returns:
            청크 리스트
        """
        # 파일 읽기
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'articles' not in data:
            raise ValueError("'articles' 키가 없습니다")
        
        # 파일명에서 계약 유형 추출
        contract_type = self._extract_contract_type(input_path.name)
        source_file = input_path.name
        
        # 청킹
        chunks = []
        order_index = 0
        
        # 조 처리
        for article in data['articles']:
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
                        chunk = self._process_top_level_item(
                            item,
                            article_no,
                            parent_id,
                            title,
                            contract_type,
                            source_file,
                            order_index
                        )
                        if chunk:
                            chunks.append(chunk)
        
        return chunks
    
    def _extract_contract_type(self, filename: str) -> str:
        """
        파일명에서 계약 유형 추출
        
        Args:
            filename: 파일명 (예: provide_std_contract_structured.json)
            
        Returns:
            계약 유형 (예: provide)
        """
        for key in self.contract_type_map.keys():
            if filename.startswith(key):
                return self.contract_type_map[key]
        
        raise ValueError(f"파일명에서 계약 유형을 추출할 수 없습니다: {filename}")
    
    def _extract_title_from_article_text(self, text: str) -> str:
        """
        조 text에서 title 추출
        
        Args:
            text: 조 text (예: 제1조(목적))
            
        Returns:
            title (예: 목적)
        """
        # 제n조(title) 형식에서 title 추출
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
        contract_type: str,
        source_file: str,
        order_index: int
    ) -> Dict[str, Any]:
        """
        조의 최상위 하위항목 처리
        
        Args:
            item: 항목 딕셔너리
            article_no: 조 번호
            parent_id: 부모 ID (제n조)
            title: 조 제목
            contract_type: 계약 유형
            source_file: 원본 파일명
            order_index: 문서 내 순서
            
        Returns:
            청크 딕셔너리 또는 None
        """
        item_type = item.get('type', '')
        
        if item_type == '조 본문':
            return self._process_article_text(
                item, article_no, parent_id, title, contract_type, source_file, order_index
            )
        elif item_type == '항':
            return self._process_clause(
                item, article_no, parent_id, title, contract_type, source_file, order_index
            )
        elif item_type == '호':
            return self._process_subclause(
                item, article_no, parent_id, title, contract_type, source_file, order_index
            )
        
        return None
    
    def _process_article_text(
        self,
        item: Dict,
        article_no: int,
        parent_id: str,
        title: str,
        contract_type: str,
        source_file: str,
        order_index: int
    ) -> Dict[str, Any]:
        """
        조 본문 처리
        
        Args:
            item: 조 본문 딕셔너리
            article_no: 조 번호
            parent_id: 부모 ID
            title: 조 제목
            contract_type: 계약 유형
            source_file: 원본 파일명
            order_index: 문서 내 순서
            
        Returns:
            청크 딕셔너리
        """
        item_text = item.get('text', '')
        
        # ID 생성
        chunk_id = f"제{article_no}조 조본문"
        global_id = f"urn:std:{contract_type}:art:{article_no:03d}:att"
        
        # text_raw와 text_norm 생성
        text_raw = item_text
        text_norm = self._normalize_text(item_text, '조 본문')
        
        # 청크 생성
        chunk = {
            "id": chunk_id,
            "global_id": global_id,
            "unit_type": "articleText",
            "parent_id": parent_id,
            "title": title,
            "order_index": order_index,
            "text_raw": text_raw,
            "text_norm": text_norm,
            "anchors": [],
            "source_file": source_file
        }
        
        return chunk
    
    def _process_clause(
        self,
        item: Dict,
        article_no: int,
        parent_id: str,
        title: str,
        contract_type: str,
        source_file: str,
        order_index: int
    ) -> Dict[str, Any]:
        """
        항 처리
        
        Args:
            item: 항 딕셔너리
            article_no: 조 번호
            parent_id: 부모 ID
            title: 조 제목
            contract_type: 계약 유형
            source_file: 원본 파일명
            order_index: 문서 내 순서
            
        Returns:
            청크 딕셔너리
        """
        item_number = item.get('number', 0)
        item_text = item.get('text', '')
        
        # ID 생성
        chunk_id = f"제{article_no}조 제{item_number}항"
        global_id = f"urn:std:{contract_type}:art:{article_no:03d}:cla:{item_number:03d}"
        
        # text_raw와 text_norm 생성
        text_raw_parts = [item_text]
        text_norm_parts = [self._normalize_text(item_text, '항')]
        anchors = []
        
        # 하위 항목 처리
        if 'content' in item and isinstance(item['content'], list):
            self._process_sub_items(
                item['content'],
                text_raw_parts,
                text_norm_parts,
                anchors,
                f"제{article_no}조 제{item_number}항"
            )
        
        text_raw = '\n'.join(text_raw_parts)
        # text_norm: 개행 제거, 앞뒤 공백 제거, //로 연결
        text_norm_parts_cleaned = [part.replace('\n', ' ').strip() for part in text_norm_parts]
        text_norm = '//'.join(text_norm_parts_cleaned)
        
        # 청크 생성
        chunk = {
            "id": chunk_id,
            "global_id": global_id,
            "unit_type": "clause",
            "parent_id": parent_id,
            "title": title,
            "order_index": order_index,
            "text_raw": text_raw,
            "text_norm": text_norm,
            "anchors": anchors,
            "source_file": source_file
        }
        
        return chunk
    
    def _process_subclause(
        self,
        item: Dict,
        article_no: int,
        parent_id: str,
        title: str,
        contract_type: str,
        source_file: str,
        order_index: int
    ) -> Dict[str, Any]:
        """
        호 처리 (조의 직접 하위항목인 경우)
        
        Args:
            item: 호 딕셔너리
            article_no: 조 번호
            parent_id: 부모 ID
            title: 조 제목
            contract_type: 계약 유형
            source_file: 원본 파일명
            order_index: 문서 내 순서
            
        Returns:
            청크 딕셔너리
        """
        item_number = item.get('number', 0)
        item_text = item.get('text', '')
        
        # ID 생성
        chunk_id = f"제{article_no}조 제{item_number}호"
        global_id = f"urn:std:{contract_type}:art:{article_no:03d}:sub:{item_number:03d}"
        
        # text_raw와 text_norm 생성
        text_raw_parts = [item_text]
        text_norm_parts = [self._normalize_text(item_text, '호')]
        anchors = []
        
        # 하위 항목 처리
        if 'content' in item and isinstance(item['content'], list):
            self._process_sub_items(
                item['content'],
                text_raw_parts,
                text_norm_parts,
                anchors,
                f"제{article_no}조 제{item_number}호"
            )
        
        text_raw = '\n'.join(text_raw_parts)
        # text_norm: 개행 제거, 앞뒤 공백 제거, //로 연결
        text_norm_parts_cleaned = [part.replace('\n', ' ').strip() for part in text_norm_parts]
        text_norm = '//'.join(text_norm_parts_cleaned)
        
        # 청크 생성
        chunk = {
            "id": chunk_id,
            "global_id": global_id,
            "unit_type": "subClause",
            "parent_id": parent_id,
            "title": title,
            "order_index": order_index,
            "text_raw": text_raw,
            "text_norm": text_norm,
            "anchors": anchors,
            "source_file": source_file
        }
        
        return chunk
    
    def _process_sub_items(
        self,
        content_list: List[Dict],
        text_raw_parts: List[str],
        text_norm_parts: List[str],
        anchors: List[Dict],
        parent_breadcrumb: str
    ):
        """
        하위 항목들을 재귀적으로 처리
        
        Args:
            content_list: content 리스트
            text_raw_parts: text_raw 파트 리스트 (참조로 수정)
            text_norm_parts: text_norm 파트 리스트 (참조로 수정)
            anchors: anchors 리스트 (참조로 수정)
            parent_breadcrumb: 부모 breadcrumb
        """
        for item in content_list:
            item_type = item.get('type', '')
            item_text = item.get('text', '')
            item_number = item.get('number', 0)
            
            # offset 계산
            offset_raw = len('\n'.join(text_raw_parts))
            if text_raw_parts:
                offset_raw += 1
            
            # text_norm의 offset은 //로 연결되므로 계산 방법이 다름
            offset_norm = sum(len(part.replace('\n', ' ').strip()) for part in text_norm_parts)
            if text_norm_parts:
                offset_norm += len('//') * len(text_norm_parts)
            
            if item_type == '항 본문':
                text_raw_parts.append(item_text)
                text_norm_parts.append(self._normalize_text(item_text, '항 본문'))
                
                anchors.append({
                    "unit_type": "clauseText",
                    "offset_raw": offset_raw,
                    "offset_norm": offset_norm,
                    "breadcrumb": f"{parent_breadcrumb} 항본문"
                })
            
            elif item_type == '호':
                breadcrumb = f"{parent_breadcrumb} 제{item_number}호"
                text_raw_parts.append(item_text)
                text_norm_parts.append(self._normalize_text(item_text, '호'))
                
                anchors.append({
                    "unit_type": "subClause",
                    "offset_raw": offset_raw,
                    "offset_norm": offset_norm,
                    "breadcrumb": breadcrumb
                })
                
                # 하위 content 처리
                if 'content' in item and isinstance(item['content'], list):
                    self._process_sub_items(
                        item['content'],
                        text_raw_parts,
                        text_norm_parts,
                        anchors,
                        breadcrumb
                    )
            
            elif item_type == '목':
                breadcrumb = f"{parent_breadcrumb} 제{item_number}목"
                text_raw_parts.append(item_text)
                text_norm_parts.append(self._normalize_text(item_text, '목'))
                
                anchors.append({
                    "unit_type": "subSubClause",
                    "offset_raw": offset_raw,
                    "offset_norm": offset_norm,
                    "breadcrumb": breadcrumb
                })
                
                # 하위 content 처리
                if 'content' in item and isinstance(item['content'], list):
                    self._process_sub_items(
                        item['content'],
                        text_raw_parts,
                        text_norm_parts,
                        anchors,
                        breadcrumb
                    )
            
            elif item_type == '표':
                breadcrumb = f"{parent_breadcrumb} 표"
                table_text_raw, table_text_norm = self._process_table(item)
                text_raw_parts.append(table_text_raw)
                text_norm_parts.append(table_text_norm)
                
                anchors.append({
                    "unit_type": "table",
                    "offset_raw": offset_raw,
                    "offset_norm": offset_norm,
                    "breadcrumb": breadcrumb
                })
    
    def _normalize_text(self, text: str, item_type: str) -> str:
        """
        텍스트 정규화 (인덱스 제거)
        
        Args:
            text: 원본 텍스트
            item_type: 항목 유형
            
        Returns:
            정규화된 텍스트
        """
        # 공백 제거 후 처리
        normalized = text.strip()
        
        if item_type == '조 본문':
            # 조 본문은 그대로 반환
            return normalized
        
        elif item_type == '항':
            # "  ① " 형태 제거
            normalized = re.sub(r'^\s*[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]\s*', '', normalized)
            return normalized
        
        elif item_type == '항 본문':
            # 항 본문은 그대로 반환
            return normalized
        
        elif item_type == '호':
            # "  1. " 형태 제거
            normalized = re.sub(r'^\s*\d+\.\s*', '', normalized)
            return normalized
        
        elif item_type == '목':
            # "  가. " 형태 제거
            normalized = re.sub(r'^\s*[가-힣]\.\s*', '', normalized)
            return normalized
        
        return normalized
    
    def _process_table(self, table: Dict) -> Tuple[str, str]:
        """
        표 처리
        
        Args:
            table: 표 딕셔너리
            
        Returns:
            (text_raw, text_norm) 튜플
        """
        parts_raw = []
        parts_norm = []
        
        # data 처리
        if 'data' in table and isinstance(table['data'], list):
            for row in table['data']:
                if isinstance(row, dict):
                    for key, value in row.items():
                        if value:  # 빈 값이 아닌 경우만
                            parts_raw.append(f"{key}: {value}")
                            # text_norm에서는 개행 제거
                            value_norm = str(value).replace('\n', ' ').strip()
                            parts_norm.append(f"{key}: {value_norm}")
        
        # notes 처리
        if 'notes' in table and table['notes']:
            parts_raw.append(table['notes'])
            # text_norm에서는 개행 제거
            notes_norm = table['notes'].replace('\n', ' ').strip()
            parts_norm.append(notes_norm)
        
        text_raw = '\n'.join(parts_raw)
        # text_norm: data의 각 요소와 notes를 //로 구분
        text_norm = '//'.join(parts_norm)
        
        return text_raw, text_norm
    
    def save_chunks(self, chunks: List[Dict[str, Any]], output_path: Path):
        """
        청크를 JSON 파일로 저장
        
        Args:
            chunks: 청크 리스트
            output_path: 출력 파일 경로
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
