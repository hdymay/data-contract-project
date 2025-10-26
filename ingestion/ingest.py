import cmd
import os
import sys
from pathlib import Path
from typing import Optional
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# python ingestion/ingest.py
# verify -u data/user_contract_sample_1.txt


class IngestionCLI(cmd.Cmd):
    """지식베이스 구축 CLI 모듈"""
    
    intro = """

Commands:
  - run     : 작업 실행
  - search  : FAISS 검색 테스트
  - verify  : 계약서 검증 (표준 계약서 대비 사용자 계약서 검증)
  - status  : 디렉토리 상태 확인
  - help    : 도움말
  - exit    : 종료

"""
    prompt = ' ingestion> '
    
    def __init__(self):
        super().__init__()
        # 경로 설정
        self.base_path = Path("/app/data")
        self.source_path = self.base_path / "source_documents"
        self.extracted_path = self.base_path / "extracted_documents"
        self.chunked_path = self.base_path / "chunked_documents"
        self.index_path = Path("/app/search_indexes")
    
    def do_run(self, arg):
        """
        작업 실행
        
        사용법:
          run --mode <mode> --file <filename>
          run -m <mode> -f <filename>
          
        예시:
          run --mode parsing --file create_std_contract.pdf
          run -m parsing -f create_std_contract.docx
          run -m full -f all
          run --mode chunking --file create_std_contract.json
          run -m embedding -f create_std_contract_chunks.jsonl
        
        --mode 옵션:
          - full        : 전체 파이프라인 (파싱→청킹→임베딩→인덱싱)
          - parsing     : 문서 파싱만 (PDF/DOCX 자동 감지)
          - chunking    : JSON 청킹만
          - embedding   : 임베딩 + 인덱싱
          - s_embedding : 간이 청킹 및 임베딩 (조/별지 단위)
        
        --file 옵션:
          - all             : 모든 파일 (PDF, DOCX 모두)
          - <filename>      : 특정 파일 하나
        
        참고:
          - 파일 확장자 감지로 파서 자동 선택
          - 파일명에 'guidebook' 포함 → 활용안내서 모듈 사용
          - 그 외 파일 → 표준계약서 모듈 사용
        """
        try:
            # 인자 파싱
            args = self._parse_run_args(arg)
            if not args:
                return
            
            mode = args.get('mode')
            filename = args.get('file')
            
            logger.info("=" * 60)
            logger.info(f" 작업 시작")
            logger.info(f"  모드: {mode}")
            logger.info(f"  파일: {filename}")
            logger.info("=" * 60)
            
            # 모드별 실행
            if mode == 'full':
                self._run_full_pipeline(filename)
            elif mode == 'parsing':
                self._run_parsing(filename)
            elif mode == 'chunking':
                self._run_chunking(filename)
            elif mode == 'embedding':
                self._run_embedding(filename)
            elif mode == 's_embedding':
                self._run_simple_embedding(filename)
            else:
                logger.error(f" 알 수 없는 모드: {mode}")
                return
            
            logger.info("=" * 60)
            logger.info(" 작업 완료")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f" 오류 발생: {e}")
            import traceback
            traceback.print_exc()
    
    def _parse_run_args(self, arg):
        """run 명령어 인자 파싱"""
        args = {}
        tokens = arg.split()
        
        i = 0
        while i < len(tokens):
            if tokens[i] in ['--mode', '-m'] and i + 1 < len(tokens):
                mode = tokens[i + 1]
                if mode not in ['full', 'parsing', 'chunking', 'embedding', 's_embedding']:
                    logger.error(f" 잘못된 모드: {mode}")
                    logger.error("   사용 가능: full, parsing, chunking, embedding, s_embedding")
                    return None
                args['mode'] = mode
                i += 2
            elif tokens[i] in ['--file', '-f'] and i + 1 < len(tokens):
                args['file'] = tokens[i + 1]
                i += 2
            else:
                i += 1
        
        # 필수 인자 체크
        if 'mode' not in args:
            logger.error(" --mode (-m) 인자가 필요합니다")
            return None
        if 'file' not in args:
            logger.error(" --file (-f) 인자가 필요합니다")
            return None
        
        return args
    
    def _is_guidebook(self, filename):
        if filename == 'all':
            return None  # all은 혼합 타입
        return 'guidebook' in filename.lower()
    
    def _run_full_pipeline(self, filename):
        logger.info("=== 전체 파이프라인 실행 ===")
        self._run_parsing(filename)
        
        # 파싱 결과를 청킹 입력으로
        if filename == 'all':
            chunking_file = 'all'
        else:
            # .pdf 또는 .docx를 .json으로 변환
            chunking_file = filename.replace('.pdf', '.json').replace('.docx', '_structured.json')
        
        self._run_chunking(chunking_file)
        
        # 청킹 결과를 임베딩 입력으로
        if filename == 'all':
            embedding_file = 'all'
        else:
            # 확장자 제거 후 _chunks.jsonl 추가
            base_name = filename.rsplit('.', 1)[0]
            embedding_file = f"{base_name}_chunks.jsonl"
        
        self._run_embedding(embedding_file)
    
    def _get_parser(self, filename: str, file_ext: str):
        """
        파일명과 확장자를 기반으로 적절한 파서 선택
        
        Args:
            filename: 파일명
            file_ext: 파일 확장자 (.pdf, .docx 등)
            
        Returns:
            파서 인스턴스
        """
        is_guidebook = self._is_guidebook(filename)
        
        # 확장자와 문서 유형에 따라 파서 선택
        if file_ext == '.pdf':
            if is_guidebook:
                from ingestion.parsers.guidebook_pdf_parser import GuidebookPdfParser
                return GuidebookPdfParser(), "활용안내서 PDF 파서"
            else:
                from ingestion.parsers.std_contract_pdf_parser import StdContractPdfParser
                return StdContractPdfParser(), "표준계약서 PDF 파서"
        
        elif file_ext == '.docx':
            if is_guidebook:
                from ingestion.parsers.guidebook_docx_parser import GuidebookDocxParser
                return GuidebookDocxParser(), "활용안내서 DOCX 파서"
            else:
                from ingestion.parsers.std_contract_docx_parser import StdContractDocxParser
                return StdContractDocxParser(), "표준계약서 DOCX 파서"
        
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {file_ext}")
    
    def _run_parsing(self, filename):
        logger.info("=== 1단계: 파싱 시작 ===")
        logger.info(f"  입력: {self.source_path}")
        logger.info(f"  출력: {self.extracted_path}")
        
        # 출력 디렉토리 생성
        self.extracted_path.mkdir(parents=True, exist_ok=True)
        
        if filename == 'all':
            # 모든 파일 처리 (PDF와 DOCX)
            pdf_files = list(self.source_path.glob("*.pdf"))
            docx_files = list(self.source_path.glob("*.docx"))
            all_files = pdf_files + docx_files
            
            logger.info(f"  처리할 파일: {len(all_files)}개 (PDF: {len(pdf_files)}, DOCX: {len(docx_files)})")
            
            for file in all_files:
                file_ext = file.suffix.lower()
                
                try:
                    parser, parser_name = self._get_parser(file.name, file_ext)
                    logger.info(f"    - {file.name} ({parser_name})")
                    
                    parser.parse(file, self.extracted_path)
                    logger.info(f"        파싱 완료")
                    
                except ValueError as e:
                    logger.error(f"       [ERROR] {e}")
                except Exception as e:
                    logger.error(f"       [ERROR] 파싱 실패: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            # 특정 파일 처리
            file_path = self.source_path / filename
            if not file_path.exists():
                logger.error(f"   [ERROR] 파일을 찾을 수 없습니다: {filename}")
                return
            
            file_ext = file_path.suffix.lower()
            
            try:
                parser, parser_name = self._get_parser(filename, file_ext)
                logger.info(f"  처리할 파일: {filename}")
                logger.info(f"  사용 파서: {parser_name}")
                
                parser.parse(file_path, self.extracted_path)
                logger.info(f"   [OK] 파싱 완료")
                
            except ValueError as e:
                logger.error(f"   [ERROR] {e}")
            except Exception as e:
                logger.error(f"   [ERROR] 파싱 실패: {e}")
                import traceback
                traceback.print_exc()
    
    def _run_chunking(self, filename):
        logger.info("=== 2단계: 청킹 시작 ===")
        logger.info(f"  입력: {self.extracted_path}")
        logger.info(f"  출력: {self.chunked_path}")
        
        from ingestion.processors.chunker import TextChunker
        chunker = TextChunker(base_dir=self.base_path)
        
        def process_single(target_path: Path):
            try:
                chunker.process_file(target_path.name)
                logger.info(f"   [OK] 청킹 완료: {target_path.name}")
            except Exception as e:
                logger.error(f"   [ERROR] 청킹 실패: {target_path.name} - {e}")
                import traceback
                traceback.print_exc()
        
        if filename == 'all':
            files = sorted(self.extracted_path.glob("*.json"))
            if not files:
                logger.warning("  처리할 JSON 파일이 없습니다.")
                return
            
            logger.info(f"  처리할 파일: {len(files)}개")
            for file in files:
                is_guidebook = self._is_guidebook(file.name)
                chunker_type = "활용 안내서 청커" if is_guidebook else "표준계약서 청커"
                logger.info(f"    - {file.name} ({chunker_type})")
                process_single(file)
        else:
            file_path = self.extracted_path / filename
            if not file_path.exists():
                logger.error(f"   파일을 찾을 수 없습니다: {filename}")
                return
            
            is_guidebook = self._is_guidebook(filename)
            chunker_type = "활용 안내서 청커" if is_guidebook else "표준계약서 청커"
            logger.info(f"  처리할 파일: {filename}")
            logger.info(f"  사용 청커: {chunker_type}")
            
            process_single(file_path)
    def _run_embedding(self, filename):
        """임베딩 + 인덱싱 실행"""
        logger.info("=== 3단계: 임베딩 시작 ===")
        logger.info(f"  입력: {self.chunked_path}")
        
        # TODO: 임베딩 로직 구현
        # from ingestion.processors.embedder import TextEmbedder
        
        if filename == 'all':
            pattern = "*.jsonl"
            files = list(self.chunked_path.glob(pattern))
            logger.info(f"  처리할 파일: {len(files)}개")
            for file in files:
                is_guidebook = self._is_guidebook(file.name)
                doc_type = "활용안내서" if is_guidebook else "표준계약서"
                logger.info(f"    - {file.name} ({doc_type})")
        else:
            file_path = self.chunked_path / filename
            if not file_path.exists():
                logger.error(f"   파일을 찾을 수 없습니다: {filename}")
                return
            
            is_guidebook = self._is_guidebook(filename)
            doc_type = "활용안내서" if is_guidebook else "표준계약서"
            logger.info(f"  처리할 파일: {filename}")
            logger.info(f"  문서 타입: {doc_type}")
        
        # TODO: 임베딩 로직 (동일한 임베더 사용)
        pass
        
        logger.info("=== 4단계: 인덱싱 시작 ===")
        logger.info(f"  출력: {self.index_path}")
        
        # TODO: 인덱싱 로직 (Whoosh + FAISS)
        pass
    
    def _run_simple_embedding(self, filename):
        """
        간이 청킹 및 임베딩 실행
        조/별지 단위로 청킹하고 Azure OpenAI 임베딩 생성 후 FAISS에 저장
        """
        import os
        from ingestion.processors.s_embedder import SimpleEmbedder
        
        logger.info("=== 간이 청킹 및 임베딩 시작 ===")
        logger.info(f"  입력: {self.extracted_path}")
        logger.info(f"  출력: {self.index_path}")
        
        # Azure OpenAI API 키 및 엔드포인트 확인
        api_key = os.getenv('AZURE_OPENAI_API_KEY')
        azure_endpoint = os.getenv('AZURE_ENDPOINT')
        
        if not api_key:
            logger.error("   [ERROR] AZURE_OPENAI_API_KEY 환경변수가 설정되지 않았습니다")
            return
        
        if not azure_endpoint:
            logger.error("   [ERROR] AZURE_ENDPOINT 환경변수가 설정되지 않았습니다")
            return
        
        # structured.json 파일 경로 확인
        file_path = self.extracted_path / filename
        if not file_path.exists():
            logger.error(f"   [ERROR] 파일을 찾을 수 없습니다: {filename}")
            return
        
        # Azure OpenAI deployment name 확인 (선택사항, 기본값 사용 가능)
        deployment_name = os.getenv('AZURE_EMBEDDING_DEPLOYMENT', 'text-embedding-3-large')
        
        logger.info(f"  Azure Endpoint: {azure_endpoint}")
        logger.info(f"  Deployment Name: {deployment_name}")
        
        # SimpleEmbedder로 처리
        embedder = SimpleEmbedder(
            api_key=api_key,
            azure_endpoint=azure_endpoint,
            model=deployment_name
        )
        faiss_output_dir = self.index_path / "faiss"
        
        success = embedder.process_file(file_path, faiss_output_dir)
        
        if not success:
            logger.error("   [ERROR] 간이 청킹 및 임베딩 실패")
            return
    
    def do_search(self, arg):
        """
        FAISS 검색 테스트
        
        사용법:
          search --index <index_name> --query <query_text>
          search -i <index_name> -q <query_text>
          search -i <index_name> -q <query_text> --top <k>
          
        예시:
          search -i provide_std_contract -q "질의"
          search -i provide_std_contract -q "질의" --top 3
        
        --index 옵션:
          - FAISS 인덱스 이름
          - 예: provide_std_contract
        
        --query 옵션:
          - 검색할 질문
          
        --top 옵션 (선택):
          - 반환할 결과 개수 (기본값: 5)
        """
        try:
            import os
            from ingestion.processors.s_searcher import SimpleSearcher
            
            # 인자 파싱
            args = self._parse_search_args(arg)
            if not args:
                return
            
            index_name = args.get('index')
            query = args.get('query')
            top_k = args.get('top', 5)
            
            logger.info("=" * 60)
            logger.info(" 간이 RAG 검색 시작")
            logger.info(f"  인덱스: {index_name}")
            logger.info(f"  Top-K: {top_k}")
            logger.info("=" * 60)
            
            # Azure OpenAI API 키 및 엔드포인트 확인
            api_key = os.getenv('AZURE_OPENAI_API_KEY')
            azure_endpoint = os.getenv('AZURE_ENDPOINT')
            deployment_name = os.getenv('AZURE_EMBEDDING_DEPLOYMENT', 'text-embedding-3-large')
            
            if not api_key or not azure_endpoint:
                logger.error("   [ERROR] Azure OpenAI 환경변수가 설정되지 않았습니다")
                return
            
            # SimpleSearcher 초기화
            searcher = SimpleSearcher(
                api_key=api_key,
                azure_endpoint=azure_endpoint,
                embedding_model=deployment_name
            )
            
            # 인덱스 로드
            faiss_dir = self.index_path / "faiss"
            if not searcher.load_index(faiss_dir, index_name):
                return
            
            # 검색 수행
            results = searcher.search(query, top_k=top_k)
            
            # 결과 표시
            searcher.display_results(results)
            
            # 컨텍스트 추출 (LLM 사용 시 활용 가능)
            if results:
                context = searcher.get_context(results)
                logger.info(f"  [INFO] LLM용 컨텍스트 길이: {len(context)} 문자")
            
            logger.info("=" * 60)
            logger.info(" 검색 완료")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f" 오류 발생: {e}")
            import traceback
            traceback.print_exc()
    
    def _parse_search_args(self, arg):
        """search 명령어 인자 파싱"""
        args = {}
        tokens = arg.split()
        
        i = 0
        query_tokens = []
        collecting_query = False
        
        while i < len(tokens):
            if tokens[i] in ['--index', '-i'] and i + 1 < len(tokens):
                args['index'] = tokens[i + 1]
                i += 2
            elif tokens[i] in ['--query', '-q']:
                collecting_query = True
                i += 1
            elif tokens[i] in ['--top', '-t'] and i + 1 < len(tokens):
                try:
                    args['top'] = int(tokens[i + 1])
                except ValueError:
                    logger.error(f" --top 값은 숫자여야 합니다: {tokens[i + 1]}")
                    return None
                collecting_query = False
                i += 2
            elif collecting_query:
                # --top이 나올 때까지 모든 토큰을 쿼리로 수집
                if tokens[i] in ['--top', '-t']:
                    collecting_query = False
                    continue
                query_tokens.append(tokens[i])
                i += 1
            else:
                i += 1
        
        # 쿼리 조립
        if query_tokens:
            args['query'] = ' '.join(query_tokens)
        
        # 필수 인자 체크
        if 'index' not in args:
            logger.error(" --index (-i) 인자가 필요합니다")
            return None
        if 'query' not in args:
            logger.error(" --query (-q) 인자가 필요합니다")
            return None
        
        return args
    
    def do_status(self, arg):
        """
        현재 디렉토리 상태 확인
        
        사용법:
          status
          status --detail
        """
        logger.info("=== 디렉토리 상태 ===")
        
        # source_documents
        pdf_files = list(self.source_path.glob("*.pdf")) if self.source_path.exists() else []
        docx_files = list(self.source_path.glob("*.docx")) if self.source_path.exists() else []
        logger.info(f"\n [원본 문서] ({self.source_path}):")
        logger.info(f"  총 {len(pdf_files) + len(docx_files)}개 파일 (PDF: {len(pdf_files)}, DOCX: {len(docx_files)})")
        if '--detail' in arg:
            for f in pdf_files + docx_files:
                logger.info(f"    - {f.name}")
        
        # extracted_documents
        json_files = list(self.extracted_path.glob("*.json")) if self.extracted_path.exists() else []
        logger.info(f"\n [파싱 결과] ({self.extracted_path}):")
        logger.info(f"  총 {len(json_files)}개 파일")
        if '--detail' in arg:
            for f in json_files:
                logger.info(f"    - {f.name}")
        
        # chunked_documents
        jsonl_files = list(self.chunked_path.glob("*.jsonl")) if self.chunked_path.exists() else []
        logger.info(f"\n [청킹 결과] ({self.chunked_path}):")
        logger.info(f"  총 {len(jsonl_files)}개 파일")
        if '--detail' in arg:
            for f in jsonl_files:
                logger.info(f"    - {f.name}")
        
        # search_indexes
        whoosh_status = self._check_whoosh_index()
        faiss_status = self._check_faiss_index()
        
        logger.info(f"\n [검색 인덱스] ({self.index_path}):")
        logger.info(f"  Whoosh: {whoosh_status['icon']} {whoosh_status['message']}")
        logger.info(f"  FAISS: {faiss_status['icon']} {faiss_status['message']}")
    
    def _check_whoosh_index(self) -> dict:
        """
        Whoosh 인덱스 파일 존재 확인
        
        Returns:
            dict: {"icon": str, "message": str, "exists": bool}
        """
        whoosh_dir = self.index_path / "whoosh"
        
        # Whoosh 인덱스 필수 파일 체크
        # _MAIN_*.toc 파일이 있으면 인덱스가 생성된 것
        toc_files = list(whoosh_dir.glob("_MAIN_*.toc"))
        
        if not toc_files:
            return {"icon": "X", "message": "인덱스 없음", "exists": False}
        
        # 세그먼트 파일도 확인
        seg_files = list(whoosh_dir.glob("*.seg"))
        
        if toc_files and seg_files:
            return {"icon": "O", "message": f"준비됨 ({len(toc_files)}개 TOC, {len(seg_files)}개 세그먼트)", "exists": True}
        else:
            return {"icon": "!", "message": "인덱스 불완전 (세그먼트 파일 없음)", "exists": False}
    
    def _check_faiss_index(self) -> dict:
        """
        FAISS 인덱스 파일 존재 확인
        
        Returns:
            dict: {"icon": str, "message": str, "exists": bool}
        """
        faiss_dir = self.index_path / "faiss"
        
        # FAISS 인덱스 필수 파일 체크
        # 일반적으로 .index 또는 .faiss 확장자 파일
        index_files = list(faiss_dir.glob("*.index")) + list(faiss_dir.glob("*.faiss"))
        
        if not index_files:
            return {"icon": "X", "message": "인덱스 없음", "exists": False}
        
        # 메타데이터 파일도 확인 (선택적)
        metadata_files = list(faiss_dir.glob("*.json")) + list(faiss_dir.glob("*.pkl"))
        
        total_size = sum(f.stat().st_size for f in index_files) / (1024 * 1024)  # MB
        
        msg = f"준비됨 ({len(index_files)}개 파일, {total_size:.1f}MB"
        if metadata_files:
            msg += f", 메타데이터 {len(metadata_files)}개"
        msg += ")"
        return {"icon": "O", "message": msg, "exists": True}
    
    def do_ls(self, arg):
        """
        파일 목록 보기 (별칭: list)
        
        사용법:
          ls <디렉토리>
          
        디렉토리:
          - source    : 원본 PDF
          - extracted : 파싱 결과
          - chunked   : 청킹 결과
          - index     : 인덱스
        """
        if not arg:
            logger.error(" 디렉토리를 지정해주세요 (source, extracted, chunked, index)")
            return
        
        path_map = {
            'source': self.source_path,
            'extracted': self.extracted_path,
            'chunked': self.chunked_path,
            'index': self.index_path
        }
        
        if arg not in path_map:
            logger.error(f" 잘못된 디렉토리: {arg}")
            return
        
        target_path = path_map[arg]
        if not target_path.exists():
            logger.warning(f"  디렉토리가 존재하지 않습니다: {target_path}")
            return
        
        logger.info(f"\n {target_path}:")
        files = sorted(target_path.iterdir())
        for f in files:
            if f.is_file():
                size_kb = f.stat().st_size / 1024
                logger.info(f"  {f.name} ({size_kb:.1f} KB)")
            elif f.is_dir():
                logger.info(f"   {f.name}/")
    
    def do_verify(self, arg):
        """
        계약서 검증 실행
        
        사용법:
          verify --user <user_contract_path>
          verify -u <user_contract_path>
          verify -u <user_contract_path> --format <format>
          
        예시:
          verify -u data/user_contract.txt
          verify -u data/user_contract.docx
          verify -u data/user_contract.docx --format pdf
          verify -u data/user_contract.txt --format both
        
        --user 옵션:
          - 사용자 계약서 파일 경로 (.txt 또는 .docx 파일)
          
        --format 옵션 (선택):
          - text : 텍스트 보고서만 생성 (기본값)
          - pdf  : PDF 보고서만 생성
          - both : 텍스트 + PDF 보고서 모두 생성
        
        참고:
          - 표준 계약서는 자동으로 data/chunked_documents/provide_std_contract_chunks.json 사용
          - 하이브리드 검색 (BM25 + FAISS) + LLM 검증 파이프라인 사용
          - 항 단위 청킹으로 정확도 향상
          - 보고서는 data/reports/ 디렉토리에 저장됩니다
        """
        try:
            # 인자 파싱
            args = self._parse_verify_args(arg)
            if not args:
                return
            
            user_contract_path = args.get('user')
            report_format = args.get('format', 'text')
            
            logger.info("=" * 60)
            logger.info(" 계약서 검증 시작")
            logger.info(f"  사용자 계약서: {user_contract_path}")
            logger.info(f"  보고서 형식: {report_format}")
            logger.info("=" * 60)
            
            # 검증 실행
            self._run_verification(user_contract_path, report_format)
            
            logger.info("=" * 60)
            logger.info(" 검증 완료")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f" 오류 발생: {e}")
            import traceback
            traceback.print_exc()
    
    def _parse_verify_args(self, arg):
        """verify 명령어 인자 파싱"""
        args = {}
        tokens = arg.split()
        
        i = 0
        while i < len(tokens):
            if tokens[i] in ['--user', '-u'] and i + 1 < len(tokens):
                args['user'] = tokens[i + 1]
                i += 2
            elif tokens[i] in ['--format', '-f'] and i + 1 < len(tokens):
                fmt = tokens[i + 1]
                if fmt not in ['text', 'pdf', 'both']:
                    logger.error(f" 잘못된 형식: {fmt}")
                    logger.error("   사용 가능: text, pdf, both")
                    return None
                args['format'] = fmt
                i += 2
            else:
                i += 1
        
        # 필수 인자 체크
        if 'user' not in args:
            logger.error(" --user (-u) 인자가 필요합니다")
            return None
        
        return args
    
    def _group_results_by_article(self, match_results):
        """매칭 결과를 조문별로 그룹화"""
        article_groups = {}
        
        for match in match_results:
            if match.is_matched:
                # 조문 번호 추출 (예: "제1조 (목적)" → "제1조")
                user_title = match.matched_clause.title
                article_num = user_title.split()[0] if user_title.startswith('제') else user_title
                
                if article_num not in article_groups:
                    article_groups[article_num] = []
                
                article_groups[article_num].append(match)
        
        return article_groups
    
    def _generate_detailed_report(self, report_path, result, grouped_results, user_clauses):
        """상세 리포트 생성 (run_chunked_verification.py와 동일)"""
        from datetime import datetime
        
        with open(report_path, 'w', encoding='utf-8') as f:
            # 헤더
            f.write("="*100 + "\n")
            f.write("개선된 계약서 검증 보고서 (항 단위 청킹 + 조문별 그룹화)\n")
            f.write("="*100 + "\n\n")
            f.write(f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"검증 방식: 항 단위 청킹 → 표준 조문 매칭 → 조문별 그룹화\n\n")
            
            # 점수 해석 가이드
            f.write("📖 점수 해석 가이드\n")
            f.write("-" * 50 + "\n")
            f.write("• BM25 점수: 키워드 매칭 점수 (높을수록 좋음, 0~1)\n")
            f.write("• FAISS 유사도: 의미적 유사도 (높을수록 좋음, 0~100%)\n")
            f.write("  - 계산: exp(-(거리^2)/2) × 100%\n")
            f.write("  - 80%+: 매우 유사\n")
            f.write("  - 60~80%: 어느 정도 유사\n")
            f.write("  - 40~60%: 유사도 낮음\n")
            f.write("  - 40% 미만: 매우 다름\n")
            f.write("• 하이브리드: BM25(20%) + FAISS(80%) 결합 점수\n\n")
            
            # 요약 통계
            f.write("📊 검증 결과 요약\n")
            f.write("-" * 50 + "\n")
            f.write(f"총 청크 수: {len(user_clauses)}개\n")
            f.write(f"매칭된 청크: {result.matched_clauses}개\n")
            f.write(f"매칭률: {result.matched_clauses/len(user_clauses)*100:.1f}%\n")
            f.write(f"조문별 그룹: {len(grouped_results)}개\n\n")
            
            # 조문별 매칭 결과
            f.write("📋 조문별 매칭 결과\n")
            f.write("-" * 50 + "\n")
            
            for article_num in sorted(grouped_results.keys(), key=lambda x: int(x[1:-1]) if x[1:-1].isdigit() else 999):
                matches = grouped_results[article_num]
                f.write(f"\n🔸 {article_num} ({len(matches)}개 항 매칭)\n")
                
                for match in matches:
                    f.write(f"   ✅ [{match.standard_clause.id}] {match.standard_clause.title}\n")
                    f.write(f"      ← {match.matched_clause.title}\n")
                    
                    # 별지 참조 확인
                    if "[별지" in match.standard_clause.text:
                        f.write(f"      📎 별지 참조 있음\n")
                    
                    if match.llm_decision:
                        f.write(f"      신뢰도: {match.llm_decision.confidence:.0%}\n")
                    f.write(f"      하이브리드 점수: {match.hybrid_score:.3f}\n")
                    # FAISS 유사도 계산: exp(-(distance^2)/2) * 100
                    import numpy as np
                    if match.faiss_raw_distance is not None:
                        faiss_similarity = np.exp(-(match.faiss_raw_distance ** 2) / 2.0) * 100
                        f.write(f"      BM25: {match.bm25_score:.3f} | FAISS 유사도: {faiss_similarity:.1f}%\n")
                    else:
                        f.write(f"      FAISS 점수: {match.faiss_score:.3f}\n")
                    f.write("\n")
            
            # 상세 매칭 결과
            f.write("\n" + "="*100 + "\n")
            f.write("📝 상세 매칭 결과\n")
            f.write("="*100 + "\n\n")
            
            for i, match in enumerate([m for m in result.match_results if m.is_matched], 1):
                f.write(f"{i:2d}. 매칭 성공\n")
                f.write(f"    표준 조문: [{match.standard_clause.id}] {match.standard_clause.title}\n")
                
                # 별지 참조 확인
                if "[별지" in match.standard_clause.text:
                    import re
                    appendix_refs = re.findall(r'\[별지(\d+)\]', match.standard_clause.text)
                    if appendix_refs:
                        f.write(f"    📎 별지 참조: 별지{', 별지'.join(appendix_refs)}\n")
                
                f.write(f"    사용자 항: {match.matched_clause.title}\n")
                
                if match.llm_decision:
                    f.write(f"    LLM 신뢰도: {match.llm_decision.confidence:.0%}\n")
                    f.write(f"    LLM 판단: {match.llm_decision.reasoning}\n")
                
                f.write(f"    검색 점수:\n")
                f.write(f"      - 하이브리드: {match.hybrid_score:.3f}\n")
                # FAISS 유사도 계산
                import numpy as np
                if match.faiss_raw_distance is not None and match.bm25_raw_score is not None:
                    f.write(f"      - BM25: {match.bm25_score:.3f} (원점수: {match.bm25_raw_score:.3f})\n")
                    faiss_similarity = np.exp(-(match.faiss_raw_distance ** 2) / 2.0) * 100
                    f.write(f"      - FAISS 유사도: {faiss_similarity:.1f}%\n")
                else:
                    f.write(f"      - FAISS 점수: {match.faiss_score:.3f}\n")
                
                f.write(f"\n    표준 조문 내용:\n")
                f.write(f"    {match.standard_clause.text[:200]}...\n")
                
                f.write(f"\n    사용자 항 내용:\n")
                f.write(f"    {match.matched_clause.text[:200]}...\n")
                
                f.write("\n" + "-"*80 + "\n\n")
            
            # 매칭되지 않은 표준 조문 (누락된 조문)
            if result.missing_clauses:
                f.write("❌ 매칭되지 않은 표준 조문 (누락)\n")
                f.write("-" * 50 + "\n")
                for clause in result.missing_clauses:
                    f.write(f"   [{clause.id}] {clause.title}\n")
                    f.write(f"   {clause.text[:100]}...\n\n")
            
            # 매칭되지 않은 사용자 항 (Top-3 후보와 함께 표시)
            matched_user_ids = {m.matched_clause.id for m in result.match_results if m.is_matched}
            unmatched_results = [m for m in result.match_results if not m.is_matched and m.matched_clause is not None]
            
            # 사용자 항별로 그룹화
            from collections import defaultdict
            unmatched_by_user = defaultdict(list)
            for match in unmatched_results:
                unmatched_by_user[match.matched_clause.id].append(match)
            
            if unmatched_by_user:
                f.write("\n❓ 매칭되지 않은 사용자 항 (관련 조항 분석)\n")
                f.write("=" * 100 + "\n\n")
                
                for user_id, matches in unmatched_by_user.items():
                    # 사용자 항 정보
                    user_clause = matches[0].matched_clause
                    f.write(f"📄 {user_clause.title}\n")
                    f.write(f"   {user_clause.text[:200]}...\n\n")
                    
                    f.write(f"   💭 관련 조항 분석 (Top {len(matches)}):\n")
                    f.write("   " + "-" * 90 + "\n\n")
                    
                    # Top-3 후보 표시
                    for idx, match in enumerate(matches[:3], 1):
                        f.write(f"   {idx}️⃣ [{match.standard_clause.id}] {match.standard_clause.title}\n")
                        f.write(f"      📊 유사도: {match.hybrid_score:.2f}\n")
                        if match.llm_decision:
                            f.write(f"      🤖 신뢰도: {match.llm_decision.confidence:.2f}\n")
                            if match.llm_decision.reasoning:
                                f.write(f"      💭 LLM 판단: {match.llm_decision.reasoning}\n")
                        f.write("\n")
                    
                    f.write("\n")
    
    def _run_verification(self, user_contract_path: str, report_format: str):
        """
        계약서 검증 실행
        
        Args:
            user_contract_path: 사용자 계약서 파일 경로
            report_format: 보고서 형식 (text, pdf, both)
        """
        import sys
        from pathlib import Path
        
        # backend 모듈 경로 추가
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from backend.clause_verification.node_1_clause_matching.data_loader import ContractDataLoader
        from backend.clause_verification.node_1_clause_matching.verification_engine import ContractVerificationEngine
        from backend.clause_verification.node_1_clause_matching.embedding_service import EmbeddingService
        from backend.clause_verification.node_1_clause_matching.hybrid_search import HybridSearchEngine
        from backend.clause_verification.node_1_clause_matching.llm_verification import LLMVerificationService
        
        # 표준 계약서 경로 (항 단위 청킹 버전)
        standard_contract_path = "data/chunked_documents/provide_std_contract_chunks.json"
        
        # 파일 존재 확인
        if not Path(standard_contract_path).exists():
            logger.error(f"   [ERROR] 표준 계약서를 찾을 수 없습니다: {standard_contract_path}")
            logger.error("   힌트: 먼저 'python embed_std_contract_articles.py'를 실행하세요")
            return
        
        if not Path(user_contract_path).exists():
            logger.error(f"   [ERROR] 사용자 계약서를 찾을 수 없습니다: {user_contract_path}")
            return
        
        logger.info("\n=== 1단계: 데이터 로드 ===")
        
        # 데이터 로더 초기화
        loader = ContractDataLoader()
        
        # 표준 계약서 로드
        standard_clauses = loader.load_standard_contract()
        logger.info(f"   [OK] 표준 계약서 로드: {len(standard_clauses)}개 조문")
        
        # 사용자 계약서 로드 (항 단위 청킹 방식)
        # 여러 인코딩 시도
        encodings = ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']
        user_text = None
        for encoding in encodings:
            try:
                with open(user_contract_path, 'r', encoding=encoding) as f:
                    user_text = f.read()
                logger.info(f"   [OK] 파일 인코딩 감지: {encoding}")
                break
            except UnicodeDecodeError:
                continue
        
        if user_text is None:
            logger.error(f"   [ERROR] 파일을 읽을 수 없습니다. 시도한 인코딩: {', '.join(encodings)}")
            return
        
        user_clauses = loader.load_user_contract_chunked(user_text)
        logger.info(f"   [OK] 사용자 계약서 로드: {len(user_clauses)}개 청크 (항 단위)")
        
        logger.info("\n=== 2단계: 검증 엔진 초기화 ===")
        
        # 서비스 초기화
        embedding_service = EmbeddingService()
        hybrid_search = HybridSearchEngine()  # 기본 가중치 사용 (BM25: 0.3, FAISS: 0.7)
        
        # 기존 인덱스 로드 시도 (없으면 자동 생성됨)
        try:
            hybrid_search.load_faiss_index()
            logger.info("   [OK] 기존 FAISS 인덱스 로드")
        except FileNotFoundError:
            logger.info("   [INFO] FAISS 인덱스 없음 (검증 시 자동 생성됨)")
        
        llm_verification = LLMVerificationService()
        
        # 검증 엔진 초기화
        engine = ContractVerificationEngine(
            embedding_service=embedding_service,
            hybrid_search=hybrid_search,
            llm_verification=llm_verification
        )
        
        logger.info("   [OK] 검증 엔진 초기화 완료")
        
        logger.info("\n=== 3단계: 계약서 검증 수행 ===")
        
        # 검증 수행 (역방향 검증: 사용자→표준)
        result = engine.verify_contract_reverse(
            standard_clauses=standard_clauses,
            user_clauses=user_clauses,
            top_k_candidates=10,
            top_k_titles=5,
            min_confidence=0.5
        )
        
        logger.info(f"   [OK] 검증 완료")
        logger.info(f"        - 표준 조문 수: {result.total_standard_clauses}")
        logger.info(f"        - 사용자 청크 수: {result.total_user_clauses}")
        logger.info(f"        - 매칭된 청크: {result.matched_clauses}")
        logger.info(f"        - 누락된 조문: {result.missing_count}")
        logger.info(f"        - 검증 완료율: {result.verification_rate:.1f}%")
        
        logger.info("\n=== 4단계: 결과 분석 및 그룹화 ===")
        
        # 조문별 그룹화
        grouped_results = self._group_results_by_article(result.match_results)
        logger.info(f"   [OK] 조문별 그룹: {len(grouped_results)}개")
        
        logger.info("\n=== 5단계: 상세 보고서 생성 ===")
        
        # 상세 보고서 생성
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = Path(f"data/reports/chunked_verification_report_{timestamp}.txt")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._generate_detailed_report(report_path, result, grouped_results, user_clauses)
        
        logger.info(f"   [OK] 상세 보고서 저장: {report_path}")
        
        # 콘솔 요약 출력
        summary = result.get_summary()
        print("\n" + "="*80)
        print("📋 계약서 검증 결과 요약")
        print("="*80)
        print(f"\n📊 통계:")
        print(f"   총 청크 수: {len(user_clauses)}개")
        print(f"   매칭된 청크: {summary['matched_clauses']}개")
        print(f"   매칭률: {result.matched_clauses/len(user_clauses)*100:.1f}%")
        print(f"   조문별 그룹: {len(grouped_results)}개")
        print(f"\n📄 상세 보고서: {report_path}")
        print("="*80)
    
    def do_exit(self, arg):
        logger.info("ingestion 종료")
        return True
    
    def emptyline(self):
        pass
    
    def default(self, line):
        logger.error(f" 알 수 없는 명령어 {line}")
        logger.info(" 'help'를 입력하여 사용 가능한 명령어 확인")


def main():
    """메인 함수"""
    cli = IngestionCLI()
    try:
        cli.cmdloop()
    except KeyboardInterrupt:
        logger.info("\n\ningestion 종료")
        sys.exit(0)


if __name__ == "__main__":
    main()
