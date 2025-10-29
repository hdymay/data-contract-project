# Requirements Document

## Introduction

본 문서는 데이터 표준계약 검증 시스템의 하이브리드 검색 로직 고도화를 위한 요구사항을 정의합니다. 현재 Consistency Agent의 A3 노드에서 사용하는 FAISS + Whoosh 하이브리드 검색 방식을 개선하여, 제목(title)과 본문(text_norm)을 독립적으로 검색하고 가중합하는 방식으로 전환합니다.

## Glossary

- **System**: 데이터 표준계약 검증 시스템
- **Consistency Agent**: 계약서 정합성 검증을 수행하는 에이전트
- **A3 Node**: Consistency Agent 내 조항별 내용 분석을 수행하는 노드
- **FAISS**: Facebook AI Similarity Search, 벡터 유사도 검색 라이브러리
- **Whoosh**: Python 기반 BM25 키워드 검색 엔진
- **Hybrid Search**: FAISS와 Whoosh를 결합한 검색 방식
- **Chunk**: 계약서 조항의 하위 항목 단위 텍스트 조각
- **text_norm**: 청크의 정규화된 본문 텍스트
- **title**: 청크가 속한 조항의 제목
- **Ingestion Container**: 표준계약서를 파싱하고 인덱스를 생성하는 컨테이너
- **Knowledge Base**: 표준계약서 5종의 인덱스 및 청크 데이터
- **User Contract**: 사용자가 업로드한 검증 대상 계약서
- **Standard Contract**: 비교 기준이 되는 표준계약서

## Requirements

### Requirement 1

**User Story:** 개발자로서, Whoosh 검색 시 제목과 본문을 독립적으로 검색하고 가중합하여 더 정확한 매칭 결과를 얻고 싶습니다.

#### Acceptance Criteria

1. WHEN 사용자 계약서 조항을 검색할 때, THE System SHALL 사용자 조항의 제목과 본문을 분리하여 각각 독립적인 쿼리로 생성한다
2. WHEN Whoosh 검색을 수행할 때, THE System SHALL 제목 쿼리는 title 필드에만, 본문 쿼리는 text_norm 필드에만 검색한다
3. WHEN Whoosh 검색 결과를 취합할 때, THE System SHALL 동일 청크에 대한 제목 매칭 점수와 본문 매칭 점수를 본문:제목=7:3 비율로 가중합한다
4. WHEN 제목 또는 본문 검색 결과가 없을 때, THE System SHALL 존재하는 검색 결과만으로 점수를 계산한다
5. THE System SHALL Whoosh 검색 결과의 최종 점수를 0~1 범위로 정규화한다

### Requirement 2

**User Story:** 개발자로서, FAISS 검색 시 제목과 본문을 독립적으로 임베딩하고 검색하여 의미적 유사도를 더 정확하게 측정하고 싶습니다.

#### Acceptance Criteria

1. WHEN Ingestion Container가 인덱스를 생성할 때, THE System SHALL 각 청크의 text_norm과 title을 각각 임베딩하여 두 개의 벡터를 생성한다
2. WHEN FAISS 인덱스를 구축할 때, THE System SHALL text_norm 벡터와 title 벡터를 별도의 인덱스로 저장한다
3. WHEN 사용자 계약서 조항을 검색할 때, THE System SHALL 사용자 조항의 제목과 본문을 각각 임베딩하여 두 개의 쿼리 벡터를 생성한다
4. WHEN FAISS 검색을 수행할 때, THE System SHALL 본문 쿼리 벡터는 text_norm 인덱스에서, 제목 쿼리 벡터는 title 인덱스에서 검색한다
5. WHEN FAISS 검색 결과를 취합할 때, THE System SHALL 동일 청크에 대한 제목 유사도와 본문 유사도를 본문:제목=7:3 비율로 가중합한다
6. WHEN 제목 또는 본문 검색 결과가 없을 때, THE System SHALL 존재하는 검색 결과만으로 점수를 계산한다

### Requirement 3

**User Story:** 개발자로서, 하이브리드 검색 후 조 단위 취합 로직을 개선하여 불필요한 평균 계산을 제거하고 더 직관적인 결과를 얻고 싶습니다.

#### Acceptance Criteria

1. WHEN 하위항목별 검색이 완료되었을 때, THE System SHALL 각 하위항목에 대해 top-1 청크 결과만 선택한다
2. WHEN 동일 조에 속한 여러 청크가 검색되었을 때, THE System SHALL 해당 조의 최고 점수 청크를 대표 점수로 사용한다
3. THE System SHALL 조별 취합 시 하위항목 개수를 1순위, 대표 점수를 2순위, 조 번호를 3순위 정렬 기준으로 사용한다
4. THE System SHALL 각 하위항목의 top-1 결과를 조 단위로 그룹화하여 최종 매칭 조 목록을 생성한다
5. THE System SHALL 기존의 top-5 청크 검색 후 조별 평균 계산 방식을 제거한다

### Requirement 4

**User Story:** 사용자로서, 검색 가중합 비율(본문:제목, 시멘틱:키워드)을 UI에서 조정하여 검색 품질을 최적화하고 싶습니다.

#### Acceptance Criteria

1. THE System SHALL Streamlit UI에 본문:제목 가중합 비율 조정 슬라이더를 제공한다
2. THE System SHALL Streamlit UI에 시멘틱:키워드 가중합 비율 조정 슬라이더를 제공한다
3. THE System SHALL 본문:제목 가중합 비율의 기본값을 7:3으로 설정한다
4. THE System SHALL 시멘틱:키워드 가중합 비율의 기본값을 85:15로 설정한다
5. WHEN 사용자가 가중합 비율을 변경할 때, THE System SHALL 변경된 비율을 즉시 검색에 적용한다
6. THE System SHALL 검색 로그에 적용된 가중합 비율을 기록한다
7. THE System SHALL 각 가중합 비율의 합이 1.0이 되도록 검증한다

### Requirement 5

**User Story:** 개발자로서, 기존 시스템과의 호환성을 유지하면서 점진적으로 새로운 검색 로직을 적용하고 싶습니다.

#### Acceptance Criteria

1. THE System SHALL 기존 FAISS 인덱스 파일 형식과 호환되지 않는 경우 명확한 에러 메시지를 제공한다
2. THE System SHALL Ingestion Container 실행 시 새로운 형식의 인덱스를 생성한다
3. THE System SHALL 기존 Whoosh 인덱스 스키마와 호환성을 유지한다
4. THE System SHALL 검색 결과 데이터 구조가 기존 A3 노드 로직과 호환되도록 한다
