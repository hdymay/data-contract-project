# Requirements Document - Consistency Agent A3 Node

## Introduction

본 문서는 Consistency Validation Agent의 A3 노드(Content Analysis)에 대한 요구사항을 정의합니다. A3 노드는 사용자 계약서의 각 조항 내용이 표준계약서 대비 충실한지 평가하고, 누락된 요소 및 개선 제안을 생성합니다.

## Glossary

- **A3 Node**: Content Analysis 노드, 조항별 내용 충실도 분석
- **User Contract**: 사용자가 업로드한 검증 대상 계약서
- **Standard Contract**: 분류된 유형에 해당하는 표준계약서
- **Content Analysis**: 조항 내용의 완전성, 명확성, 실무적 적절성 평가
- **RAG Search**: 표준계약서에서 대응 조항을 검색하는 방법
- **LLM Analysis**: Azure OpenAI GPT-4를 사용한 내용 비교 및 분석
- **Missing Elements**: 표준계약서 대비 누락된 핵심 요소
- **Suggestions**: 조항 개선을 위한 구체적 제안

## Requirements

### Requirement 1: 조항별 대응 조항 검색 (멀티벡터 방식)

**User Story:** 검증 시스템으로서, 사용자 계약서의 각 조항에 대해 표준계약서에서 의미적으로 유사한 대응 조항을 찾고 싶습니다.

#### Acceptance Criteria

1. WHEN 사용자 계약서의 조항이 입력되면, THE A3 Node SHALL 조항의 각 하위항목을 정규화하여 개별 검색 쿼리로 사용합니다
2. WHEN 각 하위항목으로 RAG 검색이 수행되면, THE A3 Node SHALL 하이브리드 검색(FAISS 0.85 + Whoosh 0.15)을 통해 상위 10개 유사 청크를 반환합니다
3. WHEN 청크 레벨 검색이 완료되면, THE A3 Node SHALL 청크들을 parent_id 기준으로 조 단위로 그룹화합니다
4. WHEN 조 단위 그룹화가 완료되면, THE A3 Node SHALL 정규화된 평균 점수(avg_score / sqrt(total_chunks))를 계산하여 조별 점수를 산출합니다
5. WHEN 조별 점수가 산출되면, THE A3 Node SHALL 최고 점수의 조를 대응 조항으로 선택합니다
6. WHEN 최고 점수가 0.7 이상이면, THE A3 Node SHALL 해당 조를 매칭 성공으로 처리합니다
7. WHEN 최고 점수가 0.7 미만이면, THE A3 Node SHALL 해당 조항을 "특수 조항"으로 분류하고 별도 처리합니다
8. WHEN 대응 조항이 선택되면, THE A3 Node SHALL 해당 조의 모든 청크(조 본문 + 모든 하위항목)를 컨텍스트로 로드합니다

### Requirement 2: LLM 기반 내용 비교

**User Story:** 검증 시스템으로서, 사용자 계약서 조항과 표준계약서 조항의 내용을 LLM으로 비교하여 충실도를 평가하고 싶습니다.

#### Acceptance Criteria

1. WHEN 사용자 조항과 표준 조항이 준비되면, THE A3 Node SHALL LLM에 두 조항을 입력하여 내용 비교를 요청합니다
2. WHEN LLM 분석이 수행되면, THE A3 Node SHALL 완전성(completeness), 명확성(clarity), 실무적 적절성(practicality) 세 가지 측면에서 점수(0~1)를 산출합니다
3. WHEN 완전성 점수가 0.8 미만이면, THE A3 Node SHALL 누락된 핵심 요소 목록을 생성합니다
4. WHEN 명확성 점수가 0.7 미만이면, THE A3 Node SHALL 불명확한 표현 및 개선 방향을 제안합니다
5. WHEN 실무적 적절성 점수가 0.7 미만이면, THE A3 Node SHALL 실무적 관점에서의 문제점 및 개선안을 제안합니다

### Requirement 3: 맥락 기반 유연한 평가

**User Story:** 검증 시스템으로서, 단순 형식 비교가 아닌 계약의 맥락을 고려한 유연한 평가를 수행하고 싶습니다.

#### Acceptance Criteria

1. WHEN 사용자 조항이 표준 조항과 구조적으로 다르면, THE A3 Node SHALL 의미적 유사도를 기반으로 실질적 내용 충족도를 평가합니다
2. WHEN 사용자 조항에 표준 조항에 없는 내용이 포함되면, THE A3 Node SHALL 해당 내용의 목적과 적절성을 분석합니다
3. WHEN 표준 조항의 핵심 요소가 사용자 조항에 명시적으로 없으면, THE A3 Node SHALL 다른 표현이나 암묵적 포함 여부를 확인합니다
4. WHEN 계약 당사자의 특수한 목적으로 인한 차이가 감지되면, THE A3 Node SHALL 이를 문제가 아닌 특이사항으로 분류합니다
5. WHEN 평가 결과를 생성할 때, THE A3 Node SHALL 심각도(low, medium, high)를 맥락에 따라 조정합니다

