
# 임베딩 생성 모듈
from typing import List, Dict, Any
import numpy as np
import json
import logging
from pathlib import Path
import faiss
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class TextEmbedder:
    """
    텍스트 임베딩 생성 클래스
    chunks.json 파일을 읽어서 text_norm을 임베딩하고 FAISS 인덱스로 저장
    """

    def __init__(
        self,
        api_key: str,
        azure_endpoint: str,
        model: str = "text-embedding-3-large",
        api_version: str = "2024-02-01"
    ):
        """
        Args:
            api_key: Azure OpenAI API 키
            azure_endpoint: Azure OpenAI 엔드포인트
            model: 사용할 임베딩 모델 (Azure deployment name)
            api_version: Azure OpenAI API 버전
        """
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=azure_endpoint
        )
        self.model = model

    def process_file(self, input_path: Path, faiss_output_dir: Path, whoosh_output_dir: Path) -> bool:
        """
        chunks.json 파일을 처리하여 FAISS 및 Whoosh 인덱스 생성

        Args:
            input_path: 입력 chunks.json 파일 경로
            faiss_output_dir: FAISS 인덱스 출력 디렉토리
            whoosh_output_dir: Whoosh 인덱스 출력 디렉토리

        Returns:
            성공 여부
        """
        try:
            # 1. 파일 읽기
            logger.info(f"  파일 읽기: {input_path.name}")
            with open(input_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)

            if not isinstance(chunks, list):
                logger.error("   [ERROR] chunks는 리스트 형식이어야 합니다")
                return False

            logger.info(f"  총 {len(chunks)}개 청크")

            if not chunks:
                logger.error("   [ERROR] 청크가 없습니다")
                return False

            # 2. 임베딩 생성
            logger.info("\n  [1/3] 임베딩 생성 중...")
            embeddings = self.create_embeddings(chunks)

            # None이 아닌 임베딩만 필터링
            valid_indices = [i for i, emb in enumerate(embeddings) if emb is not None]
            valid_chunks = [chunks[i] for i in valid_indices]
            valid_embeddings = [embeddings[i] for i in valid_indices]

            logger.info(f"    성공한 임베딩 수: {len(valid_embeddings)}")

            if not valid_embeddings:
                logger.error("   [ERROR] 생성된 임베딩이 없습니다")
                return False

            # 3. FAISS 인덱스 저장
            logger.info("\n  [2/3] FAISS 인덱스 생성 중...")
            self.save_to_faiss(valid_embeddings, valid_chunks, input_path.name, faiss_output_dir)

            # 4. Whoosh 인덱스 생성
            logger.info("\n  [3/3] Whoosh 인덱스 생성 중...")
            self.save_to_whoosh(chunks, input_path.name, whoosh_output_dir)

            logger.info("\n     임베딩 및 인덱싱 완료")
            return True

        except Exception as e:
            logger.error(f"   [ERROR] 처리 실패: {e}")
            import traceback
            traceback.print_exc()
            return False

    def create_embeddings(self, chunks: List[Dict]) -> List[Any]:
        """
        청크 리스트에 대해 임베딩 생성
        각 청크의 text_norm 필드를 사용

        Args:
            chunks: 청크 리스트

        Returns:
            임베딩 리스트 (실패한 경우 None 포함)
        """
        embeddings = []

        for i, chunk in enumerate(chunks):
            try:
                # text_norm 필드 사용
                text_norm = chunk.get('text_norm', '')
                if not text_norm or not text_norm.strip():
                    logger.warning(f"    [WARNING] 청크 {i}의 text_norm이 비어있습니다")
                    embeddings.append(None)
                    continue

                response = self.client.embeddings.create(
                    model=self.model,
                    input=text_norm
                )
                embedding = response.data[0].embedding
                embeddings.append(embedding)

                if (i + 1) % 10 == 0:
                    logger.info(f"    진행: {i + 1}/{len(chunks)}")

            except Exception as e:
                logger.error(f"    [ERROR] 청크 {i} 임베딩 실패: {e}")
                embeddings.append(None)

        return embeddings

    def save_to_faiss(
        self,
        embeddings: List[List[float]],
        chunks: List[Dict],
        source_filename: str,
        output_dir: Path
    ):
        """
        FAISS 인덱스 저장

        Args:
            embeddings: 임베딩 벡터 리스트
            chunks: 청크 데이터 리스트 (사용하지 않음, 호환성 유지)
            source_filename: 원본 파일명
            output_dir: 출력 디렉토리
        """
        # 출력 디렉토리 생성
        output_dir.mkdir(parents=True, exist_ok=True)

        # 임베딩을 numpy 배열로 변환
        embeddings_array = np.array(embeddings, dtype=np.float32)
        dimension = embeddings_array.shape[1]

        logger.info(f"    임베딩 차원: {dimension}")
        logger.info(f"    벡터 수: {len(embeddings_array)}")

        # FAISS 인덱스 생성 (L2 거리 사용)
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings_array)

        # 파일명에서 확장자 제거
        base_name = source_filename.replace('_chunks.json', '')

        # FAISS 인덱스 저장
        index_path = output_dir / f"{base_name}.faiss"
        faiss.write_index(index, str(index_path))
        logger.info(f"    FAISS 인덱스 저장: {index_path}")

    def save_to_whoosh(
        self,
        chunks: List[Dict],
        source_filename: str,
        output_dir: Path
    ):
        """
        Whoosh 인덱스 저장

        Args:
            chunks: 청크 데이터 리스트
            source_filename: 원본 파일명
            output_dir: 출력 디렉토리
        """
        from ingestion.indexers.whoosh_indexer import WhooshIndexer

        # 파일명에서 확장자 제거
        base_name = source_filename.replace('_chunks.json', '')

        # Whoosh 인덱스 디렉토리 (파일별로 별도 디렉토리)
        whoosh_index_dir = output_dir / base_name

        # WhooshIndexer 초기화 및 빌드
        indexer = WhooshIndexer(whoosh_index_dir)
        indexer.build(chunks)

        logger.info(f"    Whoosh 인덱스 저장: {whoosh_index_dir}")

