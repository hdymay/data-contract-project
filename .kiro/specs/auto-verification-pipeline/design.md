# Design Document

## Overview

사용자가 Streamlit에서 계약서를 업로드하면 FastAPI 백엔드가 자동으로 전체 검증 파이프라인을 실행하여 결과 리포트를 생성하는 시스템입니다. 기존 CLI 기반 검증 로직을 재사용하되, API 엔드포인트로 래핑하여 웹 인터페이스에서 사용할 수 있도록 합니다.

## Architecture

### High-Level Flow

```
[Streamlit Frontend]
        ↓ (1) 파일 업로드
[FastAPI Backend]
        ↓ (2) 파일 저장
[Verification Pipeline Service]
        ↓ (3) 파싱 → 청킹 → 임베딩 → 검증
[Report Generator]
        ↓ (4) 리포트 생성
[FastAPI Backend]
        ↓ (5) 리포트 경로 반환
[Streamlit Frontend]
        ↓ (6) 결과 표시 및 다운로드
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                  Streamlit Frontend                      │
│  - 파일 업로드 UI                                         │
│  - 검증 진행 상태 표시                                     │
│  - 결과 다운로드 버튼                                      │
└────────────────┬────────────────────────────────────────┘
                 │ HTTP POST /upload
                 │ HTTP POST /verify
                 ↓
┌─────────────────────────────────────────────────────────┐
│                   FastAPI Backend                        │
│  - /upload: 파일 업로드 및 저장                           │
│  - /verify: 검증 파이프라인 실행                          │
│  - /report/{report_id}: 리포트 다운로드                   │
└────────────────┬────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────┐
│          VerificationPipelineService                     │
│  - run_pipeline(): 전체 파이프라인 실행                   │
│  - parse_document(): 문서 파싱                           │
│  - chunk_document(): 조문 청킹                           │
│  - generate_embeddings(): 임베딩 생성                    │
│  - verify_contract(): 계약서 검증                        │
└────────────────┬────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────┐
│              Existing Verification Engine                │
│  - ContractVerificationEngine                            │
│  - HybridSearchEngine                                    │
│  - LLMVerificationService                                │
│  - ReportGenerator                                       │
└─────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. VerificationPipelineService

새로 추가할 서비스 클래스로, 전체 검증 파이프라인을 오케스트레이션합니다.

**위치**: `backend/clause_verification/verification_pipeline_service.py`

**주요 메서드**:

```python
class VerificationPipelineService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        verification_engine: ContractVerificationEngine,
        report_generator: ReportGenerator
    ):
        """파이프라인 서비스 초기화"""
        pass
    
    def run_pipeline(
        self,
        user_contract_path: Path,
        standard_contract_path: Optional[Path] = None,
        output_format: str = "txt"
    ) -> Dict[str, Any]:
        """
        전체 검증 파이프라인 실행
        
        Args:
            user_contract_path: 사용자 계약서 파일 경로 (TXT, DOCX, PDF)
            standard_contract_path: 표준 계약서 경로 (기본값: config에서 로드)
            output_format: 리포트 형식 ("txt", "pdf", "both")
        
        Returns:
            {
                "success": bool,
                "report_path": str,
                "report_txt_path": Optional[str],
                "report_pdf_path": Optional[str],
                "verification_result": VerificationResult,
                "execution_time": float,
                "error": Optional[str]
            }
        """
        pass
    
    def _parse_document(self, file_path: Path) -> str:
        """문서 파싱 (PDF, DOCX, TXT 지원)"""
        pass
    
    def _chunk_document(self, text: str, file_path: Path) -> List[ClauseData]:
        """텍스트를 조문 단위로 청킹"""
        pass
    
    def _generate_embeddings(self, clauses: List[ClauseData]) -> List[ClauseData]:
        """조문 임베딩 생성"""
        pass
    
    def _verify_contract(
        self,
        standard_clauses: List[ClauseData],
        user_clauses: List[ClauseData]
    ) -> VerificationResult:
        """계약서 검증 실행"""
        pass
```

### 2. FastAPI Endpoints

**위치**: `backend/fastapi/main.py`

**새로운 엔드포인트**:

```python
@app.post("/verify")
async def verify_contract(
    file: UploadFile = File(...),
    output_format: str = "txt"
) -> Dict[str, Any]:
    """
    계약서 업로드 및 자동 검증
    
    Args:
        file: 업로드된 계약서 파일 (TXT, DOCX, PDF)
        output_format: 리포트 형식 ("txt", "pdf", "both")
    
    Returns:
        {
            "success": bool,
            "filename": str,
            "report_id": str,
            "report_path": str,
            "verification_summary": {
                "total_standard_clauses": int,
                "matched_clauses": int,
                "missing_clauses": int,
                "compliance_rate": float
            },
            "execution_time": float,
            "error": Optional[str]
        }
    """
    pass

