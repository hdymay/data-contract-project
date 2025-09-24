"""
임베딩 서비스
"""
from typing import List, Dict, Any
import openai
from core.config import settings

class EmbeddingService:
    """임베딩 서비스"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "text-embedding-3-large"
    
    async def embed_text(self, text: str) -> List[float]:
        """텍스트 임베딩"""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise Exception(f"임베딩 생성 실패: {e}")
    
    async def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """문서들 임베딩"""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=documents
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            raise Exception(f"문서 임베딩 실패: {e}")
    
    async def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """청크들 임베딩"""
        try:
            texts = [chunk["text"] for chunk in chunks]
            embeddings = await self.embed_documents(texts)
            
            for i, chunk in enumerate(chunks):
                chunk["embedding"] = embeddings[i]
            
            return chunks
        except Exception as e:
            raise Exception(f"청크 임베딩 실패: {e}")
