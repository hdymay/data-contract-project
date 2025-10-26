"""
Report Generator for Contract Verification Results

이 모듈은 계약서 검증 결과를 텍스트 및 PDF 형식의 보고서로 생성합니다.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .models import VerificationResult, ClauseData

# Configure logging
logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    검증 결과 보고서 생성기
    
    텍스트 및 PDF 형식으로 계약서 검증 결과를 생성합니다.
    """
    
    def __init__(self, output_dir: Optional[Path] = None, font_path: Optional[str] = None):
        """
        보고서 생성기 초기화
        
        Args:
            output_dir: 보고서 저장 디렉토리 (None인 경우 data/reports 사용)
            font_path: 한글 폰트 파일 경로 (None인 경우 기본 폰트 사용)
        """
        if output_dir is None:
            output_dir = Path("data/reports")
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 한글 폰트 설정
        self.font_name = "NanumGothic"
        self._setup_korean_font(font_path)
        
        logger.info(f"Report Generator initialized with output_dir: {self.output_dir}")
    
    def _setup_korean_font(self, font_path: Optional[str] = None):
        """
        한글 폰트 설정
        
        Args:
            font_path: 폰트 파일 경로 (None인 경우 시스템 폰트 검색)
        """
        try:
            if font_path and Path(font_path).exists():
                pdfmetrics.registerFont(TTFont(self.font_name, font_path))
                logger.info(f"Korean font registered: {font_path}")
            else:
                # 일반적인 Windows/Linux 폰트 경로 시도
                common_paths = [
                    "C:/Windows/Fonts/malgun.ttf",  # Windows - 맑은 고딕
                    "C:/Windows/Fonts/NanumGothic.ttf",  # Windows - 나눔고딕
                    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # Linux
                    "/System/Library/Fonts/AppleGothic.ttf",  # macOS
                ]
                
                font_registered = False
                for path in common_paths:
                    if Path(path).exists():
                        pdfmetrics.registerFont(TTFont(self.font_name, path))
                        logger.info(f"Korean font registered: {path}")
                        font_registered = True
                        break
                
                if not font_registered:
                    logger.warning(
                        "Korean font not found. PDF may not display Korean text correctly. "
                        "Please provide font_path parameter."
                    )
                    self.font_name = "Helvetica"  # Fallback to default
        except Exception as e:
            logger.error(f"Failed to register Korean font: {e}")
            self.font_name = "Helvetica"  # Fallback to default
    
    def generate_text_report(
        self,
        result: VerificationResult,
        output_path: Optional[str] = None
    ) -> str:
        """
        텍스트 형식 보고서 생성
        
        Args:
            result: 검증 결과
            output_path: 출력 파일 경로 (None인 경우 자동 생성)
        
        Returns:
            생성된 보고서 파일 경로
        """
        logger.info("Generating text report...")
        
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
        report_lines.append("계약서 조문 검증 보고서")
        report_lines.append("Contract Clause Verification Report")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # 검증 일시
        report_lines.append(f"검증 일시: {result.verification_date.strftime('%Y년 %m월 %d일 %H:%M:%S')}")
        report_lines.append("")
        
        # 검증 결과 요약
        report_lines.append("-" * 80)
        report_lines.append("검증 결과 요약")
        report_lines.append("-" * 80)
        report_lines.append(f"표준 계약서 조문 수: {result.total_standard_clauses}개")
        report_lines.append(f"사용자 계약서 조문 수: {result.total_user_clauses}개")
        report_lines.append(f"매칭된 조문 수: {result.matched_clauses}개")
        report_lines.append(f"누락된 조문 수: {result.missing_count}개")
        report_lines.append(f"중복 매칭 수: {result.duplicate_count}개")
        report_lines.append("")
        report_lines.append(f"검증 완료율: {result.verification_rate:.2f}% (사용자 계약서 기준)")
        report_lines.append(f"완전성 여부: {'완전' if result.is_complete else '불완전'}")
        report_lines.append("")
        
        # 1. 매칭된 조문 목록 (먼저 표시)
        matched_results = [r for r in result.match_results if r.is_matched]
        if matched_results:
            report_lines.append("-" * 80)
            report_lines.append("✓ 매칭된 조문")
            report_lines.append("-" * 80)
            report_lines.append("")
            
            for i, match in enumerate(matched_results, 1):
                std_clause = match.standard_clause
                user_clause = match.matched_clause
                
                report_lines.append(f"{i}. {std_clause.display_title}")
                report_lines.append(f"   ID: {std_clause.id}")
                report_lines.append(f"   상태: ✓ 매칭됨")
                report_lines.append(f"   매칭된 사용자 조문: {user_clause.display_title} (ID: {user_clause.id})")
                report_lines.append("")
                report_lines.append(f"   📝 항 내용: {std_clause.text}")
                report_lines.append("")
                
                if match.llm_decision:
                    report_lines.append(f"   🤖 LLM 판단 근거:")
                    report_lines.append(f"   {match.llm_decision.reasoning}")
                    report_lines.append("")
                    report_lines.append(f"   신뢰도: {match.llm_decision.confidence:.2f}")
                
                report_lines.append(f"   FAISS 점수: {match.faiss_score:.4f}")
                report_lines.append("")
        
        # 2. 누락된 조문 목록 (두 번째로 표시)
        if result.missing_clauses:
            report_lines.append("-" * 80)
            report_lines.append("❌ 누락된 조문 목록")
            report_lines.append("-" * 80)
            report_lines.append("")
            
            formatted_missing = self.format_missing_clauses(result.missing_clauses)
            report_lines.append(formatted_missing)
        else:
            report_lines.append("-" * 80)
            report_lines.append("✓ 모든 필수 조문이 포함되어 있습니다.")
            report_lines.append("-" * 80)
            report_lines.append("")
        
        # 3. 중복 매칭 목록 (있는 경우)
        if result.duplicate_matches:
            report_lines.append("-" * 80)
            report_lines.append("⚠️ 중복 매칭 감지")
            report_lines.append("-" * 80)
            report_lines.append("")
            report_lines.append("다음 사용자 조문들이 이미 매칭된 표준 조문과 중복 매칭되었습니다:")
            report_lines.append("")
            
            for i, dup_match in enumerate(result.duplicate_matches, 1):
                user_clause = dup_match.matched_clause
                std_clause = dup_match.standard_clause
                report_lines.append(f"{i}. 사용자 조문: {user_clause.display_title} (ID: {user_clause.id})")
                report_lines.append(f"   → 표준 조문: {std_clause.display_title} (ID: {std_clause.id})")
                report_lines.append(f"   신뢰도: {dup_match.llm_decision.confidence:.2f}")
                report_lines.append(f"   사유: {dup_match.duplicate_reason}")
                report_lines.append("")
        
        # 4. 전체 검증 결과 상세 (마지막)
        report_lines.append("-" * 80)
        report_lines.append("전체 검증 결과 상세")
        report_lines.append("-" * 80)
        report_lines.append("")
        
        for i, match_result in enumerate(result.match_results, 1):
            std_clause = match_result.standard_clause
            report_lines.append(f"{i}. {std_clause.display_title}")
            report_lines.append(f"   ID: {std_clause.id}")
            
            if match_result.is_matched:
                matched = match_result.matched_clause
                report_lines.append(f"   상태: ✓ 매칭됨")
                report_lines.append(f"   매칭된 사용자 조문: {matched.display_title} (ID: {matched.id})")
                report_lines.append("")
                report_lines.append(f"   📋 매칭된 표준 항: {std_clause.id}")
                report_lines.append(f"   📝 항 내용: {std_clause.text[:200]}{'...' if len(std_clause.text) > 200 else ''}")
                report_lines.append("")
                
                if match_result.llm_decision:
                    report_lines.append(f"   🤖 LLM 판단 근거:")
                    report_lines.append(f"   {match_result.llm_decision.reasoning}")
                    report_lines.append("")
                    report_lines.append(f"   신뢰도: {match_result.llm_decision.confidence:.2f}")
                    report_lines.append(f"   FAISS 점수: {match_result.hybrid_score:.4f}")
            else:
                report_lines.append(f"   상태: ✗ 누락")
                if match_result.llm_decision:
                    report_lines.append(f"   사유: {match_result.llm_decision.reasoning}")
            
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
        
        logger.info(f"Text report saved to: {output_path}")
        
        return str(output_path)
    
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
    
    def generate_pdf_report(
        self,
        result: VerificationResult,
        output_path: Optional[str] = None
    ) -> str:
        """
        PDF 형식 보고서 생성
        
        Args:
            result: 검증 결과
            output_path: 출력 파일 경로 (None인 경우 자동 생성)
        
        Returns:
            생성된 보고서 파일 경로
        """
        logger.info("Generating PDF report...")
        
        # 출력 파일 경로 결정
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"verification_report_{timestamp}.pdf"
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # PDF 문서 생성
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # 스타일 설정
        styles = self._create_pdf_styles()
        
        # 문서 요소 리스트
        story = []
        
        # 제목
        story.append(Paragraph("계약서 조문 검증 보고서", styles['Title']))
        story.append(Paragraph("Contract Clause Verification Report", styles['ReportSubtitle']))
        story.append(Spacer(1, 0.5*cm))
        
        # 검증 일시
        verification_date = result.verification_date.strftime('%Y년 %m월 %d일 %H:%M:%S')
        story.append(Paragraph(f"검증 일시: {verification_date}", styles['Normal']))
        story.append(Spacer(1, 0.5*cm))
        
        # 검증 결과 요약 테이블
        story.append(Paragraph("검증 결과 요약", styles['Heading1']))
        story.append(Spacer(1, 0.3*cm))
        
        summary_data = [
            ['항목', '값'],
            ['표준 계약서 조문 수', f"{result.total_standard_clauses}개"],
            ['사용자 계약서 조문 수', f"{result.total_user_clauses}개"],
            ['매칭된 조문 수', f"{result.matched_clauses}개"],
            ['누락된 조문 수', f"{result.missing_count}개"],
            ['중복 매칭 수', f"{result.duplicate_count}개"],
            ['검증 완료율', f"{result.verification_rate:.2f}%"],
            ['완전성 여부', '완전' if result.is_complete else '불완전']
        ]
        
        summary_table = Table(summary_data, colWidths=[8*cm, 8*cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), self.font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 0.5*cm))
        
        # 중복 매칭 목록
        if result.duplicate_matches:
            story.append(Paragraph("⚠ 중복 매칭 감지", styles['Heading1']))
            story.append(Spacer(1, 0.3*cm))
            
            story.append(Paragraph(
                "다음 사용자 조문들이 이미 매칭된 표준 조문과 중복 매칭되었습니다:",
                styles['Normal']
            ))
            story.append(Spacer(1, 0.3*cm))
            
            for i, dup_match in enumerate(result.duplicate_matches, 1):
                user_clause = dup_match.matched_clause
                std_clause = dup_match.standard_clause
                
                story.append(Paragraph(
                    f"{i}. 사용자 조문: {user_clause.display_title}",
                    styles['Heading2']
                ))
                story.append(Paragraph(
                    f"→ 표준 조문: {std_clause.display_title}",
                    styles['Normal']
                ))
                story.append(Paragraph(
                    f"신뢰도: {dup_match.llm_decision.confidence:.2f}",
                    styles['Normal']
                ))
                story.append(Paragraph(
                    f"사유: {dup_match.duplicate_reason}",
                    styles['Normal']
                ))
                story.append(Spacer(1, 0.3*cm))
            
            story.append(Spacer(1, 0.5*cm))
        
        # 누락된 조문 목록
        story.append(Paragraph("누락된 조문 목록", styles['Heading1']))
        story.append(Spacer(1, 0.3*cm))
        
        if result.missing_clauses:
            for i, clause in enumerate(result.missing_clauses, 1):
                # 조문 제목
                story.append(Paragraph(
                    f"{i}. {clause.display_title}",
                    styles['Heading2']
                ))
                
                # 조문 정보
                story.append(Paragraph(f"ID: {clause.id}", styles['Normal']))
                story.append(Paragraph(f"타입: {clause.type}", styles['Normal']))
                
                # 조문 내용 (처음 300자)
                text_preview = clause.text[:300]
                if len(clause.text) > 300:
                    text_preview += "..."
                
                story.append(Paragraph(f"내용: {text_preview}", styles['Normal']))
                story.append(Spacer(1, 0.3*cm))
        else:
            story.append(Paragraph(
                "✓ 모든 필수 조문이 포함되어 있습니다.",
                styles['Normal']
            ))
        
        story.append(Spacer(1, 0.5*cm))
        
        # 상세 매칭 결과
        story.append(Paragraph("상세 매칭 결과", styles['Heading1']))
        story.append(Spacer(1, 0.3*cm))
        
        for i, match_result in enumerate(result.match_results, 1):
            std_clause = match_result.standard_clause
            
            # 조문 제목
            story.append(Paragraph(
                f"{i}. {std_clause.display_title}",
                styles['Heading2']
            ))
            
            story.append(Paragraph(f"ID: {std_clause.id}", styles['Normal']))
            
            if match_result.is_matched:
                matched = match_result.matched_clause
                story.append(Paragraph("상태: ✓ 매칭됨", styles['Normal']))
                story.append(Paragraph(
                    f"매칭된 사용자 조문: {matched.display_title} (ID: {matched.id})",
                    styles['Normal']
                ))
                story.append(Spacer(1, 0.2*cm))
                
                # 매칭된 항 상세 정보
                story.append(Paragraph(
                    f"📋 매칭된 표준 항: {std_clause.id}",
                    styles['Normal']
                ))
                
                # 항 내용 (300자 제한)
                text_preview = std_clause.text[:300]
                if len(std_clause.text) > 300:
                    text_preview += "..."
                story.append(Paragraph(
                    f"📝 항 내용: {text_preview}",
                    styles['Normal']
                ))
                story.append(Spacer(1, 0.2*cm))
                
                if match_result.llm_decision:
                    # LLM 판단 근거
                    story.append(Paragraph(
                        "🤖 LLM 판단 근거:",
                        styles['Normal']
                    ))
                    story.append(Paragraph(
                        match_result.llm_decision.reasoning,
                        styles['Normal']
                    ))
                    story.append(Spacer(1, 0.2*cm))
                    
                    story.append(Paragraph(
                        f"신뢰도: {match_result.llm_decision.confidence:.2f}",
                        styles['Normal']
                    ))
                    story.append(Paragraph(
                        f"FAISS 점수: {match_result.hybrid_score:.4f}",
                        styles['Normal']
                    ))
            else:
                story.append(Paragraph("상태: ✗ 누락", styles['Normal']))
                if match_result.llm_decision:
                    story.append(Paragraph(
                        f"사유: {match_result.llm_decision.reasoning}",
                        styles['Normal']
                    ))
            
            story.append(Spacer(1, 0.3*cm))
        
        # PDF 생성
        doc.build(story)
        
        logger.info(f"PDF report saved to: {output_path}")
        
        return str(output_path)
    
    def _create_pdf_styles(self) -> dict:
        """
        PDF 스타일 생성
        
        Returns:
            스타일 딕셔너리
        """
        styles = getSampleStyleSheet()
        
        # 제목 스타일 (기존 Title 스타일 수정)
        styles['Title'].fontName = self.font_name
        styles['Title'].fontSize = 24
        styles['Title'].textColor = colors.HexColor('#1a1a1a')
        styles['Title'].spaceAfter = 12
        styles['Title'].alignment = TA_CENTER
        
        # 부제목 스타일 (새로 추가)
        styles.add(ParagraphStyle(
            name='ReportSubtitle',
            parent=styles['Normal'],
            fontName=self.font_name,
            fontSize=14,
            textColor=colors.HexColor('#666666'),
            spaceAfter=12,
            alignment=TA_CENTER
        ))
        
        # 헤딩1 스타일 (기존 스타일 수정)
        styles['Heading1'].fontName = self.font_name
        styles['Heading1'].fontSize = 16
        styles['Heading1'].textColor = colors.HexColor('#2c3e50')
        styles['Heading1'].spaceAfter = 12
        styles['Heading1'].spaceBefore = 12
        
        # 헤딩2 스타일 (기존 스타일 수정)
        styles['Heading2'].fontName = self.font_name
        styles['Heading2'].fontSize = 12
        styles['Heading2'].textColor = colors.HexColor('#34495e')
        styles['Heading2'].spaceAfter = 6
        styles['Heading2'].spaceBefore = 6
        
        # 일반 텍스트 스타일 (기존 스타일 수정)
        styles['Normal'].fontName = self.font_name
        styles['Normal'].fontSize = 10
        styles['Normal'].textColor = colors.HexColor('#333333')
        styles['Normal'].spaceAfter = 6
        styles['Normal'].alignment = TA_LEFT
        
        return styles
