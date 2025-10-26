"""
Data Loader for Contract Clause Verification System

이 모듈은 계약서 데이터를 로드하고 파싱하는 기능을 제공합니다.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

try:
    from backend.clause_verification.node_1_clause_matching.models import ClauseData
    from backend.clause_verification.node_1_clause_matching.config import config
except ImportError:
    from models import ClauseData
    from config import config

# 로깅 설정
logger = logging.getLogger(__name__)


class ContractDataLoader:
    """
    계약서 데이터를 로드하고 파싱하는 클래스
    
    표준 계약서(JSONL 형식)와 사용자 계약서(평문 텍스트)를 로드하여
    ClauseData 모델로 변환합니다.
    """
    
    def __init__(self):
        """데이터 로더 초기화"""
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def load_standard_contract(self, file_path: Optional[Path] = None) -> List[ClauseData]:
        """
        표준 계약서를 JSONL 파일에서 로드 (저장된 임베딩 자동 로드)
        
        Args:
            file_path: JSONL 파일 경로 (기본값: config.STANDARD_CONTRACT_PATH)
        
        Returns:
            ClauseData 객체 리스트 (임베딩 포함)
        
        Raises:
            FileNotFoundError: 파일이 존재하지 않는 경우
            JSONDecodeError: JSON 파싱 오류가 발생한 경우
        """
        if file_path is None:
            file_path = config.STANDARD_CONTRACT_PATH
        
        if not file_path.exists():
            raise FileNotFoundError(f"표준 계약서 파일을 찾을 수 없습니다: {file_path}")
        
        self.logger.info(f"표준 계약서 로드 중: {file_path}")
        
        # 저장된 임베딩 파일 경로
        embeddings_dir = file_path.parent.parent / "embeddings"
        embeddings_file = embeddings_dir / f"{file_path.stem}_embeddings.npy"
        metadata_file = embeddings_dir / f"{file_path.stem}_metadata.json"
        
        clauses = []
        
        try:
            # 여러 인코딩 시도
            encodings = ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']
            file_content = None
            used_encoding = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        file_content = f.read()
                    used_encoding = encoding
                    self.logger.info(f"파일 인코딩 감지 성공: {encoding}")
                    break
                except UnicodeDecodeError:
                    self.logger.debug(f"인코딩 {encoding} 실패, 다음 시도...")
                    continue
            
            if file_content is None:
                raise UnicodeDecodeError(
                    'unknown', b'', 0, 1,
                    f"파일을 읽을 수 없습니다. 시도한 인코딩: {', '.join(encodings)}"
                )
            
            # JSON 배열 형식으로 로드
            if file_path.suffix == '.json':
                data_list = json.loads(file_content)
                for item in data_list:
                    try:
                        clause = self._parse_clause_from_dict(item)
                        clauses.append(clause)
                    except ValueError as e:
                        self.logger.warning(f"데이터 검증 오류 (ID: {item.get('id', 'unknown')}): {e}")
                        continue
            # JSONL 형식으로 로드
            else:
                line_number = 0
                for line in file_content.split('\n'):
                    line_number += 1
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        clause = self._parse_clause_from_dict(data)
                        clauses.append(clause)
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"라인 {line_number}에서 JSON 파싱 오류 (건너뜀): {e}")
                        continue
                    except ValueError as e:
                        self.logger.warning(f"라인 {line_number}에서 데이터 검증 오류: {e}")
                        continue
        
        except Exception as e:
            self.logger.error(f"파일 읽기 오류: {e}")
            raise
        
        self.logger.info(f"총 {len(clauses)}개의 조문을 로드했습니다")
        
        # 저장된 임베딩 로드 시도
        if embeddings_file.exists() and metadata_file.exists():
            try:
                import numpy as np
                
                self.logger.info(f"저장된 임베딩 로드 중: {embeddings_file}")
                embeddings = np.load(embeddings_file)
                
                # 메타데이터 검증 (여러 인코딩 시도)
                metadata = None
                for encoding in ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']:
                    try:
                        with open(metadata_file, 'r', encoding=encoding) as f:
                            metadata = json.load(f)
                        self.logger.debug(f"메타데이터 인코딩: {encoding}")
                        break
                    except UnicodeDecodeError:
                        continue
                
                if metadata is None:
                    raise UnicodeDecodeError('unknown', b'', 0, 1, "메타데이터 파일을 읽을 수 없습니다")
                
                if len(clauses) == len(embeddings) == len(metadata['clause_ids']):
                    # 순서대로 임베딩 할당
                    for i, clause in enumerate(clauses):
                        clause.embedding = embeddings[i]
                    self.logger.info(f"✅ 저장된 임베딩 로드 완료 ({len(embeddings)}개)")
                else:
                    self.logger.warning(f"임베딩 개수 불일치 (조문: {len(clauses)}, 임베딩: {len(embeddings)})")
            except Exception as e:
                self.logger.warning(f"임베딩 로드 실패 (나중에 생성됨): {e}")
        else:
            self.logger.info("저장된 임베딩 없음 (나중에 생성됨)")
        
        return clauses
    
    def load_user_contract_chunked(self, text: str) -> List[ClauseData]:
        """
        사용자 계약서를 문단 단위로 청킹하여 로드
        
        각 조문 내의 항(①②③④⑤) 단위로 분리하여 더 세밀한 매칭 가능
        
        Args:
            text: 사용자 계약서 평문 텍스트
        
        Returns:
            ClauseData 객체 리스트 (문단 단위로 분리됨)
        """
        import re
        
        if not text or not text.strip():
            raise ValueError("입력 텍스트가 비어있습니다")
        
        self.logger.info("사용자 계약서 문단 단위 청킹 중")
        
        # 먼저 조 단위로 분리
        clause_patterns = [
            re.compile(r'제(\d{1,2})조\s*\([^)]+\)'),  # 제1조(목적)
            re.compile(r'제(\d{1,2})조\s+\([^)]+\)'),  # 제1조 (목적)  
            re.compile(r'제(\d{1,2})조\s+[^\n\r]+'),   # 제1조 목적
            re.compile(r'제(\d{1,2})조'),              # 제1조 (단독)
        ]
        
        # 모든 제N조 패턴의 위치 찾기
        matches = []
        for pattern in clause_patterns:
            matches = list(pattern.finditer(text))
            if matches:
                break
        
        if not matches:
            # 제N조 패턴이 없으면 전체를 하나의 조문으로 처리
            return [ClauseData(
                id="user-1",
                title="사용자 조문 1",
                subtitle=None,
                type="조",
                text=text.strip()
            )]
        
        chunks = []
        chunk_id = 1
        
        for idx, match in enumerate(matches, start=1):
            title = match.group(0)
            start_pos = match.end()
            
            # 다음 조문의 시작 위치 찾기
            if idx < len(matches):
                end_pos = matches[idx].start()
            else:
                end_pos = len(text)
            
            # 내용 추출
            content = text[start_pos:end_pos].strip()
            
            if not content:
                continue
            
            # 항 번호로 분리 (①②③④⑤⑥⑦⑧⑨⑩ 또는 ① ② ③ 형식)
            paragraph_pattern = re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩]\s*')
            paragraph_matches = list(paragraph_pattern.finditer(content))
            
            if paragraph_matches:
                # 항이 있는 경우 - 각 항을 별도 청크로 분리
                for p_idx, p_match in enumerate(paragraph_matches):
                    p_start = p_match.start()
                    
                    # 다음 항의 시작 위치 찾기
                    if p_idx < len(paragraph_matches) - 1:
                        p_end = paragraph_matches[p_idx + 1].start()
                    else:
                        p_end = len(content)
                    
                    # 항 내용 추출
                    paragraph_content = content[p_start:p_end].strip()
                    
                    if paragraph_content:
                        # 항 번호 추출
                        paragraph_num = p_match.group(0)
                        
                        # 호 번호로 추가 분리: 
                        # 1) 한글: (가), (나), (다) 등
                        # 2) 숫자: 1., 2., 3. 또는 1) 2) 3) 형식
                        ho_pattern = re.compile(r'(?:\([가-힣]\)|\d+\.\s+|\d+\)\s+)')
                        ho_matches = list(ho_pattern.finditer(paragraph_content))
                        
                        if ho_matches:
                            # 호가 있는 경우 - 세그먼트 기법 적용
                            # 항 도입부 추출 (첫 번째 호 이전)
                            intro_text = paragraph_content[:ho_matches[0].start()].strip()
                            
                            # 각 호 내용 추출
                            ho_segments = []
                            for h_idx, h_match in enumerate(ho_matches):
                                h_start = h_match.start()
                                
                                # 다음 호의 시작 위치 찾기
                                if h_idx < len(ho_matches) - 1:
                                    h_end = ho_matches[h_idx + 1].start()
                                else:
                                    h_end = len(paragraph_content)
                                
                                # 호 내용 추출 (호 번호 제거)
                                ho_content = paragraph_content[h_start:h_end].strip()
                                # 호 번호 제거 (1. 또는 1) 또는 (가) 형식)
                                ho_content_clean = re.sub(r'^(?:\([가-힣]\)|\d+\.\s*|\d+\)\s*)', '', ho_content).strip()
                                if ho_content_clean:
                                    ho_segments.append(ho_content_clean)
                            
                            # 세그먼트 기법: 도입부 + // + 각 호
                            if intro_text and ho_segments:
                                text_norm_segmented = intro_text + "//" + "//".join(ho_segments)
                            elif ho_segments:
                                text_norm_segmented = "//".join(ho_segments)
                            else:
                                text_norm_segmented = self._normalize_text(paragraph_content)
                            
                            chunk = ClauseData(
                                id=f"user-{chunk_id}",
                                title=f"{title} {paragraph_num}",
                                subtitle=None,
                                type="항",
                                text=paragraph_content,
                                text_norm=text_norm_segmented
                            )
                            chunks.append(chunk)
                            chunk_id += 1
                        else:
                            # 호가 없는 경우 - 항 전체를 하나의 청크로
                            chunk = ClauseData(
                                id=f"user-{chunk_id}",
                                title=f"{title} {paragraph_num}",
                                subtitle=None,
                                type="항",
                                text=paragraph_content,
                                text_norm=self._normalize_text(paragraph_content)
                            )
                            chunks.append(chunk)
                            chunk_id += 1
            else:
                # 항이 없는 경우 - 전체를 하나의 청크로
                chunk = ClauseData(
                    id=f"user-{chunk_id}",
                    title=title,
                    subtitle=None,
                    type="조",
                    text=content,
                    text_norm=self._normalize_text(content)
                )
                chunks.append(chunk)
                chunk_id += 1
        
        self.logger.info(f"총 {len(chunks)}개의 청크를 생성했습니다")
        return chunks
    
    def _normalize_text(self, text: str) -> str:
        """
        텍스트 정규화 (임베딩용) - 보수적 접근
        
        최소한의 정규화만 수행하여 의미 있는 내용을 보존합니다.
        
        제거 대상:
        - 개행 문자 (\n, \r)
        - 플레이스홀더 (○○○, □□□)
        - 과도한 공백
        
        유지 대상:
        - 실제 내용과 핵심 키워드
        - 법령 인용 (「」)
        - 인용부호 ("")
        - 조문 번호 (의미 구분에 중요)
        - 번호 매기기 (내용 구조 파악에 중요)
        """
        import re
        
        # 1. 개행 문자를 공백으로 변환
        text = text.replace('\n', ' ').replace('\r', ' ')
        
        # 2. 플레이스홀더만 제거 (실제 내용은 보존)
        text = text.replace('○○○', '[데이터제공자]')  # 의미 있는 플레이스홀더로 변환
        text = text.replace('□□□', '[데이터이용자]')
        text = text.replace('○○', '[항목]')
        text = text.replace('□□', '[항목]')
        
        # 3. 빈 괄호나 밑줄만 제거
        text = re.sub(r'_+', '', text)  # 밑줄 제거
        text = re.sub(r'\[\s*\]', '', text)  # 빈 대괄호 제거
        
        # 4. 여러 공백을 하나로
        text = re.sub(r'\s+', ' ', text)
        
        # 5. 앞뒤 공백 제거
        text = text.strip()
        
        return text
    
    def load_user_contract_from_text(self, text: str) -> List[ClauseData]:
        """
        사용자가 입력한 평문 텍스트를 파싱하여 ClauseData 리스트로 변환
        
        텍스트를 "제N조" 패턴을 기준으로 조문 단위로 분리하고,
        제목과 내용을 분리하여 ClauseData로 변환합니다.
        
        Args:
            text: 사용자 계약서 평문 텍스트
        
        Returns:
            ClauseData 객체 리스트
        
        Raises:
            ValueError: 텍스트가 비어있는 경우
        """
        import re
        
        if not text or not text.strip():
            raise ValueError("입력 텍스트가 비어있습니다")
        
        self.logger.info("사용자 계약서 텍스트 파싱 중")
        
        # 제N조 패턴으로 분리 (다양한 형식 지원)
        # 1. 제N조(제목) - 괄호 있는 형식
        # 2. 제N조 (제목) - 공백 + 괄호
        # 3. 제N조 제목 - 괄호 없는 형식
        clause_patterns = [
            re.compile(r'제(\d{1,2})조\s*\([^)]+\)'),  # 제1조(목적)
            re.compile(r'제(\d{1,2})조\s+\([^)]+\)'),  # 제1조 (목적)  
            re.compile(r'제(\d{1,2})조\s+[^\n\r]+'),   # 제1조 목적
            re.compile(r'제(\d{1,2})조'),              # 제1조 (단독)
        ]
        
        # 모든 제N조 패턴의 위치 찾기 (여러 패턴 시도)
        matches = []
        for pattern in clause_patterns:
            matches = list(pattern.finditer(text))
            if matches:
                self.logger.debug(f"패턴 매칭 성공: {pattern.pattern}")
                break
        
        if not matches:
            # 제N조 패턴이 없으면 전체를 하나의 조문으로 처리
            self.logger.warning("제N조 패턴을 찾을 수 없습니다. 전체를 하나의 조문으로 처리합니다.")
            return [ClauseData(
                id="user-1",
                title="사용자 조문 1",
                subtitle=None,
                type="조",
                text=text.strip()
            )]
        
        clauses = []
        
        for idx, match in enumerate(matches, start=1):
            title = match.group(0)
            start_pos = match.end()
            
            # 다음 조문의 시작 위치 찾기
            if idx < len(matches):
                end_pos = matches[idx].start()
            else:
                end_pos = len(text)
            
            # 내용 추출 (제목 이후부터 다음 조문 전까지)
            content = text[start_pos:end_pos].strip()
            
            # 내용이 비어있으면 건너뛰기
            if not content:
                self.logger.debug(f"내용이 없는 조문 건너뛰기: {title}")
                continue
            
            clause = ClauseData(
                id=f"user-{idx}",
                title=title,
                subtitle=None,
                type="조",
                text=content
            )
            clauses.append(clause)
            self.logger.debug(f"파싱된 조문: {title} (길이: {len(content)}자)")
        
        self.logger.info(f"총 {len(clauses)}개의 조문을 파싱했습니다")
        return clauses
    
    def load_user_contract_from_file(self, file_path: Path, chunked: bool = False) -> List[ClauseData]:
        """
        파일(.txt 또는 .docx)에서 사용자 계약서를 로드
        
        Args:
            file_path: 파일 경로 (.txt 또는 .docx)
            chunked: True면 문단 단위로 청킹, False면 조 단위로 파싱
        
        Returns:
            ClauseData 객체 리스트
        
        Raises:
            FileNotFoundError: 파일이 존재하지 않는 경우
        """
        if not file_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
        
        file_ext = file_path.suffix.lower()
        self.logger.info(f"사용자 계약서 파일 로드 중: {file_path} (형식: {file_ext}, 청킹: {chunked})")
        
        try:
            # 파일 형식에 따라 텍스트 추출
            if file_ext == '.docx':
                text = self._extract_text_from_docx(file_path)
            elif file_ext == '.txt':
                text = self._read_text_file_with_encoding_detection(file_path)
            else:
                raise ValueError(f"지원하지 않는 파일 형식: {file_ext} (지원: .txt, .docx)")
            
            # 청킹 방식에 따라 처리
            if chunked:
                return self.load_user_contract_chunked(text)
            else:
                return self.load_user_contract_from_text(text)
        
        except Exception as e:
            self.logger.error(f"파일 읽기 오류: {e}")
            raise
    
    def _read_text_file_with_encoding_detection(self, file_path: Path) -> str:
        """
        텍스트 파일을 여러 인코딩으로 시도하여 읽기
        
        한국어 파일의 경우 UTF-8, CP949, EUC-KR 순서로 시도합니다.
        
        Args:
            file_path: 텍스트 파일 경로
        
        Returns:
            읽은 텍스트
        
        Raises:
            UnicodeDecodeError: 모든 인코딩 시도 실패
        """
        encodings = ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    text = f.read()
                self.logger.info(f"파일 인코딩 감지 성공: {encoding}")
                return text
            except UnicodeDecodeError:
                self.logger.debug(f"인코딩 {encoding} 실패, 다음 시도...")
                continue
        
        # 모든 인코딩 실패
        raise UnicodeDecodeError(
            'unknown', b'', 0, 1,
            f"파일을 읽을 수 없습니다. 시도한 인코딩: {', '.join(encodings)}"
        )
    
    def _extract_text_from_docx(self, docx_path: Path) -> str:
        """
        DOCX 파일에서 텍스트 추출
        
        Args:
            docx_path: DOCX 파일 경로
        
        Returns:
            추출된 텍스트
        """
        try:
            from docx import Document
        except ImportError:
            raise ImportError(
                "DOCX 파일 처리를 위해 python-docx가 필요합니다.\n"
                "설치: pip install python-docx"
            )
        
        self.logger.info(f"DOCX 파일에서 텍스트 추출 중: {docx_path.name}")
        
        doc = Document(str(docx_path))
        
        # 모든 문단의 텍스트 추출
        paragraphs = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:  # 빈 문단 제외
                paragraphs.append(text)
        
        # 개행으로 연결
        full_text = "\n".join(paragraphs)
        
        self.logger.info(f"텍스트 추출 완료: {len(paragraphs)}개 문단, {len(full_text)}자")
        
        return full_text
    
    def filter_clauses(
        self,
        clauses: List[ClauseData],
        clause_type: str = "조"
    ) -> List[ClauseData]:
        """
        특정 타입의 조문만 필터링
        
        Args:
            clauses: ClauseData 객체 리스트
            clause_type: 필터링할 조문 타입 (기본값: "조")
        
        Returns:
            필터링된 ClauseData 객체 리스트
        """
        filtered = [clause for clause in clauses if clause.type == clause_type]
        
        self.logger.info(
            f"타입 '{clause_type}' 필터링: {len(clauses)}개 중 {len(filtered)}개 선택"
        )
        
        return filtered
    
    def _parse_clause_from_dict(self, data: dict) -> ClauseData:
        """
        딕셔너리에서 ClauseData 객체 생성
        
        Args:
            data: JSON에서 파싱된 딕셔너리
        
        Returns:
            ClauseData 객체
        
        Raises:
            ValueError: 필수 필드가 누락된 경우
        """
        required_fields = ['id', 'title']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            raise ValueError(f"필수 필드 누락: {', '.join(missing_fields)}")
        
        # text 필드: text_raw 또는 text 사용
        text = data.get('text_raw') or data.get('text', '')
        if not text:
            raise ValueError("text_raw 또는 text 필드가 필요합니다")
        
        # text_norm 필드: 있으면 사용, 없으면 text 사용
        text_norm = data.get('text_norm', text)
        
        # type 필드: unit_type 또는 type 사용
        clause_type = data.get('unit_type') or data.get('type', 'article')
        
        return ClauseData(
            id=data['id'],
            title=data['title'],
            subtitle=data.get('subtitle'),
            type=clause_type,
            text=text,
            text_norm=text_norm,
            breadcrumb=data.get('breadcrumb')
        )
