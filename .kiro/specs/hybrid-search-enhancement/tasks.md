# Implementation Plan

- [x] 1. Ingestion Container - 이중 임베딩 및 인덱스 생성




  - TextEmbedder 수정하여 text_norm과 title을 각각 임베딩
  - 두 개의 FAISS 인덱스 파일 생성 (_text.faiss, _title.faiss)
  - 기존 Whoosh 인덱스 생성 로직 유지 (이미 멀티필드 지원)
  - 기존 chunks.json 파일 형식 호환성 유지
  - _Requirements: 2.1, 2.2, 2.3, 5.2, 5.3_

- [x] 1.1 TextEmbedder.create_dual_embeddings() 메서드 구현


  - 각 청크의 text_norm과 title을 각각 임베딩
  - 빈 문자열 처리 로직 추가
  - 배치 처리로 API 호출 최적화
  - 에러 발생 시 None 반환하여 기존 로직과 호환
  - _Requirements: 2.1_

- [x] 1.2 TextEmbedder.save_dual_faiss_indexes() 메서드 구현


  - text_norm 임베딩을 {base_name}_text.faiss로 저장
  - title 임베딩을 {base_name}_title.faiss로 저장
  - 기존 단일 인덱스 파일명과 충돌 방지
  - 인덱스 저장 실패 시 명확한 에러 메시지
  - _Requirements: 2.2_

- [x] 1.3 TextEmbedder.process_file() 메서드 수정


  - create_embeddings() 대신 create_dual_embeddings() 호출
  - save_to_faiss() 대신 save_dual_faiss_indexes() 호출
  - Whoosh 인덱스 생성 로직은 그대로 유지
  - 기존 메서드 시그니처 유지 (호환성)
  - _Requirements: 2.2, 5.2_

- [x] 2. Backend - KnowledgeBaseLoader 수정




  - 두 개의 FAISS 인덱스 로드 지원
  - 기존 단일 인덱스 감지 및 에러 처리
  - 캐싱 로직 업데이트 (두 개의 인덱스)
  - 기존 load_chunks(), load_whoosh_index() 메서드 유지
  - _Requirements: 2.2, 5.1_

- [x] 2.1 KnowledgeBaseLoader.load_faiss_indexes() 메서드 구현


  - {contract_type}_text.faiss와 {contract_type}_title.faiss 로드
  - 두 파일 모두 존재하는지 확인
  - 하나만 존재하면 명확한 에러 메시지
  - 기존 load_faiss_index() 메서드는 deprecated 처리
  - 캐시 키를 (contract_type, 'text'), (contract_type, 'title')로 분리
  - _Requirements: 2.2, 5.1_



- [x] 2.2 KnowledgeBaseLoader 기존 인덱스 감지 로직 추가


  - 기존 단일 인덱스 파일 존재 확인
  - 새로운 이중 인덱스 파일 존재 확인
  - 불일치 시 명확한 에러 메시지 및 해결 방법 안내
  - verify_knowledge_base() 메서드에 검증 로직 추가
  - _Requirements: 5.1_

- [x] 3. Backend - HybridSearcher 수정




  - 제목과 본문 쿼리를 분리하여 처리
  - 두 개의 FAISS 인덱스 사용
  - Whoosh 검색 시 두 개의 쿼리 사용
  - 청크별 가중합 계산 (본문:제목 = 7:3)
  - 기존 search() 메서드 시그니처 변경 (하위 호환성 주의)
  - _Requirements: 1.1, 1.2, 1.3, 2.4, 2.5, 2.6, 4.2_

- [x] 3.1 HybridSearcher 속성 추가


  - text_weight, title_weight 속성 추가 (기본값 0.7, 0.3)
  - faiss_index_text, faiss_index_title 속성 추가
  - 기존 faiss_index 속성은 deprecated 처리
  - _Requirements: 4.2, 4.3_

- [x] 3.2 HybridSearcher.load_indexes() 메서드 수정


  - 두 개의 FAISS 인덱스를 인자로 받도록 변경
  - 기존 단일 인덱스 인자는 에러 발생
  - chunks, whoosh_indexer 인자는 그대로 유지
  - _Requirements: 2.2_

