"""
조/별지 단위 청커 테스트 스크립트
"""

from pathlib import Path
from processors.art_chunker import ArticleChunker


def main():
    # 청커 초기화
    chunker = ArticleChunker()
    
    # 입력 파일
    input_path = Path("data/extracted_documents/provide_std_contract_structured.json")
    
    # 청킹
    print(f"청킹 시작: {input_path.name}")
    chunks = chunker.chunk_file(input_path)
    print(f"생성된 청크 수: {len(chunks)}")
    
    # 첫 번째 청크 출력 (조)
    if chunks:
        print("\n=== 첫 번째 청크 (조) ===")
        print(f"ID: {chunks[0]['id']}")
        print(f"Global ID: {chunks[0]['global_id']}")
        print(f"Title: {chunks[0]['title']}")
        print(f"Breadcrumb: {chunks[0]['breadcrumb']}")
        print(f"Text Raw (처음 100자): {chunks[0]['text_raw'][:100]}...")
        print(f"Text Norm (처음 100자): {chunks[0]['text_norm'][:100]}...")
        print(f"Anchors: {len(chunks[0]['anchors'])}개")
        if chunks[0]['anchors']:
            print(f"  첫 번째 anchor: {chunks[0]['anchors'][0]}")
    
    # 별지 청크 찾기
    exhibit_chunks = [c for c in chunks if c['unit_type'] == 'exhibit']
    if exhibit_chunks:
        print("\n=== 첫 번째 별지 청크 ===")
        ex = exhibit_chunks[0]
        print(f"ID: {ex['id']}")
        print(f"Global ID: {ex['global_id']}")
        print(f"Title: {ex['title']}")
        print(f"Breadcrumb: {ex['breadcrumb']}")
        print(f"Text Raw (처음 100자): {ex['text_raw'][:100]}...")
        print(f"Text Norm (처음 100자): {ex['text_norm'][:100]}...")
        print(f"Anchors: {len(ex['anchors'])}개")
        for i, anchor in enumerate(ex['anchors'][:3]):
            print(f"  Anchor {i+1}: {anchor}")
    
    # 결과 저장
    output_path = Path("data/chunked_documents/provide_std_contract_chunks.json")
    chunker.save_chunks(chunks, output_path)
    print(f"\n청크 저장 완료: {output_path}")
    
    # 통계
    article_count = len([c for c in chunks if c['unit_type'] == 'article'])
    exhibit_count = len([c for c in chunks if c['unit_type'] == 'exhibit'])
    print(f"\n=== 통계 ===")
    print(f"조 청크: {article_count}개")
    print(f"별지 청크: {exhibit_count}개")
    print(f"전체 청크: {len(chunks)}개")


if __name__ == "__main__":
    main()

