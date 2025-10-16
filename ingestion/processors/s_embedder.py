"""
간이 임베더 (Simple Embedder)
조/별지 단위로 청킹하고 OpenAI 임베딩을 생성하여 FAISS에 저장
"""

import json
import logging
import pickle
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import faiss
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class SimpleEmbedder:
    """
    간이 임베더 클래스
    structured.json 파일을 읽어서 조/별지 단위로 청킹하고
    Azure OpenAI 임베딩을 생성하여 FAISS 인덱스로 저장
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
    
    def process_file(self, input_path: Path, output_dir: Path) -> bool:
        """
        structured.json 파일을 처리하여 임베딩 생성 및 저장
        
        Args:
            input_path: 입력 structured.json 파일 경로
            output_dir: FAISS 인덱스 출력 디렉토리
            
        Returns:
            성공 여부
        """
        try:
            # 1. 파일 읽기
            logger.info(f"  파일 읽기: {input_path.name}")
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'articles' not in data:
                logger.error("   [ERROR] 'articles' 키가 없습니다")
                return False
            
            articles = data['articles']
            logger.info(f"  총 {len(articles)}개 항목 (조/별지)")
            
            # 2. 청킹
            logger.info("\n  [1/3] 청킹 중...")
            chunks = self.chunk_articles(articles, input_path.name)
            logger.info(f"    생성된 청크 수: {len(chunks)}")
            
            if not chunks:
                logger.error("   [ERROR] 생성된 청크가 없습니다")
                return False
            
            # 3. 임베딩 생성
            logger.info("\n  [2/3] 임베딩 생성 중...")
            embeddings = self.create_embeddings(chunks)
            
            # None이 아닌 임베딩만 필터링
            valid_indices = [i for i, emb in enumerate(embeddings) if emb is not None]
            valid_chunks = [chunks[i] for i in valid_indices]
            valid_embeddings = [embeddings[i] for i in valid_indices]
            
            logger.info(f"    성공한 임베딩 수: {len(valid_embeddings)}")
            
            if not valid_embeddings:
                logger.error("   [ERROR] 생성된 임베딩이 없습니다")
                return False
            
            # 4. FAISS 인덱스 저장
            logger.info("\n  [3/3] FAISS 인덱스 생성 중...")
            self.save_to_faiss(valid_embeddings, valid_chunks, input_path.name, output_dir)
            
            logger.info("\n     청킹 및 임베딩 완료")
            return True
            
        except Exception as e:
            logger.error(f"   [ERROR] 처리 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def chunk_articles(self, articles: List[Dict], source_filename: str) -> List[Dict]:
        """
        조/별지 리스트를 청크로 변환
        
        Args:
            articles: 조/별지 딕셔너리 리스트
            source_filename: 원본 파일명
            
        Returns:
            청크 리스트
        """
        chunks = []
        
        for article in articles:
            chunk_text = self.extract_article_text(article)
            if chunk_text.strip():
                chunk = {
                    'type': article.get('type', ''),
                    'number': article.get('number', ''),
                    'title': article.get('text') or article.get('title', ''),
                    'content': chunk_text,
                    'metadata': {
                        'source_file': source_filename,
                        'article_type': article.get('type', ''),
                        'article_number': article.get('number', '')
                    }
                }
                chunks.append(chunk)
        
        return chunks
    
    def extract_article_text(self, article: Dict) -> str:
        """
        조 또는 별지 항목에서 모든 텍스트를 추출
        하위 항목을 재귀적으로 순회하며 text와 표 데이터를 추출
        
        Args:
            article: 조 또는 별지 딕셔너리
            
        Returns:
            추출된 텍스트 (개행문자 제거됨)
        """
        texts = []
        
        # 제목 추가
        if 'text' in article:
            texts.append(article['text'])
        elif 'title' in article:
            texts.append(article['title'])
        
        # content 항목들 처리
        if 'content' in article and isinstance(article['content'], list):
            for item in article['content']:
                extracted = self.extract_content_text(item)
                if extracted:
                    texts.append(extracted)
        
        # 개행문자 제거하고 공백으로 연결
        full_text = ' '.join(texts)
        # 여러 공백을 하나로 축소
        full_text = ' '.join(full_text.split())
        
        return full_text
    
    def extract_content_text(self, item: Dict) -> str:
        """
        content 항목에서 텍스트를 재귀적으로 추출
        
        Args:
            item: content 항목 딕셔너리
            
        Returns:
            추출된 텍스트
        """
        texts = []
        
        item_type = item.get('type', '')
        
        # 표 타입인 경우
        if item_type == '표':
            table_text = self.extract_table_text(item)
            if table_text:
                texts.append(table_text)
        
        # 일반 텍스트인 경우
        elif 'text' in item:
            texts.append(item['text'])
        
        # 하위 content가 있으면 재귀적으로 처리
        if 'content' in item and isinstance(item['content'], list):
            for sub_item in item['content']:
                extracted = self.extract_content_text(sub_item)
                if extracted:
                    texts.append(extracted)
        
        return ' '.join(texts)
    
    def extract_table_text(self, table: Dict) -> str:
        """
        표 데이터에서 텍스트 추출
        data 리스트의 각 항목에서 key:value 형태로 추출
        
        Args:
            table: 표 딕셔너리
            
        Returns:
            추출된 텍스트
        """
        texts = []
        
        # data가 있는 경우
        if 'data' in table and isinstance(table['data'], list):
            for row in table['data']:
                if isinstance(row, dict):
                    for key, value in row.items():
                        # key와 value를 모두 포함
                        if value:  # 빈 값이 아닌 경우만
                            texts.append(f"{key}:{value}")
        
        return ' '.join(texts)
    
    def create_embeddings(self, chunks: List[Dict]) -> List[Any]:
        """
        청크 리스트에 대해 임베딩 생성
        
        Args:
            chunks: 청크 리스트
            
        Returns:
            임베딩 리스트 (실패한 경우 None 포함)
        """
        embeddings = []
        
        for i, chunk in enumerate(chunks):
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=chunk['content']
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
        FAISS 인덱스에 임베딩과 메타데이터 저장
        
        Args:
            embeddings: 임베딩 벡터 리스트
            chunks: 청크 데이터 리스트
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
        base_name = source_filename.replace('_structured.json', '')
        
        # FAISS 인덱스 저장
        index_path = output_dir / f"{base_name}.faiss"
        faiss.write_index(index, str(index_path))
        logger.info(f"    FAISS 인덱스 저장: {index_path}")
        
        # 메타데이터 저장 (JSON)
        metadata_path = output_dir / f"{base_name}_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
        logger.info(f"    메타데이터 저장: {metadata_path}")
        
        # 청크 텍스트도 별도로 저장 (검색 결과 표시용)
        chunks_path = output_dir / f"{base_name}_chunks.pkl"
        with open(chunks_path, 'wb') as f:
            pickle.dump(chunks, f)
        logger.info(f"    청크 데이터 저장: {chunks_path}")

