"""
검증 결과 간단히 보기
"""
import sys
contract_id = sys.argv[1] if len(sys.argv) > 1 else "contract_e470eef1d520"

from backend.shared.database import SessionLocal, ContractDocument, ClassificationResult
db = SessionLocal()

contract = db.query(ContractDocument).filter(ContractDocument.contract_id == contract_id).first()
classification = db.query(ClassificationResult).filter(ClassificationResult.contract_id == contract_id).first()

print(f"\n{'='*60}")
print(f"계약서 ID: {contract_id}")
print(f"상태: {contract.status}")
print(f"계약 유형: {classification.confirmed_type if classification else 'N/A'}")
print(f"{'='*60}\n")

# 검증 완료된 경우 상세 정보 표시
if contract.status == "verified":
    print("✅ 검증 완료!")
    print(f"\nChunks 경로: {contract.parsed_metadata.get('chunks_path')}")
    print("\n검증을 다시 실행하려면 scripts/generate_report_manual.py를 사용하세요.")
else:
    print(f"⏳ 현재 상태: {contract.status}")

db.close()