### Requirement 4: 개선 제안 생성

**User Story:** 사용자로서, 각 조항에 대해 구체적이고 실행 가능한 개선 제안을 받고 싶습니다.

#### Acceptance Criteria

1. WHEN 조항 분석이 완료되면, THE A3 Node SHALL 누락된 요소 각각에 대해 구체적인 개선 제안을 생성합니다
2. WHEN 개선 제안이 생성되면, THE A3 Node SHALL 제안 내용에 예시 문구를 포함합니다
3. WHEN 여러 개선 제안이 있으면, THE A3 Node SHALL 우선순위(중요도)를 부여하여 정렬합니다
4. WHEN 개선 제안이 표준계약서의 특정 부분을 참조하면, THE A3 Node SHALL 참조 위치(조, 항, 호)를 명시합니다
5. WHEN 개선 제안이 법적 리스크와 관련되면, THE A3 Node SHALL 리스크 수준을 명시합니다

### Requirement 5: 특수 조항 처리

**User Story:** 검증 시스템으로서, 표준계약서에 없는 사용자 계약서의 특수 조항을 적절히 처리하고 싶습니다.

#### Acceptance Criteria

1. WHEN 사용자 조항이 표준계약서와 유사도가 낮으면(< 0.7), THE A3 Node SHALL 해당 조항을 특수 조항으로 분류합니다
2. WHEN 특수 조항이 감지되면, THE A3 Node SHALL LLM을 사용하여 조항의 목적과 내용을 분석합니다
3. WHEN 특수 조항 분석이 완료되면, THE A3 Node SHALL 계약 맥락에서의 적절성을 평가합니다
4. WHEN 특수 조항이 계약 목적에 부합하면, THE A3 Node SHALL "특이사항"으로 분류하고 긍정적 평가를 제공합니다
5. WHEN 특수 조항이 계약 목적과 무관하거나 위험하면, THE A3 Node SHALL 경고 또는 제거 권장 제안을 생성합니다

### Requirement 6: 결과 구조화 및 저장

**User Story:** 시스템 관리자로서, A3 노드의 분석 결과를 구조화된 형태로 저장하고 다음 단계(Report Agent)로 전달하고 싶습니다.

#### Acceptance Criteria

1. WHEN 모든 조항 분석이 완료되면, THE A3 Node SHALL 결과를 JSON 형식으로 구조화합니다
2. WHEN 결과가 구조화되면, THE A3 Node SHALL 전체 평균 점수(completeness, clarity, practicality)를 계산합니다
3. WHEN 결과가 준비되면, THE A3 Node SHALL ValidationResult 테이블에 저장합니다
4. WHEN 결과가 저장되면, THE A3 Node SHALL Report Agent로 작업을 전달합니다(Phase 2)
5. WHEN 저장 또는 전달 중 오류가 발생하면, THE A3 Node SHALL 오류를 로깅하고 재시도합니다(최대 3회)

### Requirement 7: 성능 및 확장성

**User Story:** 시스템 관리자로서, A3 노드가 효율적으로 동작하고 확장 가능하기를 원합니다.

#### Acceptance Criteria

1. WHEN 계약서에 20개 조항이 있으면, THE A3 Node SHALL 전체 분석을 5분 이내에 완료합니다
2. WHEN RAG 검색이 수행되면, THE A3 Node SHALL 인덱스를 메모리에 캐싱하여 재로드를 방지합니다
3. WHEN LLM API 호출이 필요하면, THE A3 Node SHALL 가능한 경우 배치 처리를 수행합니다
4. WHEN API 호출이 실패하면, THE A3 Node SHALL 지수 백오프(exponential backoff)로 재시도합니다
5. WHEN 분석 중 메모리 사용량이 임계값을 초과하면, THE A3 Node SHALL 캐시를 정리하고 경고를 로깅합니다

### Requirement 8: 에러 처리 및 로깅

**User Story:** 시스템 관리자로서, A3 노드의 동작 상태를 모니터링하고 문제를 신속히 파악하고 싶습니다.

#### Acceptance Criteria

1. WHEN A3 노드가 시작되면, THE A3 Node SHALL 초기화 상태를 로깅합니다
2. WHEN 각 조항 분석이 시작되면, THE A3 Node SHALL 조항 번호와 제목을 로깅합니다
3. WHEN RAG 검색 또는 LLM 호출이 실패하면, THE A3 Node SHALL 상세한 에러 메시지를 로깅합니다
4. WHEN 분석이 완료되면, THE A3 Node SHALL 처리 시간 및 결과 요약을 로깅합니다
5. WHEN 치명적 오류가 발생하면, THE A3 Node SHALL 부분 결과를 저장하고 오류 상태를 반환합니다