@app.get("/report/{report_id}")
async def download_report(report_id: str):
    """
    검증 리포트 다운로드
    
    Args:
        report_id: 리포트 ID (파일명에서 추출)
    
    Returns:
        FileResponse: 리포트 파일
    """
    pass
```

### 3. Streamlit Frontend Updates

**위치**: `frontend/app.py`

**주요 변경사항**:

```python
def main():
    # 기존 업로드 UI
    file = st.file_uploader(...)
    
    if file is not None:
        if st.button("업로드 및 검증 시작", type="primary"):
            # 진행 상태 표시
            with st.spinner("검증 진행 중... (1-2분 소요)"):
                # /verify 엔드포인트 호출
                response = requests.post(
                    "http://localhost:8000/verify",
                    files={"file": file},
                    data={"output_format": "txt"}
                )
            
            if response.status_code == 200:
                result = response.json()
                
                # 검증 결과 요약 표시
                st.success("✅ 검증 완료!")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("매칭률", f"{result['verification_summary']['compliance_rate']:.1f}%")
                with col2:
                    st.metric("매칭 조항", result['verification_summary']['matched_clauses'])
                with col3:
                    st.metric("누락 조항", result['verification_summary']['missing_clauses'])
                
                # 리포트 다운로드 버튼
                report_url = f"http://localhost:8000/report/{result['report_id']}"
                st.download_button(
                    label="📄 검증 리포트 다운로드",
                    data=requests.get(report_url).content,
                    file_name=f"verification_report_{result['report_id']}.txt",
                    mime="text/plain"
                )
                
                # 상세 결과 표시 (expander)
                with st.expander("📋 상세 검증 결과 보기"):
                    st.text(requests.get(report_url).text)
```

## Data Models

### VerificationPipelineResult

```python
@dataclass
class VerificationPipelineResult:
    """파이프라인 실행 결과"""
    success: bool
    report_path: Optional[Path]
    report_txt_path: Optional[Path]
    report_pdf_path: Optional[Path]
    verification_result: Optional[VerificationResult]
    execution_time: float
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "success": self.success,
            "report_path": str(self.report_path) if self.report_path else None,
            "report_txt_path": str(self.report_txt_path) if self.report_txt_path else None,
            "report_pdf_path": str(self.report_pdf_path) if self.report_pdf_path else None,
            "verification_result": self.verification_result.to_dict() if self.verification_result else None,
            "execution_time": self.execution_time,
            "error": self.error
        }
```

## Error Handling

### 오류 처리 전략

1. **파일 업로드 오류**
   - 지원하지 않는 파일 형식: HTTP 400 반환
   - 파일 크기 초과: HTTP 413 반환
   - 파일 저장 실패: HTTP 500 반환

2. **파싱 오류**
   - PDF 파싱 실패: 오류 로깅 후 사용자에게 "파일 파싱 실패" 메시지 반환
   - DOCX 파싱 실패: 동일
   - TXT 인코딩 오류: UTF-8 재시도 후 실패 시 오류 반환

3. **임베딩 생성 오류**
   - Azure OpenAI API 호출 실패: 3회 재시도 (exponential backoff)
   - 재시도 후에도 실패: 오류 메시지 반환 및 파이프라인 중단

4. **검증 오류**
   - 표준 계약서 로드 실패: 오류 반환
   - FAISS 인덱스 로드 실패: 오류 반환
   - LLM 검증 실패: 부분 결과 반환 (매칭된 조항까지만)

5. **리포트 생성 오류**
   - 파일 쓰기 실패: 오류 로깅 후 재시도
   - PDF 생성 실패: TXT 리포트만 반환

### 로깅 전략

```python
# 각 단계별 로깅
logger.info(f"[Pipeline] Starting verification for: {filename}")
logger.info(f"[Pipeline] Step 1/5: Parsing document...")
logger.info(f"[Pipeline] Step 2/5: Chunking document...")
logger.info(f"[Pipeline] Step 3/5: Generating embeddings...")
logger.info(f"[Pipeline] Step 4/5: Running verification...")
logger.info(f"[Pipeline] Step 5/5: Generating report...")
logger.info(f"[Pipeline] Completed in {execution_time:.2f}s")

