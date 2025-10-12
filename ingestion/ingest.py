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


class IngestionCLI(cmd.Cmd):
    """지식베이스 구축 인터랙티브 CLI"""
    
    intro = """

Commands:
  - run     : 작업 실행
  - status  : 현재 디렉토리 상태 확인
  - help    : 도움말
  - exit    : 종료

"""
    prompt = ' ingestion> '
    
    def __init__(self):
        super().__init__()
        # 기본 경로 설정
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
          run -m parsing -f create_std_contract.pdf
          run -m full -f all
          run --mode chunking --file create_std_contract.json
          run -m embedding -f create_std_contract_chunks.jsonl
        
        모드:
          - full      : 전체 파이프라인 (파싱→청킹→임베딩→인덱싱)
          - parsing   : PDF 파싱만
          - chunking  : JSON 청킹만
          - embedding : 임베딩 + 인덱싱
        
        파일:
          - all             : 모든 파일
          - <filename>      : 특정 파일 하나
        
        참고:
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
                if mode not in ['full', 'parsing', 'chunking', 'embedding']:
                    logger.error(f" 잘못된 모드: {mode}")
                    logger.error("   사용 가능: full, parsing, chunking, embedding")
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
        logger.info(" 전체 파이프라인 실행")
        self._run_parsing(filename)
        
        # 파싱 결과를 청킹 입력으로
        if filename == 'all':
            chunking_file = 'all'
        else:
            chunking_file = filename.replace('.pdf', '.json')
        
        self._run_chunking(chunking_file)
        
        # 청킹 결과를 임베딩 입력으로
        if filename == 'all':
            embedding_file = 'all'
        else:
            embedding_file = filename.replace('.pdf', '_chunks.jsonl')
        
        self._run_embedding(embedding_file)
    
    def _run_parsing(self, filename):
        from ingestion.parsers.standard_contract_parser import StandardContractParser
        # from ingestion.parsers.guidebook_parser import GuidebookParser
        
        logger.info(" === 1단계: 파싱 시작 ===")
        logger.info(f"  입력: {self.source_path}")
        logger.info(f"  출력: {self.extracted_path}")
        
        # 출력 디렉토리 생성
        self.extracted_path.mkdir(parents=True, exist_ok=True)
        
        if filename == 'all':
            # 모든 파일 처리
            pattern = "*.pdf"
            files = list(self.source_path.glob(pattern))
            logger.info(f"  처리할 파일: {len(files)}개")
            
            for file in files:
                is_guidebook = self._is_guidebook(file.name)
                parser_type = "활용안내서 파서" if is_guidebook else "표준계약서 파서"
                logger.info(f"    - {file.name} ({parser_type})")
                
                if is_guidebook:
                    logger.warning(f"        활용안내서 파서(미구현)")
                    continue
                else:
                    # 표준계약서 파싱
                    try:
                        parser = StandardContractParser()
                        parser.parse(file, self.extracted_path)
                        logger.info(f"       파싱 완료")
                    except Exception as e:
                        logger.error(f"       파싱 실패: {e}")
        else:
            # 특정 파일 처리
            file_path = self.source_path / filename
            if not file_path.exists():
                logger.error(f"   파일을 찾을 수 없습니다: {filename}")
                return
            
            is_guidebook = self._is_guidebook(filename)
            parser_type = "활용안내서 파서" if is_guidebook else "표준계약서 파서"
            logger.info(f"  처리할 파일: {filename}")
            logger.info(f"  사용 파서: {parser_type}")
            
            if is_guidebook:
                logger.error(f"   활용안내서 파서(미구현)")
                return
            else:
                # 표준계약서 파싱
                try:
                    parser = StandardContractParser()
                    parser.parse(file_path, self.extracted_path)
                    logger.info(f"   파싱 완료")
                except Exception as e:
                    logger.error(f"   파싱 실패: {e}")
    
    def _run_chunking(self, filename):
        logger.info("  === 2단계: 청킹 시작 ===")
        logger.info(f"  입력: {self.extracted_path}")
        logger.info(f"  출력: {self.chunked_path}")
        
        # TODO: 청킹 로직 구현
        # from ingestion.processors.chunker import TextChunker
        
        if filename == 'all':
            pattern = "*.json"
            files = list(self.extracted_path.glob(pattern))
            logger.info(f"  처리할 파일: {len(files)}개")
            for file in files:
                is_guidebook = self._is_guidebook(file.name)
                chunker_type = "활용안내서 청커" if is_guidebook else "표준계약서 청커"
                logger.info(f"    - {file.name} ({chunker_type})")
                # TODO: 청킹 전략 선택
        else:
            file_path = self.extracted_path / filename
            if not file_path.exists():
                logger.error(f"   파일을 찾을 수 없습니다: {filename}")
                return
            
            is_guidebook = self._is_guidebook(filename)
            chunker_type = "활용안내서 청커" if is_guidebook else "표준계약서 청커"
            logger.info(f"  처리할 파일: {filename}")
            logger.info(f"  사용 청커: {chunker_type}")
            
            # TODO: 청킹 전략 선택
        
        # TODO: 청킹 로직
        pass
    
    def _run_embedding(self, filename):
        """임베딩 + 인덱싱 실행"""
        logger.info(" === 3단계: 임베딩 시작 ===")
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
        
        logger.info("🔍 === 4단계: 인덱싱 시작 ===")
        logger.info(f"  출력: {self.index_path}")
        
        # TODO: 인덱싱 로직 (Whoosh + FAISS)
        pass
    
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
        logger.info(f"\n\n원본 PDF ({self.source_path}):")
        logger.info(f"  총 {len(pdf_files)}개 파일")
        if '--detail' in arg:
            for f in pdf_files:
                logger.info(f"    - {f.name}")
        
        # extracted_documents
        json_files = list(self.extracted_path.glob("*.json")) if self.extracted_path.exists() else []
        logger.info(f"\n\n파싱 결과 ({self.extracted_path}):")
        logger.info(f"  총 {len(json_files)}개 파일")
        if '--detail' in arg:
            for f in json_files:
                logger.info(f"    - {f.name}")
        
        # chunked_documents
        jsonl_files = list(self.chunked_path.glob("*.jsonl")) if self.chunked_path.exists() else []
        logger.info(f"\n\n청킹 결과 ({self.chunked_path}):")
        logger.info(f"  총 {len(jsonl_files)}개 파일")
        if '--detail' in arg:
            for f in jsonl_files:
                logger.info(f"    - {f.name}")
        
        # search_indexes
        has_whoosh = (self.index_path / "whoosh").exists()
        has_faiss = (self.index_path / "faiss").exists()
        logger.info(f"\n\n검색 인덱스 ({self.index_path}):")
        logger.info(f"  Whoosh: {'✅' if has_whoosh else '❌'}")
        logger.info(f"  FAISS: {'✅' if has_faiss else '❌'}")
    
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
