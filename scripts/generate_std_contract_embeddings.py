#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
표준 계약서 임베딩 생성 및 저장 스크립트

사용법:
    python scripts/generate_std_contract_embeddings.py
"""

import sys
import json
import numpy as np
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.clause_verification.node_1_clause_matching.embedding_service import EmbeddingService

def main():
    print("=" * 80)
    print("표준 계약서 임베딩 생성 시작")
    print("=" * 80)
    
    # 경로 설정
    json_path = project_root / "data/chunked_documents/provide_std_contract_chunks.json"
    output_dir = project_root / "data/embeddings"
    
    # 디렉토리 생성 (이미 있으면 무시)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        pass  # 이미 존재하면 무시
    
    embeddings_path = output_dir / "provide_std_contract_chunks_embeddings.npy"
    metadata_path = output_dir / "provide_std_contract_chunks_metadata.json"
    
    # JSON 로드
    print(f"\n1. JSON 로드: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        clauses = json.load(f)
    print(f"   총 {len(clauses)}개 조문 로드")
    
    # 임베딩 서비스 초기화
    print("\n2. 임베딩 서비스 초기화")
    embedding_service = EmbeddingService()
    
    # 임베딩 생성
    print("\n3. 임베딩 생성 중...")
    texts = [clause["text_norm"] for clause in clauses]
    embeddings_list = embedding_service.embed_batch(texts)
    
    # numpy 배열로 변환
    embeddings_array = np.array([emb for emb in embeddings_list if emb is not None], dtype=np.float32)
    print(f"   생성된 임베딩: {embeddings_array.shape}")
    
    # 임베딩 저장
    print(f"\n4. 임베딩 저장: {embeddings_path}")
    np.save(str(embeddings_path), embeddings_array)
    
    # 메타데이터 저장
    print(f"5. 메타데이터 저장: {metadata_path}")
    metadata = {
        "version": "1.0",
        "created_at": datetime.now().isoformat(),
        "source_file": "provide_std_contract_chunks.json",
        "embedding_model": "text-embedding-3-large",
        "embedding_dimension": embeddings_array.shape[1],
        "total_clauses": len(clauses),
        "clause_ids": [clause["id"] for clause in clauses]
    }
    
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 80)
    print("✅ 임베딩 생성 완료!")
    print("=" * 80)
    print(f"임베딩 파일: {embeddings_path}")
    print(f"메타데이터: {metadata_path}")
    print(f"파일 크기: {embeddings_path.stat().st_size / 1024 / 1024:.2f} MB")

if __name__ == "__main__":
    main()
