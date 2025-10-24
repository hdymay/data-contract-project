# Requirements Document

## Introduction

본 문서는 데이터 표준계약 검증 시스템의 전반적인 개선 및 미구현 기능 완성을 위한 요구사항을 정의합니다. 시스템은 5종의 데이터 표준계약서와 활용안내서를 기반으로 사용자 계약서를 검증하며, 핵심 원칙은 "맥락 기반 유연한 검증"입니다.

## Glossary

- **System**: 데이터 표준계약 검증 시스템
- **User Contract**: 사용자가 업로드한 검증 대상 계약서
- **Standard Contract**: 5종의 데이터 표준계약서 (제공형, 창출형, 가공형, 중개거래형 2종)
- **Guidebook**: 표준계약서 활용안내서
- **RAG**: Retrieval-Augmented Generation, 검색 증강 생성
- **Ingestion Pipeline**: 문서 파싱, 청킹, 임베딩, 인덱싱 파이프라인
- **Classification Agent**: 사용자 계약서 유형 분류 에이전트
- **Consistency Agent**: 정합성 검증 에이전트
- **Report Agent**: 보고서 생성 및 검증 에이전트
- **Hybrid Search**: FAISS 벡터 검색과 Whoosh BM25 키워드 검색을 결합한 검색 방식

## Requirements

### Requirement 1: 활용안내서 지식베이스 구축

**User Story:** 시스템 관리자로서, 활용안내서를 파싱하고 인덱싱하여 검증 시 참조할 수 있는 지식베이스를 구축하고 싶습니다.

#### Acceptance Criteria

1. WHEN 활용안내서 DOCX 파일이 입력되면, THE System SHALL 문서를 구조화된 JSON으로 파싱합니다
2. WHEN 활용안내서가 파싱되면, THE System SHALL 조문별 해설, 조문비교표, 체크리스트를 각각 분리하여 청킹합니다
3. WHEN 활용안내서 청크가 생성되면, THE System SHALL 각 청크에 대해 임베딩을 생성하고 FAISS 및 Whoosh 인덱스를 구축합니다
4. WHEN 활용안내서 인덱스가 구축되면, THE System SHALL 표준계약서 인덱스와 독립적으로 검색 가능한 상태로 저장합니다

### Requirement 2: 사용자 계약서 파싱 및 전처리

**User Story:** 사용자로서, DOCX 형식의 계약서를 업로드하면 시스템이 자동으로 구조를 분석하고 검증 준비를 완료하기를 원합니다.

#### Acceptance Criteria

1. WHEN 사용자가 DOCX 계약서를 업로드하면, THE System SHALL 파일을 수신하고 임시 저장소에 저장합니다
2. WHEN DOCX 파일이 저장되면, THE System SHALL 문서의 계층 구조(조, 항, 호, 목)를 추출하고 구조화된 JSON으로 변환합니다
3. WHEN 사용자 계약서가 표준계약서와 다른 구조를 가지면, THE System SHALL 유연하게 파싱하고 가능한 계층 정보를 추출합니다
4. WHEN 파싱이 완료되면, THE System SHALL 구조화된 데이터를 Classification Agent로 전달합니다

### Requirement 3: 계약서 유형 분류

**User Story:** 시스템 사용자로서, 업로드한 계약서가 5종의 표준계약서 중 어떤 유형에 해당하는지 자동으로 판별되고, 필요시 직접 수정할 수 있기를 원합니다.

#### Acceptance Criteria

1. WHEN 사용자 계약서의 구조화된 데이터가 입력되면, THE Classification Agent SHALL 계약서의 주요 조항과 내용을 분석합니다
2. WHEN 계약서 내용이 분석되면, THE Classification Agent SHALL RAG를 활용하여 5종의 표준계약서와 유사도를 계산합니다
3. WHEN 유사도 계산이 완료되면, THE Classification Agent SHALL 가장 유사한 표준계약서 유형을 선택하고 신뢰도 점수를 산출합니다
4. WHEN 분류 결과가 생성되면, THE System SHALL 사용자에게 분류 결과와 신뢰도 점수를 표시하고 유형 변경 옵션을 제공합니다
5. IF 사용자가 유형을 변경하면, THEN THE System SHALL 사용자가 선택한 유형을 적용합니다
6. WHEN 유형이 확정되면, THE System SHALL 해당 유형의 표준계약서를 기준으로 Consistency Agent에 작업을 전달합니다

### Requirement 4: 복합 검색 시스템 구현

**User Story:** 검증 에이전트로서, 사용자 계약서의 특정 조항을 검증할 때 표준계약서와 활용안내서에서 관련 정보를 효과적으로 검색하고 싶습니다.

#### Acceptance Criteria

1. WHEN 검증 쿼리가 입력되면, THE System SHALL 표준계약서 인덱스와 활용안내서 인덱스에서 각각 하이브리드 검색을 수행합니다
2. WHEN 하이브리드 검색이 수행되면, THE System SHALL Dense 검색(FAISS)과 Sparse 검색(Whoosh BM25)의 결과를 가중합으로 융합합니다
3. WHEN 두 인덱스의 검색 결과가 반환되면, THE System SHALL 표준계약서 결과와 활용안내서 결과를 통합하여 순위를 재조정합니다
4. WHEN 최종 검색 결과가 생성되면, THE System SHALL 조 단위로 집계하고 관련 청크 정보를 포함하여 반환합니다

