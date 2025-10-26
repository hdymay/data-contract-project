# Requirements Document

## Introduction

사용자가 Streamlit 프론트엔드에서 계약서 파일을 업로드하면, 업로드 즉시 자동으로 파싱 → 청킹 → 임베딩 → 검증 → 리포트 생성 파이프라인을 실행하여 검증 결과를 제공하는 기능입니다. 현재는 업로드만 되고 수동으로 CLI에서 검증을 실행해야 하는데, 이를 자동화하여 사용자 경험을 개선합니다.

## Glossary

- **System**: 계약서 자동 검증 시스템 (Contract Auto-Verification System)
- **User Contract**: 사용자가 업로드한 검증 대상 계약서
- **Standard Contract**: 비교 기준이 되는 표준 계약서 (provide_std_contract)
- **Verification Pipeline**: 파싱 → 청킹 → 임베딩 → 검증 → 리포트 생성의 전체 프로세스
- **Report File**: 검증 결과를 담은 텍스트 또는 PDF 파일
- **FastAPI Backend**: 파일 업로드 및 검증 로직을 처리하는 백엔드 서버
- **Streamlit Frontend**: 사용자가 파일을 업로드하고 결과를 확인하는 웹 인터페이스

## Requirements

### Requirement 1

**User Story:** 사용자로서, 계약서 파일을 업로드하면 자동으로 검증이 실행되어 결과를 즉시 확인할 수 있기를 원합니다.

#### Acceptance Criteria

1. WHEN 사용자가 "업로드하기" 버튼을 클릭하면, THE System SHALL 파일을 FastAPI Backend로 전송한다
2. WHEN FastAPI Backend가 파일을 수신하면, THE System SHALL 파일 형식(PDF, DOCX, TXT)에 따라 텍스트를 추출한다
3. WHEN 텍스트 추출이 완료되면, THE System SHALL 추출된 텍스트를 `data/source_documents/` 디렉토리에 저장한다
4. WHEN 파일 저장이 완료되면, THE System SHALL Verification Pipeline을 자동으로 시작한다
5. WHEN Verification Pipeline이 완료되면, THE System SHALL 생성된 Report File의 경로를 응답으로 반환한다

### Requirement 2

**User Story:** 사용자로서, 검증 진행 상황을 확인하고 싶습니다.

#### Acceptance Criteria

1. WHEN Verification Pipeline이 실행 중일 때, THE System SHALL 현재 진행 단계(파싱/청킹/임베딩/검증)를 서버 로그에 기록한다
2. WHILE Verification Pipeline이 실행 중일 때, THE System SHALL Streamlit Frontend에 "검증 진행 중..." 메시지를 표시한다
3. IF Verification Pipeline 실행 중 오류가 발생하면, THEN THE System SHALL 오류 메시지를 사용자에게 표시한다
4. WHEN Verification Pipeline이 완료되면, THE System SHALL "검증 완료" 메시지를 표시한다

### Requirement 3

**User Story:** 사용자로서, 검증 결과 리포트를 다운로드하거나 화면에서 바로 확인하고 싶습니다.

#### Acceptance Criteria

1. WHEN Verification Pipeline이 완료되면, THE System SHALL Report File을 `data/reports/` 디렉토리에 저장한다
2. WHEN Report File이 생성되면, THE System SHALL Streamlit Frontend에 다운로드 버튼을 표시한다
3. WHEN 사용자가 다운로드 버튼을 클릭하면, THE System SHALL Report File을 사용자의 로컬 시스템으로 다운로드한다
4. WHERE 사용자가 화면에서 결과를 확인하고 싶을 때, THE System SHALL Report File의 주요 내용(매칭률, 누락 조항 수)을 Streamlit Frontend에 표시한다
5. WHERE 사용자가 상세 결과를 확인하고 싶을 때, THE System SHALL expander를 통해 전체 리포트 내용을 표시한다

### Requirement 4

**User Story:** 시스템 관리자로서, 검증 파이프라인이 안정적으로 실행되고 오류 발생 시 적절히 처리되기를 원합니다.

#### Acceptance Criteria

1. IF 파일 파싱 중 오류가 발생하면, THEN THE System SHALL 오류를 로깅하고 사용자에게 "파일 파싱 실패" 메시지를 반환한다
2. IF 임베딩 생성 중 Azure OpenAI API 호출이 실패하면, THEN THE System SHALL 재시도를 3회까지 수행한다
3. IF 재시도 후에도 실패하면, THEN THE System SHALL 오류 메시지를 반환하고 파이프라인을 중단한다
4. WHEN Verification Pipeline이 실행될 때, THE System SHALL 각 단계의 시작과 완료를 로그에 기록한다
5. WHEN 파이프라인이 완료되면, THE System SHALL 총 실행 시간을 로그에 기록한다

### Requirement 5

**User Story:** 개발자로서, 검증 파이프라인을 재사용 가능한 모듈로 구현하여 CLI와 API 모두에서 사용할 수 있기를 원합니다.

#### Acceptance Criteria

1. THE System SHALL Verification Pipeline을 독립적인 서비스 클래스로 구현한다
2. THE System SHALL 파이프라인 실행 함수가 파일 경로를 입력으로 받고 Report File 경로를 반환하도록 한다
3. THE System SHALL 파이프라인 실행 함수가 진행 상황 콜백을 지원하도록 한다
4. THE System SHALL 기존 CLI 검증 로직과 동일한 검증 엔진을 사용한다
5. THE System SHALL 파이프라인 설정(표준 계약서 경로, 검증 모드 등)을 환경 변수 또는 설정 파일로 관리한다
