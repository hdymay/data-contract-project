"""
사용자 계약서 처리 통합 서비스
파싱 → 청킹 → 임베딩 파이프라인
"""

import logging
from pathlib import Path
from typing import Dict, Any, List
import json

logger = logging.getLogger(__name__)


class UserContractProcessor:
    """
    사용자 계약서 처리 파이프라인
    1. 파싱 (user_contract_parser)
    2. 청킹 (user_contract_chunker)
    3. 임베딩 (user_contract_embedder)
    """
    
    def __init__(self, parser, chunker, embedder):
        """
        초기화
        
        Args:
            parser: UserContractParser 인스턴스
            chunker: UserContractChunker 인스턴스
            embedder: UserContractEmbedder 인스턴스
        """
        self.parser = parser
        self.chunker = chunker
        self.embedder = embedder
    
    def process_contract(
        self,
        docx_path: Path,
        output_dir: Path,
        contract_id: str
    ) -> Dict[str, Any]:
        """
        사용자 계약서 전체 처리 파이프라인
        
        Args:
            docx_path: DOCX 파일 경로
            output_dir: 출력 디렉토리
            contract_id: 계약서 ID
            
        Returns:
            {
                "success": bool,
                "structured_path": Path,
                "chunks_path": Path,
                "embeddings_path": Path,
                "chunks": List[Dict],
                "metadata": Dict
            }
        """
        try:
            logger.info(f"사용자 계약서 처리 시작: {contract_id}")
            
            # 1. 파싱
            logger.info("1/3: 파싱 중...")
            parse_result = self.parser.parse_to_dict(docx_path)
            
            if not parse_result['success']:
                return {
                    "success": False,
                    "error": parse_result.get('error', 'Unknown parsing error'),
                    "stage": "parsing"
                }
            
            structured_data = parse_result['structured_data']
            
            # structured.json 저장
            structured_path = output_dir / f"{contract_id}_structured.json"
            with open(structured_path, 'w', encoding='utf-8') as f:
                json.dump(structured_data, f, ensure_ascii=False, indent=2)
            
            # 2. 청킹
            logger.info("2/3: 청킹 중...")
            chunks = self.chunker.chunk_structured_data(
                structured_data,
                source_filename=docx_path.name
            )
            
            # chunks.json 저장
            chunks_path = output_dir / f"{contract_id}_chunks.json"
            with open(chunks_path, 'w', encoding='utf-8') as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
            
            # 3. 임베딩
            logger.info("3/3: 임베딩 생성 중...")
            chunks_with_embeddings = self.embedder.embed_chunks(chunks)
            
            # 임베딩 저장
            embeddings_path = output_dir / f"{contract_id}_embeddings"
            self.embedder.save_embeddings(chunks_with_embeddings, str(embeddings_path))
            
            logger.info(f"처리 완료: {len(chunks)}개 청크 생성")
            
            # 메타데이터 안전하게 추출
            parsed_meta = parse_result.get('parsed_metadata', {})
            total_articles = parsed_meta.get('total_articles', len(structured_data.get('articles', [])))
            
            return {
                "success": True,
                "structured_path": str(structured_path),
                "chunks_path": str(chunks_path),
                "embeddings_path": str(embeddings_path),
                "chunks": chunks_with_embeddings,
                "structured_data": structured_data,
                "metadata": {
                    "total_chunks": len(chunks),
                    "total_articles": total_articles,
                    "recognized_articles": total_articles,
                    "confidence": parsed_meta.get('confidence', 1.0)
                }
            }
            
        except Exception as e:
            logger.error(f"처리 실패: {contract_id} - {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "error": str(e),
                "stage": "unknown"
            }
