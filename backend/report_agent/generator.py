"""
Report Generator for Contract Verification Results

이 모듈은 계약서 검증 결과를 텍스트 형식의 보고서로 생성합니다.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from collections import defaultdict
from openai import AzureOpenAI

from backend.shared.models import VerificationResult, ClauseData, MatchResult
from backend.consistency_agent.node_1_clause_matching.config import config

# Configure logging
logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    검증 결과 보고서 생성기
    
    텍스트 형식으로 계약서 검증 결과를 생성합니다.
    """
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        보고서 생성기 초기화
        
        Args:
            output_dir: 보고서 저장 디렉토리 (None인 경우 data/reports 사용)
        """
        if output_dir is None:
            output_dir = Path("data/reports")
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Azure OpenAI 클라이언트 초기화
        self.llm_client = AzureOpenAI(
            api_key=config.AZURE_OPENAI_API_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT
        )
        
        logger.info(f"Report Generator initialized with output_dir: {self.output_dir}")
    
    def _group_matches_by_user_article(self, match_results: List[MatchResult]) -> Dict[str, List[MatchResult]]:
        """
        매칭 결과를 사용자 계약서의 조별로 그룹핑
        
        Args:
            match_results: 매칭 결과 리스트
        
        Returns:
            조별로 그룹핑된 매칭 결과 딕셔너리
        """
        grouped = defaultdict(list)
        
        for match in match_results:
            if match.is_matched and match.matched_clause:
                # 사용자 조문 ID에서 조 번호 추출 (예: "제1조 조본문" -> "제1조")
                user_clause_id = match.matched_clause.id
                article_num = user_clause_id.split()[0] if ' ' in user_clause_id else user_clause_id
                
                # 조 제목 추출
                article_title = match.matched_clause.title
                
                # 키는 "조번호 (제목)" 형식
                key = f"{article_num} ({article_title})"
                grouped[key].append(match)
        
        return dict(grouped)
    
    def _analyze_article_matching_pattern(self, matches: List[MatchResult]) -> Dict:
        """
        한 조의 매칭 패턴 분석 (LLM 사용)
        
        Args:
            matches: 한 조에 속한 매칭 결과들
        
        Returns:
            분석 결과 딕셔너리
        """
        # 기본 통계
        total_items = len(matches)
        avg_confidence = sum(m.llm_decision.confidence for m in matches if m.llm_decision) / total_items if total_items > 0 else 0
        
        # 매칭된 표준 조항들 추출
        std_articles = defaultdict(int)
        for match in matches:
            std_article_num = match.standard_clause.id.split()[0] if ' ' in match.standard_clause.id else match.standard_clause.id
            std_articles[std_article_num] += 1
        
        # 매칭 유형 판단
        if len(std_articles) == 1:
            matching_type = "완전 일대일 매칭" if total_items == list(std_articles.values())[0] else "부분 매칭"
        else:
            matching_type = "통합 매칭"
        
        # LLM에게 법적 분석 요청
        legal_analysis = self._generate_legal_analysis(matches, matching_type)
        
        return {
            "total_items": total_items,
            "avg_confidence": avg_confidence,
            "std_articles": dict(std_articles),
            "matching_type": matching_type,
            "legal_analysis": legal_analysis
        }
    
    def _generate_legal_analysis(self, matches: List[MatchResult], matching_type: str) -> str:
        """
        LLM을 사용하여 법적 분석 생성
        
        Args:
            matches: 매칭 결과들
            matching_type: 매칭 유형
        
        Returns:
            법적 분석 텍스트
        """
        # 사용자 조 정보
        user_article = matches[0].matched_clause.title if matches else ""
        user_article_id = matches[0].matched_clause.id.split()[0] if matches and ' ' in matches[0].matched_clause.id else ""
        
        # 표준 조항 정보
        std_info = []
        for match in matches:
            std_id = match.standard_clause.id.split()[0] if ' ' in match.standard_clause.id else match.standard_clause.id
            std_title = match.standard_clause.title
            std_info.append(f"{std_id}({std_title})")
        
        prompt = f"""당신은 계약서 전문가입니다. 다음 매칭 결과에 대한 법적 분석을 2-3문장으로 작성하세요.

**사용자 계약서 조항:** {user_article_id} ({user_article})
**매칭된 표준 조항:** {', '.join(std_info)}
**매칭 유형:** {matching_type}
**매칭된 항목 수:** {len(matches)}개

**분석 요구사항:**
1. 왜 이런 매칭 패턴이 나타났는지 설명
2. 사용자 계약서와 표준 계약서의 구조적 차이
3. 법적 의미나 명확성 측면에서의 차이점

