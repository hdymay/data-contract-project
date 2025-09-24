"""
데이터 준비 스크립트
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def prepare_data_directories():
    """데이터 디렉토리 준비"""
    directories = [
        "data/standard_contracts/data_provision",
        "data/standard_contracts/data_creation", 
        "data/standard_contracts/data_processing",
        "data/standard_contracts/data_brokerage_provider",
        "data/standard_contracts/data_brokerage_user",
        "data/guide",
        "data/embeddings/faiss_index",
        "data/embeddings/whoosh_index",
        "data/database",
        "data/uploads",
        "data/reports",
        "logs"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"디렉토리 생성: {directory}")

def create_sample_files():
    """샘플 파일 생성"""
    # TODO: 기타 샘플 파일 생성 로직
    pass

if __name__ == "__main__":
    print("데이터 디렉토리를 준비합니다...")
    prepare_data_directories()
    create_sample_files()
    print("데이터 준비가 완료되었습니다!")
