"""
항/호 단위 청킹 모듈
표준계약서의 조의 하위항목 중 최상위 항목을 기준으로 청킹
별지는 인덱스("1.", "2." 등)가 있으면 인덱스 단위로, 없으면 별지 전체 단위로 청킹
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional


class ClauseChunker:
    """
    항/호 단위 청커 (Clause-level Chunker)
    표준계약서의 structured.json 파일을 읽어서 조의 최상위 하위항목 단위로 청킹
    별지도 적절한 단위로 청킹
    """
    
    def __init__(self, segment_threshold: int = 1000, segment_size: int = 800):
        """
        초기화
        
        Args:
            segment_threshold: 세그먼트 분할을 트리거하는 최소 텍스트 길이 (기본값: 1000자)
            segment_size: 각 세그먼트의 목표 텍스트 길이 (기본값: 800자)
        """
        self.contract_type_map = {
            'provide': 'provide',
            'create': 'create',
            'process': 'process',
            'brokerage_provider': 'brokerage_provider',
            'brokerage_user': 'brokerage_user'
        }
        
        if segment_size >= segment_threshold:
            raise ValueError(f"segment_size({segment_size})는 segment_threshold({segment_threshold})보다 작아야 합니다")
        
        self.segment_threshold = segment_threshold
        self.segment_size = segment_size
        self.segment_counter = 0
    
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
                        result = self._process_top_level_item(
                            item,
                            article_no,
                            parent_id,
                            title,
                            contract_type,
                            source_file,
                            order_index
                        )
                        if result:
                            # 세그먼트 리스트인 경우
                            if isinstance(result, list):
                                for seg_chunk in result:
                                    seg_chunk['order_index'] = order_index
                                    chunks.append(seg_chunk)
                                    order_index += 1
                                order_index -= 1  # 마지막 증가 보정
                            else:
                                # 단일 청크인 경우
                                chunks.append(result)
        
        # 별지 처리
        if 'exhibits' in data and isinstance(data['exhibits'], list):
            for exhibit in data['exhibits']:
                exhibit_type = exhibit.get('type', '')
                
                if exhibit_type == '별지':
                    exhibit_chunks = self._process_exhibit(
                        exhibit,
                        contract_type,
                        source_file,
                        order_index
                    )
                    for chunk in exhibit_chunks:
                        order_index += 1
                        chunk['order_index'] = order_index
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
        항 처리 (세그먼트 분할 지원)
        
        Args:
            item: 항 딕셔너리
            article_no: 조 번호
            parent_id: 부모 ID
            title: 조 제목
            contract_type: 계약 유형
            source_file: 원본 파일명
            order_index: 문서 내 순서
            
        Returns:
            청크 딕셔너리 또는 세그먼트 청크 리스트
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
        
        # 세그먼트 분할 여부 확인
        if len(text_raw) > self.segment_threshold:
            # 세그먼트로 분할
            return self._split_clause_into_segments(
                item,
                article_no,
                item_number,
                parent_id,
                title,
                contract_type,
                source_file,
                order_index
            )
        
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
        
        elif item_type == '별지 본문':
            # "1. " 형태가 있으면 제거
            normalized = re.sub(r'^\s*\d+\.\s*', '', normalized)
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
        
        # data 처리 - 각 row를 항목으로 그룹화
        if 'data' in table and isinstance(table['data'], list):
            for idx, row in enumerate(table['data'], 1):
                if isinstance(row, dict):
                    # 항목 헤더
                    row_items_raw = [f"항목{idx}:"]
                    row_items_norm = []
                    
                    # 각 key-value 쌍을 마크다운 리스트 형식으로
                    for key, value in row.items():
                        # text_raw와 text_norm 모두 개행 제거
                        key_clean = str(key).replace('\n', ' ').strip()
                        value_str = str(value).replace('\n', ' ').strip()
                        
                        # 빈 값("")은 text_raw와 text_norm 모두 "..."로 표시
                        if value_str:
                            value_clean = value_str
                        else:
                            value_clean = "..."
                        
                        row_items_raw.append(f"- {key_clean}: {value_clean}")
                        row_items_norm.append(f"{key_clean}: {value_clean}")
                    
                    # row 내 항목들을 줄바꿈으로 연결
                    parts_raw.append('\n'.join(row_items_raw))
                    # text_norm은 기존처럼 각 row의 모든 key-value를 하나로
                    parts_norm.extend(row_items_norm)
        
        # notes 처리
        if 'notes' in table and table['notes']:
            # text_raw와 text_norm 모두 개행을 공백으로 변경
            notes_clean = table['notes'].replace('\n', ' ').strip()
            parts_raw.append(notes_clean)
            parts_norm.append(notes_clean)
        
        # text_raw: 항목별로 그룹화하여 줄바꿈으로 구분
        text_raw = '\n'.join(parts_raw)
        # text_norm: data의 각 요소와 notes를 //로 구분
        text_norm = '//'.join(parts_norm)
        
        return text_raw, text_norm
    
    def _process_exhibit(
        self,
        exhibit: Dict,
        contract_type: str,
        source_file: str,
        current_order_index: int
    ) -> List[Dict[str, Any]]:
        """
        별지(exhibit) 처리
        별지 본문에 "1.", "2." 등의 인덱스가 있으면 인덱스 단위로 청킹
        없으면 별지 전체를 하나의 청크로 처리
        
        Args:
            exhibit: 별지 딕셔너리
            contract_type: 계약 유형
            source_file: 원본 파일명
            current_order_index: 현재 order_index
            
        Returns:
            청크 리스트
        """
        exhibit_no = exhibit.get('number', 0)
        exhibit_title = exhibit.get('title', '')
        content_list = exhibit.get('content', [])
        
        # 별지 본문에서 인덱스가 있는지 확인
        indexed_positions = self._find_indexed_exhibit_texts(content_list)
        
        if not indexed_positions:
            # 인덱스가 없으면 별지 전체를 하나의 청크로
            chunk = self._create_whole_exhibit_chunk(
                exhibit_no,
                exhibit_title,
                content_list,
                contract_type,
                source_file,
                current_order_index
            )
            return [chunk]
        else:
            # 인덱스가 있으면 인덱스 단위로 청킹
            return self._create_indexed_exhibit_chunks(
                exhibit_no,
                exhibit_title,
                content_list,
                indexed_positions,
                contract_type,
                source_file,
                current_order_index
            )
    
    def _find_indexed_exhibit_texts(self, content_list: List[Dict]) -> List[Tuple[int, int]]:
        """
        별지 content에서 "1.", "2." 등의 인덱스로 시작하는 별지 본문의 위치 찾기
        
        Args:
            content_list: 별지의 content 리스트
            
        Returns:
            (인덱스 번호, content_list에서의 위치) 튜플 리스트
        """
        indexed_positions = []
        
        for idx, item in enumerate(content_list):
            if item.get('type') == '별지 본문':
                text = item.get('text', '').strip()
                # "1.", "2." 등으로 시작하는지 확인
                match = re.match(r'^\s*(\d+)\.\s+', text)
                if match:
                    index_num = int(match.group(1))
                    indexed_positions.append((index_num, idx))
        
        return indexed_positions
    
    def _create_whole_exhibit_chunk(
        self,
        exhibit_no: int,
        exhibit_title: str,
        content_list: List[Dict],
        contract_type: str,
        source_file: str,
        order_index: int
    ) -> Dict[str, Any]:
        """
        별지 전체를 하나의 청크로 생성
        
        Args:
            exhibit_no: 별지 번호
            exhibit_title: 별지 제목
            content_list: 별지의 content 리스트
            contract_type: 계약 유형
            source_file: 원본 파일명
            order_index: 문서 내 순서
            
        Returns:
            청크 딕셔너리
        """
        # ID 생성
        chunk_id = f"별지{exhibit_no}"
        global_id = f"urn:std:{contract_type}:ex:{exhibit_no:03d}"
        
        # title 추출
        title = self._extract_title_from_exhibit_title(exhibit_title)
        
        # breadcrumb 생성
        parent_id = f"별지{exhibit_no}"
        
        # text_raw와 text_norm 생성
        text_raw_parts = [exhibit_title]  # 제목은 text_raw에만
        text_norm_parts = []
        anchors = []
        
        # content 처리
        self._process_exhibit_content(
            content_list,
            text_raw_parts,
            text_norm_parts,
            anchors,
            parent_id
        )
        
        text_raw = '\n'.join(text_raw_parts)
        # text_norm: 개행 제거, 앞뒤 공백 제거, //로 연결
        text_norm_parts_cleaned = [part.replace('\n', ' ').strip() for part in text_norm_parts]
        text_norm = '//'.join(text_norm_parts_cleaned)
        
        # 청크 생성
        chunk = {
            "id": chunk_id,
            "global_id": global_id,
            "unit_type": "exhibit",
            "parent_id": parent_id,
            "title": title,
            "order_index": order_index,
            "text_raw": text_raw,
            "text_norm": text_norm,
            "anchors": anchors,
            "source_file": source_file
        }
        
        return chunk
    
    def _create_indexed_exhibit_chunks(
        self,
        exhibit_no: int,
        exhibit_title: str,
        content_list: List[Dict],
        indexed_positions: List[Tuple[int, int]],
        contract_type: str,
        source_file: str,
        current_order_index: int
    ) -> List[Dict[str, Any]]:
        """
        인덱스가 있는 별지를 인덱스 단위로 청킹
        
        Args:
            exhibit_no: 별지 번호
            exhibit_title: 별지 제목
            content_list: 별지의 content 리스트
            indexed_positions: 인덱스 위치 리스트
            contract_type: 계약 유형
            source_file: 원본 파일명
            current_order_index: 현재 order_index
            
        Returns:
            청크 리스트
        """
        chunks = []
        title = self._extract_title_from_exhibit_title(exhibit_title)
        parent_id = f"별지{exhibit_no}"
        
        # 각 인덱스 단위로 청킹
        for i, (index_num, start_pos) in enumerate(indexed_positions):
            # 다음 인덱스 위치 찾기
            if i + 1 < len(indexed_positions):
                end_pos = indexed_positions[i + 1][1]
            else:
                end_pos = len(content_list)
            
            # 해당 범위의 content 추출
            chunk_content = content_list[start_pos:end_pos]
            
            # ID 생성
            chunk_id = f"별지{exhibit_no}-{index_num}"
            global_id = f"urn:std:{contract_type}:ex:{exhibit_no:03d}:idx:{index_num:03d}"
            
            # text_raw와 text_norm 생성
            text_raw_parts = []
            text_norm_parts = []
            anchors = []
            
            # breadcrumb (예: "별지1-1")
            breadcrumb = f"{parent_id}-{index_num}"
            
            # content 처리
            self._process_exhibit_content(
                chunk_content,
                text_raw_parts,
                text_norm_parts,
                anchors,
                breadcrumb
            )
            
            text_raw = '\n'.join(text_raw_parts)
            # text_norm: 개행 제거, 앞뒤 공백 제거, //로 연결
            text_norm_parts_cleaned = [part.replace('\n', ' ').strip() for part in text_norm_parts]
            text_norm = '//'.join(text_norm_parts_cleaned)
            
            # 청크 생성
            chunk = {
                "id": chunk_id,
                "global_id": global_id,
                "unit_type": "exhibitIndexed",
                "parent_id": parent_id,
                "title": title,
                "order_index": current_order_index,  # 나중에 업데이트됨
                "text_raw": text_raw,
                "text_norm": text_norm,
                "anchors": anchors,
                "source_file": source_file
            }
            
            chunks.append(chunk)
        
        return chunks
    
    def _process_exhibit_content(
        self,
        content_list: List[Dict],
        text_raw_parts: List[str],
        text_norm_parts: List[str],
        anchors: List[Dict],
        parent_breadcrumb: str
    ):
        """
        별지 content 처리
        
        Args:
            content_list: content 리스트
            text_raw_parts: text_raw 파트 리스트 (참조로 수정)
            text_norm_parts: text_norm 파트 리스트 (참조로 수정)
            anchors: anchors 리스트 (참조로 수정)
            parent_breadcrumb: 부모 breadcrumb
        """
        for item in content_list:
            item_type = item.get('type', '')
            
            # offset 계산
            offset_raw = len('\n'.join(text_raw_parts))
            if text_raw_parts:
                offset_raw += 1
            
            # text_norm의 offset은 //로 연결되므로 계산 방법이 다름
            offset_norm = sum(len(part.replace('\n', ' ').strip()) for part in text_norm_parts)
            if text_norm_parts:
                offset_norm += len('//') * len(text_norm_parts)
            
            if item_type == '별지 본문':
                item_text = item.get('text', '')
                text_raw_parts.append(item_text)
                text_norm = self._normalize_text(item_text, '별지 본문')
                text_norm_parts.append(text_norm)
                
                anchors.append({
                    "unit_type": "exhibitText",
                    "offset_raw": offset_raw,
                    "offset_norm": offset_norm,
                    "breadcrumb": f"{parent_breadcrumb} 별지본문"
                })
            
            elif item_type == '표':
                table_text_raw, table_text_norm = self._process_table(item)
                text_raw_parts.append(table_text_raw)
                text_norm_parts.append(table_text_norm)
                
                anchors.append({
                    "unit_type": "table",
                    "offset_raw": offset_raw,
                    "offset_norm": offset_norm,
                    "breadcrumb": f"{parent_breadcrumb} 표"
                })
    
    def _extract_title_from_exhibit_title(self, title: str) -> str:
        """
        별지 title에서 실제 title 추출
        
        Args:
            title: 별지 title (예: [별지1] 대상데이터)
            
        Returns:
            title (예: 대상데이터)
        """
        # [별지n] title 형식에서 title 추출
        match = re.search(r'\[별지\d+\]\s*(.*)', title)
        if match:
            return match.group(1)
        return title
    
    def _split_clause_into_segments(
        self,
        item: Dict,
        article_no: int,
        item_number: int,
        parent_id: str,
        title: str,
        contract_type: str,
        source_file: str,
        order_index: int
    ) -> List[Dict[str, Any]]:
        """
        긴 항을 세그먼트로 분할
        
        Args:
            item: 항 딕셔너리
            article_no: 조 번호
            item_number: 항 번호
            parent_id: 부모 ID (제n조)
            title: 조 제목
            contract_type: 계약 유형
            source_file: 원본 파일명
            order_index: 문서 내 순서
            
        Returns:
            세그먼트 청크 리스트
        """
        item_text = item.get('text', '')
        clause_id = f"제{article_no}조 제{item_number}항"
        
        segments = []
        current_segment_parts = []
        current_segment_norm_parts = []
        current_segment_anchors = []
        current_length = 0
        
        # 항 본문 추가
        current_segment_parts.append(item_text)
        current_segment_norm_parts.append(self._normalize_text(item_text, '항'))
        current_length = len(item_text)
        
        # 하위 항목 처리
        if 'content' in item and isinstance(item['content'], list):
            for sub_item in item['content']:
                sub_type = sub_item.get('type', '')
                sub_text = sub_item.get('text', '')
                sub_number = sub_item.get('number', 0)
                
                # 호 단위로 그룹화
                if sub_type == '호':
                    # 호와 그 하위 목들을 하나의 단위로 처리
                    ho_parts = [sub_text]
                    ho_norm_parts = [self._normalize_text(sub_text, '호')]
                    ho_anchors = []
                    
                    # offset 계산
                    offset_raw = len('\n'.join(current_segment_parts))
                    if current_segment_parts:
                        offset_raw += 1
                    
                    offset_norm = sum(len(p.replace('\n', ' ').strip()) for p in current_segment_norm_parts)
                    if current_segment_norm_parts:
                        offset_norm += len('//') * len(current_segment_norm_parts)
                    
                    breadcrumb = f"{clause_id} 제{sub_number}호"
                    ho_anchors.append({
                        "unit_type": "subClause",
                        "offset_raw": offset_raw,
                        "offset_norm": offset_norm,
                        "breadcrumb": breadcrumb
                    })
                    
                    # 하위 목 처리
                    if 'content' in sub_item and isinstance(sub_item['content'], list):
                        self._process_sub_items(
                            sub_item['content'],
                            ho_parts,
                            ho_norm_parts,
                            ho_anchors,
                            breadcrumb
                        )
                    
                    ho_text = '\n'.join(ho_parts)
                    ho_length = len(ho_text)
                    
                    # 현재 세그먼트에 추가 가능한지 확인
                    if current_length + ho_length > self.segment_size and current_segment_parts:
                        # 현재 세그먼트 저장
                        segments.append(self._create_segment_chunk(
                            article_no,
                            item_number,
                            len(segments) + 1,
                            clause_id,
                            parent_id,
                            title,
                            contract_type,
                            source_file,
                            order_index,
                            current_segment_parts,
                            current_segment_norm_parts,
                            current_segment_anchors
                        ))
                        
                        # 새 세그먼트 시작
                        current_segment_parts = ho_parts
                        current_segment_norm_parts = ho_norm_parts
                        current_segment_anchors = ho_anchors
                        current_length = ho_length
                    else:
                        # 현재 세그먼트에 추가
                        current_segment_parts.extend(ho_parts)
                        current_segment_norm_parts.extend(ho_norm_parts)
                        current_segment_anchors.extend(ho_anchors)
                        current_length += ho_length
                
                elif sub_type == '항 본문':
                    # 항 본문은 첫 세그먼트에 포함 (이미 처리됨)
                    pass
                
                elif sub_type == '표':
                    table_text_raw, table_text_norm = self._process_table(sub_item)
                    table_length = len(table_text_raw)
                    
                    # offset 계산
                    offset_raw = len('\n'.join(current_segment_parts))
                    if current_segment_parts:
                        offset_raw += 1
                    
                    offset_norm = sum(len(p.replace('\n', ' ').strip()) for p in current_segment_norm_parts)
                    if current_segment_norm_parts:
                        offset_norm += len('//') * len(current_segment_norm_parts)
                    
                    table_anchor = {
                        "unit_type": "table",
                        "offset_raw": offset_raw,
                        "offset_norm": offset_norm,
                        "breadcrumb": f"{clause_id} 표"
                    }
                    
                    # 현재 세그먼트에 추가 가능한지 확인
                    if current_length + table_length > self.segment_size and current_segment_parts:
                        # 현재 세그먼트 저장
                        segments.append(self._create_segment_chunk(
                            article_no,
                            item_number,
                            len(segments) + 1,
                            clause_id,
                            parent_id,
                            title,
                            contract_type,
                            source_file,
                            order_index,
                            current_segment_parts,
                            current_segment_norm_parts,
                            current_segment_anchors
                        ))
                        
                        # 새 세그먼트 시작
                        current_segment_parts = [table_text_raw]
                        current_segment_norm_parts = [table_text_norm]
                        current_segment_anchors = [table_anchor]
                        current_length = table_length
                    else:
                        # 현재 세그먼트에 추가
                        current_segment_parts.append(table_text_raw)
                        current_segment_norm_parts.append(table_text_norm)
                        current_segment_anchors.append(table_anchor)
                        current_length += table_length
        
        # 마지막 세그먼트 저장
        if current_segment_parts:
            segments.append(self._create_segment_chunk(
                article_no,
                item_number,
                len(segments) + 1,
                clause_id,
                parent_id,
                title,
                contract_type,
                source_file,
                order_index,
                current_segment_parts,
                current_segment_norm_parts,
                current_segment_anchors
            ))
        
        return segments
    
    def _create_segment_chunk(
        self,
        article_no: int,
        clause_no: int,
        segment_no: int,
        clause_id: str,
        parent_article_id: str,
        title: str,
        contract_type: str,
        source_file: str,
        order_index: int,
        text_raw_parts: List[str],
        text_norm_parts: List[str],
        anchors: List[Dict]
    ) -> Dict[str, Any]:
        """
        세그먼트 청크 생성
        
        Args:
            article_no: 조 번호
            clause_no: 항 번호
            segment_no: 세그먼트 번호
            clause_id: 원본 항 ID
            parent_article_id: 부모 조 ID
            title: 조 제목
            contract_type: 계약 유형
            source_file: 원본 파일명
            order_index: 문서 내 순서
            text_raw_parts: text_raw 파트 리스트
            text_norm_parts: text_norm 파트 리스트
            anchors: anchors 리스트
            
        Returns:
            세그먼트 청크 딕셔너리
        """
        self.segment_counter += 1
        
        # ID 생성
        chunk_id = f"{clause_id}_SEG_{segment_no:03d}"
        global_id = f"urn:std:{contract_type}:art:{article_no:03d}:cla:{clause_no:03d}:seg:{segment_no:03d}"
        
        # text 생성
        text_raw = '\n'.join(text_raw_parts)
        text_norm_parts_cleaned = [part.replace('\n', ' ').strip() for part in text_norm_parts]
        text_norm = '//'.join(text_norm_parts_cleaned)
        
        # 청크 생성
        chunk = {
            "id": chunk_id,
            "global_id": global_id,
            "unit_type": "segment",
            "parent_id": clause_id,
            "parent_article_id": parent_article_id,
            "title": title,
            "order_index": order_index,
            "text_raw": text_raw,
            "text_norm": text_norm,
            "anchors": anchors,
            "source_file": source_file
        }
        
        return chunk
    
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
