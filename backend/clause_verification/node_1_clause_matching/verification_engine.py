"""
Contract Verification Engine

이 모듈은 표준 계약서와 사용자 계약서를 비교하여 누락된 조문을 식별하는
검증 엔진을 제공합니다.
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime
from collections import defaultdict
import numpy as np
import faiss

from .models import (
    ClauseData,
    MatchResult,
    VerificationResult,
    VerificationDecision
)
from .data_loader import ContractDataLoader
from .embedding_service import EmbeddingService
from .hybrid_search import HybridSearchEngine
from .llm_verification import LLMVerificationService
from .config import config

# Configure logging
logger = logging.getLogger(__name__)


class ContractVerificationEngine:
    """
    계약서 검증 엔진
    
    표준 계약서와 사용자 계약서를 비교하여 누락된 조문을 식별합니다.
    3단계 검증 프로세스를 사용합니다:
    1. BM25 키워드 검색
    2. FAISS 벡터 검색
    3. LLM 최종 검증
    
    Attributes:
        data_loader: 계약서 데이터 로더
        embedding_service: 임베딩 서비스
        hybrid_search: 하이브리드 검색 엔진
        llm_verification: LLM 검증 서비스
    """
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        hybrid_search: HybridSearchEngine,
        llm_verification: LLMVerificationService,
        data_loader: Optional[ContractDataLoader] = None
    ):
        """
        검증 엔진 초기화
        
        Args:
            embedding_service: 임베딩 서비스
            hybrid_search: 하이브리드 검색 엔진
            llm_verification: LLM 검증 서비스
            data_loader: 데이터 로더 (None인 경우 새로 생성)
        """
        self.embedding_service = embedding_service
        self.hybrid_search = hybrid_search
        self.llm_verification = llm_verification
        self.data_loader = data_loader or ContractDataLoader()
        
        logger.info("Contract Verification Engine initialized")
    
    def verify_contract_reverse(
        self,
        standard_clauses: List[ClauseData],
        user_clauses: List[ClauseData],
        top_k_candidates: int = 10,
        top_k_titles: int = 5,
        min_confidence: float = 0.5
    ) -> VerificationResult:
        """
        역방향 계약서 검증 수행 (조 단위 그룹화 + FAISS + LLM)
        
        사용자 계약서 각 조문에 대해 표준 계약서에서 매칭을 찾는 방식.
        표준 계약서를 조(title) 단위로 그룹화하여 효율적으로 검증.
        
        Args:
            standard_clauses: 표준 계약서 조문 리스트
            user_clauses: 사용자 계약서 조문 리스트
            top_k_candidates: FAISS 검색에서 반환할 후보 수 (기본값: 10)
            top_k_titles: LLM 검증할 조(title) 수 (기본값: 3)
            min_confidence: LLM 검증 최소 신뢰도 (기본값: 0.7)
        
        Returns:
            VerificationResult: 검증 결과
        """
        logger.info(
            f"Starting reverse contract verification: "
            f"{len(standard_clauses)} standard clauses, "
            f"{len(user_clauses)} user clauses"
        )
        
        # 1. 표준 계약서를 조(title) 단위로 그룹화
        logger.info("Grouping standard clauses by title...")
        standard_by_title = defaultdict(list)
        for clause in standard_clauses:
            standard_by_title[clause.title].append(clause)
        
        logger.info(f"Grouped into {len(standard_by_title)} titles from {len(standard_clauses)} clauses")
        
        # 2. 표준 계약서 임베딩 생성
        logger.info("Generating embeddings for standard clauses...")
        standard_clauses = self._embed_clauses(standard_clauses)
        
        # 3. FAISS 인덱스 구축
        logger.info("Building FAISS index...")
        embeddings_array = np.array([c.embedding for c in standard_clauses], dtype=np.float32)
        dimension = embeddings_array.shape[1]
        faiss_index = faiss.IndexFlatL2(dimension)
        faiss_index.add(embeddings_array)
        logger.info(f"FAISS index built with {len(standard_clauses)} clauses (dimension: {dimension})")
        
        # 4. 사용자 계약서 임베딩 생성
        logger.info("Generating embeddings for user clauses...")
        user_clauses = self._embed_clauses(user_clauses)
        
        # 5. 각 사용자 조문에 대해 매칭 찾기
        matched_titles = set()
        match_results = []
        duplicate_matches = []
        
        for i, user_clause in enumerate(user_clauses):
            logger.info(f"Verifying user clause {i+1}/{len(user_clauses)}: {user_clause.id}")
            
            # FAISS로 top-k 후보 찾기
            query_vector = np.array([user_clause.embedding], dtype=np.float32)
            distances, indices = faiss_index.search(query_vector, k=top_k_candidates)
            
            # 후보들을 조(title) 단위로 그룹화
            candidates_by_title = defaultdict(list)
            for idx, distance in zip(indices[0], distances[0]):
                candidate = standard_clauses[idx]
                similarity = 1.0 / (1.0 + float(distance))
                candidates_by_title[candidate.title].append({
                    'clause': candidate,
                    'similarity': similarity,
                    'distance': float(distance)
                })
            
            # 각 조(title)의 대표 후보 선택 (가장 유사도 높은 항)
            title_candidates = []
            for title, candidates in candidates_by_title.items():
                best_candidate = max(candidates, key=lambda x: x['similarity'])
                title_candidates.append({
                    'title': title,
                    'clause': best_candidate['clause'],
                    'similarity': best_candidate['similarity']
                })
            
            # 유사도 순으로 정렬
            title_candidates.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Top-k 조(title)에 대해 LLM 검증
            best_match = None
            best_match_result = None
            candidate_results = []  # 모든 후보의 결과 저장
            
            for candidate_info in title_candidates[:top_k_titles]:
                candidate = candidate_info['clause']
                candidate_title = candidate_info['title']
                
                # 이미 매칭된 표준 조문인지 확인
                if candidate_title in matched_titles:
                    # 중복 매칭 시도 감지
                    logger.warning(
                        f"Duplicate match attempt: {user_clause.id} -> {candidate_title} "
                        f"(already matched)"
                    )
                    
                    # LLM 검증은 수행하여 중복 매칭 정보 기록
                    llm_decision = self.llm_verification.verify_clause_match(
                        standard_clause=candidate,
                        candidate_clause=user_clause
                    )
                    
                    if llm_decision.is_match and llm_decision.confidence >= min_confidence:
                        # 중복 매칭 결과 생성
                        duplicate_result = MatchResult(
                            standard_clause=candidate,
                            matched_clause=user_clause,
                            bm25_score=0.0,
                            faiss_score=candidate_info['similarity'],
                            hybrid_score=candidate_info['similarity'],
                            llm_decision=llm_decision,
                            is_matched=False,  # 중복이므로 매칭으로 카운트하지 않음
                            is_duplicate=True,
                            duplicate_reason=f"표준 조문 '{candidate_title}'이(가) 이미 다른 사용자 조문과 매칭됨"
                        )
                        duplicate_matches.append(duplicate_result)
                        logger.info(
                            f"Duplicate match recorded: {user_clause.id} -> {candidate_title} "
                            f"(confidence: {llm_decision.confidence:.2f})"
                        )
                    
                    # 다음 후보로 계속
                    continue
                
                # LLM 검증
                llm_decision = self.llm_verification.verify_clause_match(
                    standard_clause=candidate,
                    candidate_clause=user_clause
                )
                
                # 매칭 결과 생성
                match_result = MatchResult(
                    standard_clause=candidate,
                    matched_clause=user_clause,
                    bm25_score=0.0,
                    faiss_score=candidate_info['similarity'],
                    hybrid_score=candidate_info['similarity'],
                    llm_decision=llm_decision,
                    is_matched=llm_decision.is_match and llm_decision.confidence >= min_confidence
                )
                
                # 모든 후보 결과 저장
                candidate_results.append(match_result)
                
                if match_result.is_matched:
                    best_match = candidate_title
                    best_match_result = match_result
                    matched_titles.add(candidate_title)
                    logger.info(
                        f"Match found: {user_clause.id} -> {candidate.title} "
                        f"(confidence: {llm_decision.confidence:.2f})"
                    )
                    break
            
            # 매칭 성공 시: 매칭된 결과만 저장
            # 매칭 실패 시: Top-3 후보 결과 모두 저장 (LLM 판단 근거 포함)
            if best_match:
                # 매칭 성공 - 매칭된 결과만 저장
                match_results.append(best_match_result)
            elif candidate_results:
                # 매칭 실패 - Top-3 후보 모두 저장
                for result in candidate_results[:3]:
                    match_results.append(result)
            
            if not best_match:
                logger.warning(f"No match found for user clause: {user_clause.id}")
        
        # 6. 누락된 조문 식별 (표준 계약서 기준)
        logger.info("Identifying missing clauses...")
        missing_clauses = []
        
        for title, clauses in standard_by_title.items():
            if title not in matched_titles:
                # 해당 조의 모든 항을 누락으로 표시
                for clause in clauses:
                    missing_clauses.append(clause)
                    # 누락된 조문에 대한 MatchResult 생성
                    match_results.append(MatchResult(
                        standard_clause=clause,
                        matched_clause=None,
                        bm25_score=0.0,
                        faiss_score=0.0,
                        hybrid_score=0.0,
                        llm_decision=None,
                        is_matched=False
                    ))
        
        # 7. 검증 결과 생성
        matched_title_count = len(matched_titles)  # 매칭된 조의 개수 (조 단위)
        matched_clause_count = len(match_results)  # 매칭된 항의 개수 (항 단위)
        
        result = VerificationResult(
            total_standard_clauses=len(standard_by_title),  # 조 단위 개수
            matched_clauses=matched_title_count,  # 조 단위로 수정
            missing_clauses=missing_clauses,
            match_results=match_results,
            duplicate_matches=duplicate_matches,
            total_user_clauses=len(user_clauses),
            verification_date=datetime.now()
        )
        
        logger.info(
            f"Reverse verification completed: "
            f"{matched_title_count}/{len(standard_by_title)} titles matched, "
            f"{matched_clause_count} clause matches found, "
            f"{len(missing_clauses)} clauses missing, "
            f"{len(duplicate_matches)} duplicate matches detected"
        )
        
        return result
    
    def verify_contract(
        self,
        standard_clauses: List[ClauseData],
        user_clauses: List[ClauseData],
        top_k_candidates: int = 3,
        min_confidence: float = 0.7
    ) -> VerificationResult:
        """
        계약서 검증 수행 (3단계 프로세스)
        
        각 표준 조문에 대해:
        1. 하이브리드 검색으로 top-k 후보 찾기
        2. LLM으로 각 후보의 의미적 일치 여부 검증
        3. 매칭 성공 시 다음 조문으로, 실패 시 누락으로 표시
        
        Args:
            standard_clauses: 표준 계약서 조문 리스트
            user_clauses: 사용자 계약서 조문 리스트
            top_k_candidates: 하이브리드 검색에서 반환할 후보 수 (기본값: 3)
            min_confidence: LLM 검증 최소 신뢰도 (기본값: 0.7)
        
        Returns:
            VerificationResult: 검증 결과
        """
        logger.info(
            f"Starting contract verification: "
            f"{len(standard_clauses)} standard clauses, "
            f"{len(user_clauses)} user clauses"
        )
        
        # 1. 사용자 계약서 조문에 임베딩 생성
        logger.info("Generating embeddings for user clauses...")
        user_clauses = self._embed_clauses(user_clauses)
        
        # 2. 하이브리드 검색 인덱스 구축 (표준 조문으로 - 이미 로드됨)
        # 인덱스는 이미 표준 조문으로 빌드되어 있음 (FAISS는 로드됨, BM25는 초기화 시 빌드됨)
        logger.info("Using pre-built search indices for standard clauses...")
        
        # 3. 각 사용자 조문에 대해 표준 조문 검색
        match_results = []
        matched_standard_ids = set()  # 이미 매칭된 표준 조문 추적
        matched_count = 0
        
        for i, user_clause in enumerate(user_clauses):
            logger.info(
                f"Searching for user clause {i+1}/{len(user_clauses)}: "
                f"{user_clause.id}"
            )
            
            # 하이브리드 검색으로 표준 조문 후보 찾기
            search_results = self.hybrid_search.search(
                query_text=user_clause.text_norm,
                query_embedding=user_clause.embedding,
                top_k=top_k_candidates
            )
            
            # LLM으로 각 표준 조문 후보 검증
            match_found = False
            best_match_result = None
            
            for standard_idx, hybrid_score, bm25_score, faiss_score, bm25_raw, faiss_dist in search_results:
                standard_candidate = self.hybrid_search.get_clause_by_index(standard_idx)
                
                # 이미 매칭된 표준 조문은 스킵
                if standard_candidate.id in matched_standard_ids:
                    continue
                
                # LLM 검증 (표준 조문과 사용자 조문 비교)
                llm_decision = self.llm_verification.verify_clause_match(
                    standard_clause=standard_candidate,
                    candidate_clause=user_clause
                )
                
                # 매칭 결과 생성
                match_result = MatchResult(
                    standard_clause=standard_candidate,
                    matched_clause=user_clause,
                    bm25_score=bm25_score,
                    faiss_score=faiss_score,
                    hybrid_score=hybrid_score,
                    bm25_raw_score=bm25_raw,
                    faiss_raw_distance=faiss_dist,
                    llm_decision=llm_decision,
                    is_matched=llm_decision.is_match and llm_decision.confidence >= min_confidence
                )
                
                # 첫 번째 매칭 성공 시 저장하고 다음 사용자 조문으로
                if match_result.is_matched:
                    match_found = True
                    best_match_result = match_result
                    matched_standard_ids.add(standard_candidate.id)
                    matched_count += 1
                    logger.info(
                        f"Match found: {standard_candidate.id} <- {user_clause.id} "
                        f"(confidence: {llm_decision.confidence:.2f})"
                    )
                    break
                
                # 첫 번째 후보 결과는 저장 (매칭 실패해도)
                if best_match_result is None:
                    best_match_result = match_result
            
            # 매칭 결과 저장 (성공 또는 실패)
            if best_match_result is not None:
                match_results.append(best_match_result)
        
        # 4. 누락된 조문 식별 (매칭되지 않은 표준 조문)
        missing_clauses = [
            clause for clause in standard_clauses
            if clause.id not in matched_standard_ids
        ]
        
        # 5. 검증 결과 생성
        result = VerificationResult(
            total_standard_clauses=len(standard_clauses),
            total_user_clauses=len(user_clauses),
            matched_clauses=matched_count,
            missing_clauses=missing_clauses,
            match_results=match_results,
            verification_date=datetime.now()
        )
        
        logger.info(
            f"Verification completed: "
            f"{matched_count}/{len(standard_clauses)} clauses matched, "
            f"{len(missing_clauses)} missing"
        )
        
        return result
    
    def identify_missing_clauses(
        self,
        standard_clauses: List[ClauseData],
        user_clauses: List[ClauseData],
        match_results: List[MatchResult]
    ) -> List[ClauseData]:
        """
        누락된 조문 식별
        
        Args:
            standard_clauses: 표준 계약서 조문 리스트
            user_clauses: 사용자 계약서 조문 리스트
            match_results: 매칭 결과 리스트
        
        Returns:
            누락된 조문 리스트
        """
        missing_clauses = []
        
        for match_result in match_results:
            if not match_result.is_matched:
                missing_clauses.append(match_result.standard_clause)
        
        logger.info(f"Identified {len(missing_clauses)} missing clauses")
        
        return missing_clauses
    
    def _embed_clauses(self, clauses: List[ClauseData]) -> List[ClauseData]:
        """
        조문 리스트에 임베딩 생성 (이미 있으면 스킵)
        
        Args:
            clauses: 조문 리스트
        
        Returns:
            임베딩이 추가된 조문 리스트
        """
        # 임베딩이 없는 조문만 필터링
        clauses_without_embedding = [c for c in clauses if c.embedding is None]
        
        if not clauses_without_embedding:
            logger.info("All clauses already have embeddings, skipping embedding generation")
            return clauses
        
        logger.info(f"Generating embeddings for {len(clauses_without_embedding)} clauses (skipping {len(clauses) - len(clauses_without_embedding)} with existing embeddings)")
        
        # 세그먼트 기법 적용: text_norm 사용 (// 구분자 포함)
        texts = [clause.text_norm or clause.text for clause in clauses_without_embedding]
        embeddings = self.embedding_service.embed_batch(texts)
        
        for clause, embedding in zip(clauses_without_embedding, embeddings):
            clause.embedding = embedding
        
        return clauses
    
    def load_and_verify(
        self,
        standard_contract_path: Optional[str] = None,
        user_contract_text: Optional[str] = None,
        user_contract_path: Optional[str] = None,
        filter_type: str = "조",
        top_k_candidates: int = 10,
        top_k_titles: int = 3,
        min_confidence: float = 0.5,
        use_reverse: bool = True
    ) -> VerificationResult:
        """
        계약서 로드 및 검증을 한 번에 수행하는 편의 메서드
        
        Args:
            standard_contract_path: 표준 계약서 경로 (None인 경우 config 사용)
            user_contract_text: 사용자 계약서 텍스트 (우선순위 높음)
            user_contract_path: 사용자 계약서 파일 경로
            filter_type: 필터링할 조문 타입 (기본값: "조")
            top_k_candidates: FAISS 검색 후보 수 (기본값: 10)
            top_k_titles: LLM 검증할 조 수 (기본값: 3)
            min_confidence: LLM 검증 최소 신뢰도
            use_reverse: 역방향 검증 사용 여부 (기본값: True)
        
        Returns:
            VerificationResult: 검증 결과
        
        Raises:
            ValueError: 사용자 계약서가 제공되지 않은 경우
        """
        # 1. 표준 계약서 로드
        logger.info("Loading standard contract...")
        if standard_contract_path:
            from pathlib import Path
            standard_clauses = self.data_loader.load_standard_contract(
                Path(standard_contract_path)
            )
        else:
            standard_clauses = self.data_loader.load_standard_contract()
        
        # 조문 타입 필터링
        standard_clauses = self.data_loader.filter_clauses(
            standard_clauses,
            clause_type=filter_type
        )
        
        # 2. 사용자 계약서 로드
        logger.info("Loading user contract...")
        if user_contract_text:
            user_clauses = self.data_loader.load_user_contract_from_text(
                user_contract_text
            )
        elif user_contract_path:
            from pathlib import Path
            user_clauses = self.data_loader.load_user_contract_from_file(
                Path(user_contract_path)
            )
        else:
            raise ValueError(
                "Either user_contract_text or user_contract_path must be provided"
            )
        
        # 3. 검증 수행 (역방향 또는 정방향)
        if use_reverse:
            return self.verify_contract_reverse(
                standard_clauses=standard_clauses,
                user_clauses=user_clauses,
                top_k_candidates=top_k_candidates,
                top_k_titles=top_k_titles,
                min_confidence=min_confidence
            )
        else:
            return self.verify_contract(
                standard_clauses=standard_clauses,
                user_clauses=user_clauses,
                top_k_candidates=top_k_candidates,
                min_confidence=min_confidence
            )
