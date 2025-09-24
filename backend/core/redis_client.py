"""
Redis 클라이언트
"""
import redis
from core.config import settings

class RedisClient:
    """Redis 클라이언트"""
    
    def __init__(self):
        self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    
    def get(self, key: str):
        """값 조회"""
        return self.client.get(key)
    
    def set(self, key: str, value: str, ex: int = None):
        """값 설정"""
        return self.client.set(key, value, ex=ex)
    
    def delete(self, key: str):
        """값 삭제"""
        return self.client.delete(key)
    
    def exists(self, key: str):
        """키 존재 여부"""
        return self.client.exists(key)

# 전역 Redis 클라이언트 인스턴스
redis_client = RedisClient()
