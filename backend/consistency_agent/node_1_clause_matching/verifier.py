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
from backend.shared.services.embedding_service import EmbeddingService
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
        
        for i, user_clause in enumerate(user_clauses):
            logger.info(f"Verifying user clause {i+1}/{len(user_clauses)}: {user_clause.id}")
            
            # FAISS로 top-k 후보 찾기 (항 단위)
            query_vector = np.array([user_clause.embedding], dtype=np.float32)
            distances, indices = faiss_index.search(query_vector, k=top_k_candidates)
            
            # 후보 항들을 유사도 순으로 정리
            candidates = []
            for idx, distance in zip(indices[0], distances[0]):
                candidate = standard_clauses[idx]
                similarity = 1.0 / (1.0 + float(distance))
                candidates.append({
                    'clause': candidate,
                    'similarity': similarity,
                    'distance': float(distance)
                })
            
            # Top-k 항에 대해 LLM 배치 검증 (한 번에 여러 후보 검증)
            candidate_results = []  # 모든 후보의 결과 저장
            matched_count_for_user = 0
            
            # 배치 검증용 후보 준비
            batch_candidates = [
                (candidate_info['clause'], candidate_info['similarity'])
                for candidate_info in candidates[:top_k_titles]
            ]
            
            # 배치 LLM 검증 (한 번의 API 호출로 모든 후보 검증)
            llm_decisions = self.llm_verification.verify_clause_match_batch(
                user_clause=user_clause,
                standard_candidates=batch_candidates,
                min_confidence=min_confidence
            )
            
            # 배치 결과 처리
            for candidate_info, llm_decision in zip(candidates[:top_k_titles], llm_decisions):
                candidate = candidate_info['clause']
                candidate_id = candidate.id
                
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
                
                # 매칭 성공 시 처리 (여러 개 가능)
                if match_result.is_matched:
                    matched_titles.add(candidate_id)
                    matched_count_for_user += 1
                    logger.info(
                        f"Match found: {user_clause.id} -> {candidate.id} "
                        f"(confidence: {llm_decision.confidence:.2f})"
                    )
            
            # 매칭된 후보가 있으면 첫 번째를 대표로 저장
            best_match_result = next(
                (r for r in candidate_results if r.is_matched),
                None
            )
            
            # 매칭 성공 시: 매칭된 결과만 저장
            # 매칭 실패 시: Top-3 후보 결과 모두 저장 (LLM 판단 근거 포함)
            if best_match_result:
                # 매칭 성공 - 매칭된 결과만 저장
                match_results.append(best_match_result)
            elif candidate_results:
                # 매칭 실패 - Top-3 후보 모두 저장
                for result in candidate_results[:3]:
                    match_results.append(result)
            
            if not best_match_result:
                logger.warning(f"No match found for user clause: {user_clause.id}")
        
        # 6. 누락된 조문 식별 (표준 계약서 기준 - 항 단위)
        logger.info("Identifying missing clauses...")
        missing_clauses = []
        
        # 매칭된 표준 항 ID 세트
        matched_standard_ids = set(matched_titles)
        
        # 모든 표준 항을 확인하여 매칭되지 않은 항 찾기
        for std_clause in standard_clauses:
            if std_clause.id not in matched_standard_ids:
                missing_clauses.append(std_clause)
                # 누락된 조문에 대한 MatchResult 생성
                match_results.append(MatchResult(
                    standard_clause=std_clause,
                    matched_clause=None,
                    bm25_score=0.0,
                    faiss_score=0.0,
                    hybrid_score=0.0,
                    llm_decision=None,
                    is_matched=False
                ))
        
        # 7. 매칭 안 된 사용자 조문 식별 및 분석
        logger.info("Identifying unmatched user clauses...")
        matched_user_ids = set(
            r.matched_clause.id for r in match_results 
            if r.is_matched and r.matched_clause
        )
        logger.info(f"Total user clauses: {len(user_clauses)}, Matched user IDs: {len(matched_user_ids)}")
        logger.info(f"Expected unmatched: {len(user_clauses) - len(matched_user_ids)}")
        
        unmatched_user_clauses = self._find_unmatched_user_clauses(
            user_clauses=user_clauses,
            matched_user_ids=matched_user_ids,
            standard_clauses=standard_clauses
        )
        
        # 8. 정방향 검증 (누락 조문 재검증)
        logger.info("Performing forward verification for missing clauses...")
        missing_clause_analysis = self._verify_missing_clauses_forward(
            missing_clauses=missing_clauses,
            user_clauses=user_clauses,
            faiss_index=faiss_index,
            standard_clauses=standard_clauses
        )
        
        # 9. 검증 결과 생성
        matched_clause_count = len(matched_standard_ids)  # 매칭된 항의 개수
        
        result = VerificationResult(
            total_standard_clauses=len(standard_clauses),  # 표준 계약서 전체 항 개수
            matched_clauses=matched_clause_count,  # 매칭된 항 개수
            missing_clauses=missing_clauses,
            match_results=match_results,
            duplicate_matches=[],  # 중복 체크 제거
            unmatched_user_clauses=unmatched_user_clauses,
            missing_clause_analysis=missing_clause_analysis,
            total_user_clauses=len(user_clauses),
            verification_date=datetime.now()
        )
        
        logger.info(
            f"Reverse verification completed: "
            f"{matched_clause_count}/{len(standard_clauses)} clauses matched, "
            f"{len(missing_clauses)} clauses missing, "
            f"{len(unmatched_user_clauses)} unmatched user clauses"
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
        
        # 5. 매칭 안 된 사용자 조문 식별 및 분석
        logger.info("Identifying unmatched user clauses...")
        matched_user_ids = set(
            r.matched_clause.id for r in match_results 
            if r.is_matched and r.matched_clause
        )
        unmatched_user_clauses = self._find_unmatched_user_clauses(
            user_clauses=user_clauses,
            matched_user_ids=matched_user_ids,
            standard_clauses=standard_clauses
        )
        
        # 6. 검증 결과 생성
        result = VerificationResult(
            total_standard_clauses=len(standard_clauses),
            total_user_clauses=len(user_clauses),
            matched_clauses=matched_count,
            missing_clauses=missing_clauses,
            match_results=match_results,
            unmatched_user_clauses=unmatched_user_clauses,
            verification_date=datetime.now()
        )
        
        logger.info(
            f"Verification completed: "
            f"{matched_count}/{len(standard_clauses)} clauses matched, "
            f"{len(missing_clauses)} missing from standard, "
            f"{len(unmatched_user_clauses)} unmatched user clauses"
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
        세그먼트 기법: text_norm에 // 구분자가 있으면 분할하여 평균 임베딩 생성
        
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
        
        # 세그먼트 기법 적용: text_norm에 // 구분자가 있으면 분할
        for clause in clauses_without_embedding:
            text_norm = clause.text_norm or clause.text
            
            # // 구분자로 세그먼트 분할
            if '//' in text_norm:
                segments = [seg.strip() for seg in text_norm.split('//') if seg.strip()]
                
                if len(segments) > 1:
                    # 각 세그먼트를 개별 임베딩
                    logger.info(f"✅ Clause {clause.id}: {len(segments)} segments found - applying segment embedding")
                    segment_embeddings = self.embedding_service.embed_batch(segments)
                    
                    # 평균 임베딩 계산
                    valid_embeddings = [emb for emb in segment_embeddings if emb is not None]
                    if valid_embeddings:
                        clause.embedding = np.mean(valid_embeddings, axis=0)
                        logger.info(f"✅ Clause {clause.id}: averaged {len(valid_embeddings)} segment embeddings")
                    else:
                        # 세그먼트 임베딩 실패 시 전체 텍스트로 임베딩
                        clause.embedding = self.embedding_service.generate_embedding(text_norm)
                else:
                    # 세그먼트가 1개만 있으면 그대로 임베딩
                    clause.embedding = self.embedding_service.generate_embedding(text_norm)
            else:
                # // 구분자가 없으면 그대로 임베딩
                clause.embedding = self.embedding_service.generate_embedding(text_norm)
        
        return clauses
    
    def _find_unmatched_user_clauses(
        self,
        user_clauses: List[ClauseData],
        matched_user_ids: set,
        standard_clauses: List[ClauseData]
    ) -> List:
        """
        매칭되지 않은 사용자 조문을 찾고 가장 유사한 표준 조문을 찾음
        
        Args:
            user_clauses: 사용자 계약서 조문 리스트
            matched_user_ids: 이미 매칭된 사용자 조문 ID 집합
            standard_clauses: 표준 계약서 조문 리스트
        
        Returns:
            UnmatchedUserClause 객체 리스트
        """
        from backend.shared.models import UnmatchedUserClause
        
        unmatched_results = []
        
        # FAISS 인덱스 구축 (표준 조문으로)
        embeddings_array = np.array([c.embedding for c in standard_clauses], dtype=np.float32)
        dimension = embeddings_array.shape[1]
        faiss_index = faiss.IndexFlatL2(dimension)
        faiss_index.add(embeddings_array)
        
        for user_clause in user_clauses:
            # 이미 매칭된 조문은 스킵
            if user_clause.id in matched_user_ids:
                continue
            
            # 가장 유사한 표준 조문 찾기 (FAISS 사용)
            try:
                query_vector = np.array([user_clause.embedding], dtype=np.float32)
                distances, indices = faiss_index.search(query_vector, k=1)
                
                if len(indices[0]) > 0:
                    idx = indices[0][0]
                    distance = distances[0][0]
                    closest_standard = standard_clauses[idx]
                    similarity = 1.0 / (1.0 + float(distance))
                    
                    unmatched_results.append(UnmatchedUserClause(
                        user_clause=user_clause,
                        closest_standard=closest_standard,
                        similarity_score=similarity
                    ))
                    
                    logger.debug(
                        f"Unmatched user clause {user_clause.id} - "
                        f"closest: {closest_standard.id} (score: {similarity:.2f})"
                    )
                else:
                    # 검색 결과가 없는 경우
                    unmatched_results.append(UnmatchedUserClause(
                        user_clause=user_clause,
                        closest_standard=None,
                        similarity_score=0.0
                    ))
                    
            except Exception as e:
                logger.warning(f"Error finding closest standard for {user_clause.id}: {e}")
                unmatched_results.append(UnmatchedUserClause(
                    user_clause=user_clause,
                    closest_standard=None,
                    similarity_score=0.0
                ))
        
        logger.info(f"Found {len(unmatched_results)} unmatched user clauses")
        return unmatched_results
    
    def _verify_missing_clauses_forward(
        self,
        missing_clauses: List[ClauseData],
        user_clauses: List[ClauseData],
        faiss_index,
        standard_clauses: List[ClauseData]
    ) -> List:
        """
        누락된 표준 조문을 정방향으로 재검증 (FAISS Top-3 + LLM 분석)
        
        Args:
            missing_clauses: 역방향에서 매칭 안 된 표준 조문들
            user_clauses: 사용자 계약서 조문 리스트
            faiss_index: 표준 조문 FAISS 인덱스 (사용 안 함)
            standard_clauses: 표준 계약서 조문 리스트 (사용 안 함)
        
        Returns:
            MissingClauseAnalysis 객체 리스트
        """
        from backend.shared.models import MissingClauseAnalysis
        
        analysis_results = []
        
        # 사용자 조문으로 FAISS 인덱스 구축
        user_embeddings = np.array([c.embedding for c in user_clauses], dtype=np.float32)
        user_faiss_index = faiss.IndexFlatL2(user_embeddings.shape[1])
        user_faiss_index.add(user_embeddings)
        
        logger.info(f"Starting forward verification for {len(missing_clauses)} missing clauses...")
        
        for i, missing_clause in enumerate(missing_clauses):
            logger.info(f"Forward verifying missing clause {i+1}/{len(missing_clauses)}: {missing_clause.id}")
            
            # 정방향 검색: 표준 조문 → 사용자 조문 (Top-3)
            query_vector = np.array([missing_clause.embedding], dtype=np.float32)
            distances, indices = user_faiss_index.search(query_vector, k=3)
            
            # Top-3 후보 수집
            top3_candidates = []
            for idx, distance in zip(indices[0], distances[0]):
                candidate = user_clauses[idx]
                similarity = 1.0 / (1.0 + float(distance))
                top3_candidates.append({
                    'clause': candidate,
                    'similarity': similarity,
                    'distance': float(distance)
                })
            
            # LLM으로 Top-3 배치 검증
            candidates_for_llm = [
                (candidate_info['clause'], candidate_info['similarity'])
                for candidate_info in top3_candidates
            ]
            
            batch_result = self.llm_verification.verify_missing_clause_forward_batch(
                standard_clause=missing_clause,
                user_candidates=candidates_for_llm
            )
            
            # 배치 결과를 개별 결과로 변환
            llm_results = []
            for i, candidate_info in enumerate(top3_candidates):
                candidate = candidate_info['clause']
                batch_candidate = batch_result['candidates'][i] if i < len(batch_result['candidates']) else None
                
                if batch_candidate:
                    llm_decision = VerificationDecision(
                        is_match=batch_candidate.get('is_match', False),
                        confidence=batch_candidate.get('confidence', 0.0),
                        reasoning=batch_candidate.get('reasoning', ''),
                        recommendation=batch_candidate.get('recommendation', None)
                    )
                else:
                    llm_decision = VerificationDecision(
                        is_match=False,
                        confidence=0.0,
                        reasoning="배치 검증 결과 없음",
                        recommendation=None
                    )
                
                llm_results.append({
                    'candidate': candidate,
                    'similarity': candidate_info['similarity'],
                    'llm_decision': llm_decision
                })
                
                logger.debug(
                    f"  Candidate {candidate.id}: "
                    f"similarity={candidate_info['similarity']:.3f}, "
                    f"match={llm_decision.is_match}, "
                    f"confidence={llm_decision.confidence:.2f}"
                )
            
            # 근거, 리스크, 권고 생성 (배치 summary 포함)
            evidence, risk_assessment, recommendation = \
                self._analyze_missing_clause_with_llm(
                    missing_clause=missing_clause,
                    llm_results=llm_results,
                    batch_summary=batch_result.get('summary', ''),
                    overall_risk=batch_result.get('overall_risk', '')
                )
            
            # 가장 유사한 후보 선택 (LLM 신뢰도 기준)
            best_candidate = max(llm_results, key=lambda x: x['llm_decision'].confidence)
            
            analysis_results.append(MissingClauseAnalysis(
                standard_clause=missing_clause,
                closest_user=best_candidate['candidate'],
                forward_similarity=best_candidate['similarity'],
                recommendation=recommendation,
                evidence=evidence,
                risk_assessment=risk_assessment,
                top3_candidates=llm_results  # Top-3 후보 모두 저장
            ))
            
            logger.info(
                f"  Analysis complete for {missing_clause.id}, "
                f"best_candidate={best_candidate['candidate'].id}"
            )
        
        logger.info(f"Forward verification completed for {len(missing_clauses)} missing clauses")
        return analysis_results
    
    def _analyze_missing_clause_with_llm(
        self,
        missing_clause: ClauseData,
        llm_results: List[Dict],
        batch_summary: str = "",
        overall_risk: str = ""
    ) -> tuple:
        """
        LLM 결과를 기반으로 누락 조문 분석
        
        Args:
            missing_clause: 누락된 표준 조문
            llm_results: Top-3 후보에 대한 LLM 검증 결과
            batch_summary: 배치 검증 종합 분석
            overall_risk: 전체 위험 평가
        
        Returns:
            (evidence, risk_assessment, recommendation)
        """
        # 가장 높은 신뢰도의 결과 찾기
        best_result = max(llm_results, key=lambda x: x['llm_decision'].confidence)
        
        # 1. 근거 (Evidence) 생성 - 자연스러운 문단 형식
        evidence_parts = []
        
        # 배치 summary를 먼저 추가 (전체 맥락 제공)
        if batch_summary:
            evidence_parts.append(f"{batch_summary}\n")
        
        # Top-3 후보 상세 분석
        evidence_parts.append(f"\n**상세 분석 (Top-3 유사 조문):**\n")
        
        for i, result in enumerate(llm_results, 1):
            candidate = result['candidate']
            similarity = result['similarity']
            llm_decision = result['llm_decision']
            
            evidence_parts.append(f"\n{i}. 사용자 조문 '{candidate.id}' (유사도: {similarity:.2f})")
            evidence_parts.append(f"\n   {llm_decision.reasoning}")
        
        evidence = "".join(evidence_parts)
        
        # 2. Risk Assessment - overall_risk 사용 (시나리오 형식)
        risk_assessment = overall_risk if overall_risk else (
            f"이 조항이 없으면 계약 이행 과정에서 불명확성이 발생할 수 있습니다."
        )
        
        # 3. Recommendation - LLM 결과에서 추출 (가장 높은 신뢰도 결과 사용)
        recommendation = best_result['llm_decision'].recommendation if best_result['llm_decision'].recommendation else (
            f"'{missing_clause.title}' 조항을 추가할 것을 권장합니다."
        )
        
        return evidence, risk_assessment, recommendation

    
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
        
        # 별지 참조 병합 (필터링 전에 수행)
        logger.info("Merging exhibit references...")
        standard_clauses = self.data_loader.merge_exhibit_references(standard_clauses)
        
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