**출력 형식:** 
• (첫 번째 문장)
• (두 번째 문장)
• (세 번째 문장)

각 문장은 bullet point로 시작하고, 간결하고 명확하게 작성하세요."""

        try:
            response = self.llm_client.chat.completions.create(
                model=config.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": "당신은 계약서 분석 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            analysis = response.choices[0].message.content.strip()
            return analysis
            
        except Exception as e:
            logger.error(f"LLM 법적 분석 생성 실패: {e}")
            return "• 분석을 생성할 수 없습니다."
    

    def generate_text_report_with_llm(
        self,
        result: VerificationResult,
        output_path: Optional[str] = None
    ) -> str:
        """
        LLM 기반 텍스트 형식 보고서 생성 (조별 매칭 요약 포함)
        
        Args:
            result: 검증 결과
            output_path: 출력 파일 경로 (None인 경우 자동 생성)
        
        Returns:
            생성된 보고서 파일 경로
        """
        logger.info("Generating LLM-based text report with article summaries...")
        
        # 출력 파일 경로 결정
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"verification_report_{timestamp}.txt"
        else:
            output_path = Path(output_path)
        
        # 보고서 내용 생성
        report_lines = []
        
        # 헤더
        report_lines.append("=" * 80)
        report_lines.append("📋 내 계약서 검증 결과")
        report_lines.append("My Contract Verification Report")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # 검증 일시
        report_lines.append(f"검증 일시: {result.verification_date.strftime('%Y년 %m월 %d일 %H:%M:%S')}")
        report_lines.append("")
        
        # 검증 결과 요약
        report_lines.append("-" * 80)
        report_lines.append("📊 검증 결과 요약")
        report_lines.append("-" * 80)
        report_lines.append(f"내 계약서 조문 수: {result.total_user_clauses}개")
        report_lines.append(f"표준 계약서와 매칭된 조문: {result.matched_clauses}개")
        report_lines.append(f"표준 계약서에 없는 조문: {result.total_user_clauses - result.matched_clauses}개")
        report_lines.append("")
        report_lines.append(f"검증 완료율: {result.verification_rate:.2f}%")
        report_lines.append("")
        
        # 조별 매칭 요약
        report_lines.append("-" * 80)
        report_lines.append("📘 내 계약서 조별 매칭 요약")
        report_lines.append("-" * 80)
        report_lines.append("")
        
        # 매칭 결과를 조별로 그룹핑
        grouped_matches = self._group_matches_by_user_article(result.match_results)
        
        for article_key, matches in sorted(grouped_matches.items()):
            # 조별 분석
            analysis = self._analyze_article_matching_pattern(matches)
            
            # 표준 조항 정보
            std_articles_str = ", ".join([f"제{k.replace('제', '').replace('조', '')}조" for k in analysis['std_articles'].keys()])
            
            # 요약 헤더
            report_lines.append(f"📘 [요약] {article_key} — 표준 {std_articles_str}와 매칭 ({analysis['matching_type']})")
            report_lines.append("─" * 60)
            
            # 법적 분석
            report_lines.append(analysis['legal_analysis'])
            report_lines.append("")
            
            # 통계 정보
            if analysis['matching_type'] == "완전 일대일 매칭":
                report_lines.append(f"📊 사용자 {article_key.split('(')[0]}의 모든 항({analysis['total_items']}개)이 표준 {std_articles_str}와 매칭됨")
            elif analysis['matching_type'] == "부분 매칭":
                # 전체 항 수 계산 (이건 근사치)
                report_lines.append(f"📊 사용자 {article_key.split('(')[0]}의 일부 항({analysis['total_items']}개)이 표준 {std_articles_str}와 매칭됨")
            else:  # 통합 매칭
                report_lines.append(f"📊 매칭 상세:")
                for std_art, count in analysis['std_articles'].items():
                    std_num = std_art.replace('제', '').replace('조', '')
                    report_lines.append(f"  • 제{std_num}조: {count}개 항 매칭")
            
            report_lines.append(f"  • 평균 신뢰도: {analysis['avg_confidence']:.1%}")
            report_lines.append("─" * 60)
            report_lines.append("")
        
        # 항별 상세 매칭 결과
        matched_clauses = [r for r in result.match_results if r.is_matched]
        
        report_lines.append("-" * 80)
        report_lines.append("✅ 내 계약서 항별 상세 매칭 결과")
        report_lines.append("-" * 80)
        report_lines.append("")
        
        if matched_clauses:
            report_lines.append(f"총 {len(matched_clauses)}개 항이 표준 계약서와 매칭되었습니다.")
            report_lines.append("")
            
            for i, match_result in enumerate(matched_clauses, 1):
                user_clause = match_result.matched_clause
                std_clause = match_result.standard_clause
                
                report_lines.append(f"[{i}] {user_clause.display_title}")
                report_lines.append(f"    ID: {user_clause.id}")
                report_lines.append(f"    내용: {user_clause.text[:120]}{'...' if len(user_clause.text) > 120 else ''}")
                report_lines.append("")
                report_lines.append(f"    ✓ 매칭: 표준 {std_clause.display_title} ({std_clause.id})")
                
                if match_result.llm_decision:
                    report_lines.append(f"       신뢰도: {match_result.llm_decision.confidence:.0%}")
                    report_lines.append(f"       판단: {match_result.llm_decision.reasoning[:180]}{'...' if len(match_result.llm_decision.reasoning) > 180 else ''}")
                
                report_lines.append("")
        else:
            report_lines.append("⚠️ 매칭된 항이 없습니다.")
            report_lines.append("")
        
        # 누락된 조문
        report_lines.append("-" * 80)
        report_lines.append("❌ 표준 계약서에 있지만 내 계약서에 없는 조문")
        report_lines.append("-" * 80)
        report_lines.append("")
        
        if result.missing_clauses:
            report_lines.append(f"총 {len(result.missing_clauses)}개의 표준 조문이 누락되었습니다.")
            report_lines.append("")
            
            for i, clause in enumerate(result.missing_clauses, 1):
                report_lines.append(f"{i}. {clause.display_title}")
                report_lines.append(f"   표준 조문 ID: {clause.id}")
                
                # 조문 내용 미리보기
                text_preview = clause.text[:150]
                if len(clause.text) > 150:
                    text_preview += "..."
                report_lines.append(f"   내용: {text_preview}")
                report_lines.append("")
        else:
            report_lines.append("✓ 모든 표준 조문이 포함되어 있습니다!")
            report_lines.append("")
        
        # 권장사항
        report_lines.append("-" * 80)
        report_lines.append("⚠️ 권장사항")
        report_lines.append("-" * 80)
        report_lines.append("")
        
        if result.missing_clauses:
            # 중요한 누락 조문 식별
            important_keywords = ['목적', '정의', '손해배상', '비밀유지', '계약기간', '해지']
            important_missing = [
                c for c in result.missing_clauses 
                if any(keyword in c.display_title for keyword in important_keywords)
            ]
            
            if important_missing:
                report_lines.append("🔴 중요: 다음 필수 조항들이 누락되었습니다:")
                report_lines.append("")
                for clause in important_missing[:5]:
                    report_lines.append(f"  • {clause.display_title} 추가 권장")
                report_lines.append("")
            
            report_lines.append("💡 개선 제안:")
            report_lines.append(f"  • 총 {len(result.missing_clauses)}개의 표준 조문 검토 필요")
            report_lines.append("  • 법적 리스크 최소화를 위해 누락된 조문 추가 고려")
            report_lines.append("")
        else:
            report_lines.append("✓ 계약서가 표준 조문을 잘 반영하고 있습니다.")
            report_lines.append("")
        
        # 푸터
        report_lines.append("=" * 80)
        report_lines.append("보고서 끝")
        report_lines.append("=" * 80)
        
        # 파일 저장
        report_content = "\n".join(report_lines)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        
        logger.info(f"LLM-based text report saved to: {output_path}")
        
        return str(output_path)
    
    def generate_text_report(
        self,
        result: VerificationResult,
        output_path: Optional[str] = None
    ) -> str:
        """
        텍스트 형식 보고서 생성 (사용자 계약서 중심)
        
        Args:
            result: 검증 결과
            output_path: 출력 파일 경로 (None인 경우 자동 생성)
        
        Returns:
            생성된 보고서 파일 경로
        """
        # LLM 기반 보고서 생성으로 리다이렉트
        return self.generate_text_report_with_llm(result, output_path)
    
    def format_missing_clauses(self, missing_clauses: list[ClauseData]) -> str:
        """
        누락된 조문을 읽기 쉬운 형식으로 포맷
        
        Args:
            missing_clauses: 누락된 조문 리스트
        
        Returns:
            포맷된 문자열
        """
        if not missing_clauses:
            return "누락된 조문이 없습니다."
        
        lines = []
        
        for i, clause in enumerate(missing_clauses, 1):
            lines.append(f"{i}. {clause.display_title}")
            lines.append(f"   ID: {clause.id}")
            lines.append(f"   타입: {clause.type}")
            
            # 조문 내용 (처음 200자만 표시)
            text_preview = clause.text[:200]
            if len(clause.text) > 200:
                text_preview += "..."
            
            lines.append(f"   내용: {text_preview}")
            lines.append("")
        
        return "\n".join(lines)