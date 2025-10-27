"""
수동으로 검증 결과 리포트 생성
"""
import sys
sys.path.append('/app')

from pathlib import Path
from backend.shared.database import SessionLocal, ContractDocument
from backend.consistency_agent.node_1_clause_matching.data_loader import ContractDataLoader
from backend.consistency_agent.node_1_clause_matching.verifier import ContractVerificationEngine
from backend.consistency_agent.node_1_clause_matching.hybrid_search import HybridSearchEngine
from backend.consistency_agent.node_1_clause_matching.llm_verification import LLMVerificationService
from backend.shared.services.embedding_service import EmbeddingService
from backend.report_agent.generator import ReportGenerator
import json

contract_id = sys.argv[1] if len(sys.argv) > 1 else "contract_d836df75e133"

# DB에서 계약서 조회
db = SessionLocal()
contract = db.query(ContractDocument).filter(
    ContractDocument.contract_id == contract_id
).first()

if not contract:
    print(f"계약서를 찾을 수 없습니다: {contract_id}")
    sys.exit(1)

# 검증 결과 다시 로드 (또는 DB에서 가져오기)
# 여기서는 간단하게 검증을 다시 실행
from backend.shared.database import ClassificationResult

classification = db.query(ClassificationResult).filter(
    ClassificationResult.contract_id == contract_id
).first()

contract_type = classification.confirmed_type or classification.predicted_type
chunks_path = contract.parsed_metadata.get("chunks_path")

print(f"계약 유형: {contract_type}")
print(f"Chunks 경로: {chunks_path}")

# 검증 재실행
loader = ContractDataLoader()
embedding_service = EmbeddingService()
hybrid_search = HybridSearchEngine()
llm_verification = LLMVerificationService()
verifier = ContractVerificationEngine(
    embedding_service=embedding_service,
    hybrid_search=hybrid_search,
    llm_verification=llm_verification,
    data_loader=loader
)

standard_clauses = loader.load_standard_contract(
    contract_type=contract_type,
    use_knowledge_base=True
)

with open(chunks_path, 'r', encoding='utf-8') as f:
    user_chunks = json.load(f)

from backend.consistency_agent.node_1_clause_matching.models import ClauseData
user_clauses = [
    ClauseData(
        id=chunk['id'],
        title=chunk.get('title', ''),
        subtitle=None,
        type=chunk.get('unit_type', 'article'),
        text=chunk.get('text_raw', ''),
        text_norm=chunk.get('text_norm', ''),
        breadcrumb=chunk.get('title', ''),
        embedding=chunk.get('embedding')
    )
    for chunk in user_chunks
]

print(f"표준: {len(standard_clauses)}개, 사용자: {len(user_clauses)}개")
print("검증 시작...")

result = verifier.verify_contract_reverse(
    standard_clauses=standard_clauses,
    user_clauses=user_clauses
)

print(f"검증 완료: 매칭 {result.matched_clauses}/{result.total_standard_clauses}")

# 리포트 생성
output_dir = Path("data/reports") / contract_id
generator = ReportGenerator(output_dir=output_dir)

text_report_path = generator.generate_text_report(result)
print(f"\n✅ 텍스트 리포트 생성: {text_report_path}")

try:
    pdf_report_path = generator.generate_pdf_report(result)
    print(f"✅ PDF 리포트 생성: {pdf_report_path}")
except Exception as e:
    print(f"⚠️ PDF 생성 실패 (reportlab 필요): {e}")

db.close()