- [x] 3.3 HybridSearcher.dense_search() 메서드 수정


  - text_query, title_query 두 개의 인자로 변경
  - text_query를 text_norm 인덱스에서 검색
  - title_query를 title 인덱스에서 검색
  - 동일 청크 ID에 대해 가중합 계산
  - 제목 또는 본문 검색 결과가 없을 때 처리
  - 결과에 text_score, title_score 필드 추가
  - _Requirements: 2.4, 2.5, 2.6_

- [x] 3.4 HybridSearcher.sparse_search() 메서드 수정


  - text_query, title_query 두 개의 인자로 변경
  - WhooshSearcher.search_with_field_weights() 호출
  - 결과에 text_score, title_score 필드 추가
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 3.5 HybridSearcher.search() 메서드 수정


  - text_query, title_query 두 개의 인자로 변경
  - dense_search(), sparse_search() 호출 시 두 쿼리 전달
  - 기존 하이브리드 융합 로직 유지 (85:15)
  - 로그에 적용된 가중치 기록
  - _Requirements: 1.5, 4.6_

- [x] 3.6 HybridSearcher.set_field_weights() 메서드 구현


  - text_weight, title_weight 설정
  - 가중치 합이 1.0인지 검증
  - 범위 검증 (0~1)
  - _Requirements: 4.1, 4.2, 4.7_

- [x] 4. Backend - WhooshSearcher 수정





  - 제목과 본문 쿼리를 분리하여 검색
  - 각 필드별 점수를 가중합
  - 기존 search() 메서드는 유지 (하위 호환성)
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 4.1 WhooshSearcher.search_with_field_weights() 메서드 구현


  - text_query를 text_norm 필드에서 검색
  - title_query를 title 필드에서 검색
  - 두 검색 결과를 청크 ID로 매핑
  - 동일 청크에 대해 가중합 계산
  - 제목 또는 본문 검색 결과가 없을 때 처리
  - 결과에 text_score, title_score 필드 추가
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [-] 5. Backend - ArticleMatcher 수정



  - 제목과 본문 쿼리를 분리하여 생성
  - top-5 → top-1 방식으로 변경
  - 조별 평균 계산 로직 제거
  - 기존 find_matching_article() 반환 형식 유지
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_



- [ ] 5.1 ArticleMatcher._build_search_queries() 메서드 구현
  - 기존 _build_search_query() 대체
  - (text_query, title_query) 튜플 반환
  - text_query = sub_item (정규화된 본문)
  - title_query = article_title (조 제목)


  - _Requirements: 3.1_

- [ ] 5.2 ArticleMatcher._get_or_create_searcher() 메서드 수정
  - KnowledgeBaseLoader.load_faiss_indexes() 호출
  - 두 개의 FAISS 인덱스 전달

  - HybridSearcher.load_indexes() 호출 시 두 인덱스 전달

  - 에러 처리 강화
  - _Requirements: 2.2_

- [-] 5.3 ArticleMatcher._hybrid_search() 메서드 수정

  - text_query, title_query 두 개의 인자로 변경
  - HybridSearcher.search() 호출 시 두 쿼리 전달
  - top_k 파라미터 유지
  - _Requirements: 3.1_

- [x] 5.4 ArticleMatcher._search_with_sub_items() 메서드 수정

  - _build_search_queries() 호출하여 두 쿼리 생성
  - _hybrid_search() 호출 시 두 쿼리 전달
  - top_k를 5에서 1로 변경
  - 기존 반환 형식 유지 (article_scores, sub_item_results)
  - _Requirements: 3.1, 3.2_


- [x] 5.5 ArticleMatcher._select_best_article_from_chunks() 메서드 수정

  - top-5 평균 계산 로직 제거
  - 각 조의 최고 점수 청크를 대표 점수로 사용
  - 조별 그룹화 로직 유지
  - 반환 형식 유지 (parent_id, title, score, chunks)
  - _Requirements: 3.2, 3.3_

- [x] 5.6 ArticleMatcher._aggregate_sub_item_results() 메서드 검증



  - 기존 로직이 top-1 결과와 호환되는지 확인
  - 정렬 로직 유지 (하위항목 개수 → 유사도 → 조 번호)
  - 반환 형식 유지
  - _Requirements: 3.3, 3.4_