# 오류 로깅
logger.error(f"[Pipeline] Failed at step: {step_name}", exc_info=True)
```

## Testing Strategy

### Unit Tests

1. **VerificationPipelineService 테스트**
   - `test_parse_document_txt()`: TXT 파일 파싱
   - `test_parse_document_docx()`: DOCX 파일 파싱
   - `test_parse_document_pdf()`: PDF 파일 파싱
   - `test_chunk_document()`: 텍스트 청킹
   - `test_generate_embeddings()`: 임베딩 생성
   - `test_run_pipeline_success()`: 전체 파이프라인 성공 케이스
   - `test_run_pipeline_parsing_error()`: 파싱 오류 처리
   - `test_run_pipeline_embedding_error()`: 임베딩 오류 처리

2. **FastAPI 엔드포인트 테스트**
   - `test_verify_endpoint_txt()`: TXT 파일 검증
   - `test_verify_endpoint_docx()`: DOCX 파일 검증
   - `test_verify_endpoint_invalid_format()`: 잘못된 파일 형식
   - `test_download_report()`: 리포트 다운로드

### Integration Tests

1. **End-to-End 테스트**
   - `test_e2e_txt_verification()`: TXT 파일 업로드 → 검증 → 리포트 다운로드
   - `test_e2e_docx_verification()`: DOCX 파일 업로드 → 검증 → 리포트 다운로드
   - `test_e2e_with_frontend()`: Streamlit에서 전체 플로우 테스트

### Manual Testing

1. **Streamlit UI 테스트**
   - 파일 업로드 → "검증 진행 중..." 메시지 확인
   - 검증 완료 후 결과 요약 확인
   - 리포트 다운로드 버튼 동작 확인
   - 상세 결과 expander 확인

2. **성능 테스트**
   - 다양한 크기의 계약서 파일 테스트 (1KB ~ 1MB)
   - 실행 시간 측정 (목표: 2분 이내)

## Configuration

### 환경 변수

```bash
# .env 파일
AZURE_OPENAI_API_KEY=your_api_key
AZURE_ENDPOINT=your_endpoint
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_LLM_DEPLOYMENT=gpt-4o

# 파이프라인 설정
STANDARD_CONTRACT_PATH=data/chunked_documents/provide_std_contract_chunks.json
VERIFICATION_MODE=reverse  # forward 또는 reverse
OUTPUT_FORMAT=txt  # txt, pdf, both

# 검증 파라미터
TOP_K_CANDIDATES=10
TOP_K_TITLES=5
MIN_CONFIDENCE=0.5
```

### 파일 경로 구조

```
data/
├── source_documents/          # 원본 업로드 파일
│   └── user_contract_*.txt
├── extracted_documents/       # 파싱된 JSON (사용 안 함)
├── chunked_documents/         # 청킹된 조문 데이터
│   ├── provide_std_contract_chunks.json  # 표준 계약서
│   └── user_contract_*_chunks.json       # 사용자 계약서 (임시)
├── embeddings/                # 임베딩 데이터
│   └── provide_std_contract_embeddings.npy
├── search_indexes/            # FAISS 인덱스
│   └── faiss/
│       └── provide_std_contract.index
└── reports/                   # 검증 리포트
    └── verification_report_YYYYMMDD_HHMMSS.txt
```

## Implementation Notes

### 기존 코드 재사용

- **ContractDataLoader**: 표준 계약서 로드에 재사용
- **ContractVerificationEngine**: 검증 로직 재사용
- **ReportGenerator**: 리포트 생성 재사용
- **ingestion/parsers**: 문서 파싱 로직 재사용
- **ingestion/processors/chunker**: 청킹 로직 재사용

### 새로 구현할 부분

- **VerificationPipelineService**: 파이프라인 오케스트레이션
- **FastAPI /verify 엔드포인트**: API 래퍼
- **FastAPI /report/{report_id} 엔드포인트**: 리포트 다운로드
- **Streamlit UI 업데이트**: 검증 버튼 및 결과 표시

### 성능 최적화

1. **표준 계약서 캐싱**: 서버 시작 시 한 번만 로드
2. **FAISS 인덱스 캐싱**: 메모리에 유지
3. **임베딩 배치 처리**: 여러 조문을 한 번에 임베딩
4. **비동기 처리**: FastAPI의 async/await 활용 (선택사항)

### 보안 고려사항

1. **파일 크기 제한**: 최대 10MB
2. **파일 형식 검증**: MIME 타입 확인
3. **경로 탐색 방지**: 파일명 sanitization
4. **임시 파일 정리**: 검증 완료 후 삭제 (선택사항)