### Requirement 5: 정합성 검증 에이전트 구현

**User Story:** 사용자로서, 내 계약서가 표준계약서 대비 어떤 항목이 부족하거나 불충분한지 상세한 분석을 받고 싶습니다.

#### Acceptance Criteria

1. WHEN 사용자 계약서와 분류된 표준계약서 유형이 입력되면, THE Consistency Agent SHALL 검증 프로세스를 시작합니다
2. WHEN 검증이 시작되면, THE Consistency Agent SHALL 사용자 계약서의 각 조항에 대해 표준계약서 및 활용안내서를 참조하여 충실도를 평가합니다
3. WHEN 조항 평가가 완료되면, THE Consistency Agent SHALL 체크리스트 기반으로 권장 항목의 존재 여부를 확인합니다
4. WHEN 권장 항목 확인이 완료되면, THE Consistency Agent SHALL 각 조항의 내용 완전성을 평가하고 개선 제안을 생성합니다
5. WHEN 모든 검증이 완료되면, THE Consistency Agent SHALL 검증 결과를 구조화된 형태로 Report Agent에 전달합니다

### Requirement 6: 보고서 생성 및 품질 검증

**User Story:** 사용자로서, 검증 결과를 이해하기 쉬운 형태의 보고서로 받고, 보고서가 과도하게 엄격하거나 누락된 문제가 없는지 확인되기를 원합니다.

#### Acceptance Criteria

1. WHEN Consistency Agent의 검증 결과가 입력되면, THE Report Agent SHALL 결과를 재검토하여 과도한 규격화 여부를 확인합니다
2. WHEN 재검토 중 과도한 규격화가 발견되면, THE Report Agent SHALL Consistency Agent에 피드백을 전달하고 재검증을 요청합니다
3. WHEN 재검토 중 누락된 문제점이 발견되면, THE Report Agent SHALL 추가 분석을 수행하고 결과를 보완합니다
4. WHEN 검증 결과가 적절하다고 판단되면, THE Report Agent SHALL 사용자 친화적인 보고서를 생성합니다
5. WHEN 보고서가 생성되면, THE Report Agent SHALL 문제점, 개선 제안, 참조 조항을 포함하여 프론트엔드로 전달합니다

### Requirement 7: 프론트엔드 보고서 표시

**User Story:** 사용자로서, 검증 결과 보고서를 웹 인터페이스에서 확인하고 다운로드할 수 있기를 원합니다.

#### Acceptance Criteria

1. WHEN 보고서가 생성되면, THE System SHALL 프론트엔드에 보고서 데이터를 전달합니다
2. WHEN 보고서 데이터가 수신되면, THE Frontend SHALL 문제점을 심각도별로 분류하여 표시합니다
3. WHEN 사용자가 특정 문제점을 클릭하면, THE Frontend SHALL 해당 조항의 상세 정보와 개선 제안을 표시합니다
4. WHEN 사용자가 다운로드를 요청하면, THE Frontend SHALL 보고서를 PDF 또는 DOCX 형식으로 다운로드합니다

### Requirement 8: 시스템 통합 및 메시지 큐

**User Story:** 시스템 관리자로서, 각 에이전트가 독립적으로 동작하면서도 안정적으로 통신하는 아키텍처를 원합니다.

#### Acceptance Criteria

1. WHEN FastAPI가 사용자 계약서를 수신하면, THE System SHALL Redis 메시지 큐를 통해 Classification Agent에 작업을 전달합니다
2. WHEN Classification Agent가 작업을 완료하면, THE System SHALL 결과를 Redis를 통해 Consistency Agent에 전달합니다
3. WHEN Consistency Agent가 작업을 완료하면, THE System SHALL 결과를 Redis를 통해 Report Agent에 전달합니다
4. WHEN Report Agent가 작업을 완료하면, THE System SHALL 최종 보고서를 FastAPI를 통해 프론트엔드에 반환합니다
5. WHEN 에이전트 간 통신 중 오류가 발생하면, THE System SHALL 오류를 로깅하고 사용자에게 적절한 오류 메시지를 표시합니다

### Requirement 9: 맥락 기반 유연한 검증

**User Story:** 사용자로서, 내 계약서가 표준계약서와 구조나 내용이 다르더라도 계약의 목적과 맥락을 고려한 검증을 받고 싶습니다.

#### Acceptance Criteria

1. WHEN 사용자 계약서의 조항이 표준계약서와 다른 제목을 가지면, THE System SHALL 의미적 유사도를 기반으로 대응 조항을 찾습니다
2. WHEN 사용자 계약서에 표준계약서에 없는 조항이 있으면, THE System SHALL 해당 조항의 목적을 분석하고 계약 맥락에서의 적절성을 평가합니다
3. WHEN 표준계약서의 권장 조항이 사용자 계약서에 명시적으로 없으면, THE System SHALL 다른 조항에서 해당 내용이 실질적으로 포함되었는지 확인합니다
4. WHEN 검증 결과를 생성할 때, THE System SHALL 단순 형식 비교가 아닌 내용의 실질적 충족도를 평가합니다
5. WHEN 계약 당사자의 특수한 목적으로 인한 차이가 감지되면, THE System SHALL 이를 문제점이 아닌 특이사항으로 분류합니다