- [x] 6. Frontend - Streamlit UI 검색 설정 추가




  - 사이드바에 검색 설정 섹션 추가
  - 본문:제목 가중치 슬라이더 (기본값 0.7:0.3)
  - 시멘틱:키워드 가중치 슬라이더 (기본값 0.85:0.15)
  - 세션 상태에 가중치 저장
  - API 호출 시 가중치 전달
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 6.1 Streamlit UI 사이드바 검색 설정 섹션 추가


  - st.sidebar.header("검색 설정") 추가
  - 본문:제목 가중치 슬라이더 구현
  - 시멘틱:키워드 가중치 슬라이더 구현
  - 가중치 비율 표시 (예: "본문: 70%, 제목: 30%")
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 6.2 Streamlit 세션 상태 관리


  - st.session_state에 text_weight, title_weight 저장
  - st.session_state에 dense_weight 저장
  - 초기값 설정 (0.7, 0.3, 0.85)
  - 슬라이더 변경 시 세션 상태 업데이트
  - _Requirements: 4.5_

- [x] 6.3 FastAPI 엔드포인트 수정


  - /api/consistency/analyze 엔드포인트에 가중치 파라미터 추가
  - text_weight, title_weight, dense_weight 받기
  - HybridSearcher 초기화 시 가중치 전달
  - 기본값 설정 (하위 호환성)
  - _Requirements: 4.5_


- [x] 6.4 Streamlit API 호출 수정

  - requests.post() 호출 시 가중치 파라미터 전달
  - 세션 상태에서 가중치 읽기
  - 에러 처리 (가중치 검증 실패 시)
  - _Requirements: 4.5_

- [ ]* 7. 통합 테스트 및 검증 (사용자가 직접 수행)
  - Ingestion Container 실행하여 새로운 인덱스 생성
  - Backend에서 인덱스 로드 및 검색 테스트
  - UI에서 가중치 조정 및 검색 테스트
  - 기존 코드와의 호환성 검증
  - 성능 측정 (검색 속도, 메모리 사용량)
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ]* 7.1 Ingestion Container 테스트
  - docker-compose로 Ingestion Container 실행
  - 5종 표준계약서 인덱스 생성 확인
  - _text.faiss, _title.faiss 파일 생성 확인
  - Whoosh 인덱스 정상 생성 확인
  - 로그에서 에러 없는지 확인
  - _Requirements: 5.2_

- [ ]* 7.2 Backend 인덱스 로드 테스트
  - KnowledgeBaseLoader.load_faiss_indexes() 호출
  - 두 개의 인덱스 정상 로드 확인
  - 기존 단일 인덱스 감지 시 에러 메시지 확인
  - 캐싱 동작 확인
  - _Requirements: 5.1, 5.4_

- [ ]* 7.3 Backend 검색 테스트
  - HybridSearcher로 제목/본문 분리 검색 수행
  - 검색 결과에 text_score, title_score 포함 확인
  - 가중합 계산 정확성 검증
  - 제목 또는 본문 검색 실패 시 처리 확인
  - _Requirements: 5.4_

- [ ]* 7.4 ArticleMatcher 통합 테스트
  - 사용자 계약서 조항으로 매칭 수행
  - top-1 선택 로직 동작 확인
  - 조별 그룹화 및 정렬 확인
  - 기존 A3 노드와 호환성 확인
  - _Requirements: 5.4_

- [ ]* 7.5 UI 통합 테스트
  - Streamlit UI에서 가중치 슬라이더 동작 확인
  - 가중치 변경 후 검색 수행
  - 검색 결과 변화 확인
  - 에러 처리 확인
  - _Requirements: 5.4_

- [ ]* 7.6 성능 측정
  - 인덱스 생성 시간 측정
  - 검색 응답 시간 측정 (하위항목 5개 기준)
  - 메모리 사용량 측정
  - 기존 시스템과 비교
  - _Requirements: 5.4_

- [ ] 8. 문서 업데이트
  - README 업데이트 (새로운 인덱스 구조 설명)
  - 환경 변수 문서 업데이트
  - API 문서 업데이트 (가중치 파라미터)
  - _Requirements: 5.1, 5.2_

- [ ] 8.1 README.md 또는 관련 문서 업데이트
  - 하이브리드 검색 로직 설명 추가
  - 인덱스 구조 변경 사항 설명 (_text.faiss, _title.faiss)
  - Ingestion Container 실행 방법 업데이트
  - 가중치 조정 기능 설명 (UI 슬라이더)
  - 기존 인덱스 재생성 필요성 안내
  - _Requirements: 5.1, 5.2_
