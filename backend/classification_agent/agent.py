"""
Classification Agent
사용자 계약서의 유형을 5종 표준계약 중 하나로 분류
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple
from openai import AzureOpenAI
from backend.shared.core.celery_app import celery_app
from backend.shared.database import SessionLocal, ContractDocument, ClassificationResult

logger = logging.getLogger(__name__)


class ClassificationAgent:
    """
    계약서 분류 에이전트

    Phase 1: 간단한 RAG 기반 유사도 + LLM 판단
    - 5종 표준계약서 각각과 유사도 계산
    - LLM으로 최종 유형 판단
    """

    # 계약 유형 정의
    CONTRACT_TYPES = {
        "provide": "데이터 제공 계약",
        "create": "데이터 생성 계약",
        "process": "데이터 가공 계약",
        "brokerage_provider": "데이터 중개 계약 (제공자용)",
        "brokerage_user": "데이터 중개 계약 (이용자용)"
    }

    # Few-shot 예시 (JSON 출력 형식)
    FEWSHOT_EXAMPLES = """
예시 1: 데이터 제공형 (provide)
---
역할 구조: 데이터제공자가 자신이 보유한 데이터를 데이터이용자에게 제공하거나 접근 권한을 부여하고, 이용자는 그 대가를 지급한다.
핵심 패턴: "대상데이터 제공", "이용허락", "대가 지급", "비밀유지", "반환 또는 폐기"
특징: 새 데이터 생성 없음 (기존 데이터의 제공 중심)
추상 요약: 이미 존재하는 데이터를 일정 조건으로 이용하게 하는 계약. 제공자 → 이용자 방향의 데이터 흐름.

출력:
{
  "type": "provide",
  "confidence": 0.95,
  "reason": "데이터 제공 및 이용허락 구조 중심, 창출·가공 조항 부재"
}



예시 2: 데이터 생성형 (create)
---
역할 구조:
복수의 당사자가 공동으로 데이터를 생성하고, 생성된 데이터(대상데이터 및 파생데이터)의 이용권리, 귀속, 분배를 정한다.

핵심 패턴:
- “공동 생성”, “파생데이터”, “이용권리 귀속”, “이익분배”, “공동 저작권”
- 데이터 제공·이용보다 ‘창출’이 핵심
- 결과물의 소유권·지식재산권 조정이 중요함

추상 요약:
→ 여러 당사자가 협력하여 데이터를 새로 만드는 계약.
→ 데이터 흐름이 쌍방향이며 ‘공동 창작’ 중심.

출력:
{
  "type": "create",
  "confidence": "0.93",
  "reason": "공동 생성과 파생데이터 귀속, 이익분배 조항 존재"
}



예시 3: 데이터 가공형 (process)
---
역할 구조:
데이터이용자가 데이터를 제공하면, 데이터가공사업자가 이를 분석·정제·결합하여 가공데이터를 제작하고 납품한다.

핵심 패턴:
- “가공서비스”, “검수”, “하자보수”, “대가 지급”, “가공데이터 귀속”
- 원본 데이터를 입력받아 변형·분석·생성하는 행위
- 공급자는 ‘가공사업자’, 수요자는 ‘이용자’

추상 요약:
→ 원본 데이터를 입력받아 가공서비스를 수행하는 위탁형 계약.
→ 산출물은 ‘가공데이터’로 명시됨.

출력:
{
  "type": "process",
  "confidence": "0.96",
  "reason": "대상데이터 제공·가공·검수 및 하자보수 구조 명확"
}



예시 4: 데이터 중개형 - 제공자용 (brokerage_provider)
---
역할 구조:
플랫폼운영자가 데이터 거래 플랫폼을 운영하고, 데이터제공자가 그 플랫폼을 통해 데이터를 판매·유통한다.

핵심 패턴:
- “플랫폼운영자”, “정산”, “수수료”, “플랫폼서비스”, “광고·프로모션”
- 제공자는 거래 데이터 등록자, 운영자는 중개자
- “거래 제한”, “환불”, “청약철회 안내”, “정산 유보” 등이 등장

추상 요약:
→ 플랫폼을 매개로 데이터를 판매하는 제공자 중심 계약.
→ 수수료·정산 등 플랫폼 이용 조건 포함.

출력:
{
  "type": "brokerage_provider",
  "confidence": "0.94",
  "reason": "플랫폼 이용 조항과 정산·수수료 구조 명확, 제공자 중심"
}


예시 5: 데이터 중개형 - 이용자용 (brokerage_user)
---
역할 구조:
플랫폼운영자가 데이터 거래 플랫폼을 운영하고, 데이터제공자가 그 플랫폼을 통해 데이터를 판매·유통한다.

핵심 패턴:
- “플랫폼운영자”, “정산”, “수수료”, “플랫폼서비스”, “광고·프로모션”
- 제공자는 거래 데이터 등록자, 운영자는 중개자
- “거래 제한”, “환불”, “청약철회 안내”, “정산 유보” 등이 등장

추상 요약:
→ 플랫폼을 매개로 데이터를 판매하는 제공자 중심 계약.
→ 수수료·정산 등 플랫폼 이용 조건 포함.

출력:
{
  "type": "brokerage_user",
  "confidence": "0.94",
  "reason": "플랫폼 이용 조항과 정산·수수료 구조 명확, 제공자 중심"
}


"""

    # Gating threshold
    SCORE_GAP_THRESHOLD = 0.05  # 1위-2위 점수 차이 임계값

    def __init__(
        self,
        api_key: str = None,
        azure_endpoint: str = None,
        embedding_model: str = "text-embedding-3-large",
        chat_model: str = None,
        api_version: str = "2024-02-01"
    ):
        """
        Args:
            api_key: Azure OpenAI API 키
            azure_endpoint: Azure OpenAI 엔드포인트
            embedding_model: 임베딩 모델명
            chat_model: GPT 모델명
            api_version: API 버전
        """
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.embedding_model = embedding_model
        self.chat_model = chat_model or os.getenv("AZURE_LLM_DEPLOYMENT", "gpt-4o")

        if not self.api_key or not self.azure_endpoint:
            raise ValueError("Azure OpenAI 자격 증명이 필요합니다")

        self.client = AzureOpenAI(
            api_key=self.api_key,
            api_version=api_version,
            azure_endpoint=self.azure_endpoint
        )

        logger.info("ClassificationAgent 초기화 완료")

    def classify(
        self,
        contract_id: str,
        chunks_path: str,
        knowledge_base_loader
    ) -> Dict[str, Any]:
        """
        사용자 계약서 분류 (chunks.json 기반)

        Args:
            contract_id: 계약서 ID
            chunks_path: chunks.json 파일 경로
            knowledge_base_loader: 지식베이스 로더 인스턴스

        Returns:
            {
                "contract_id": str,
                "predicted_type": str,
                "confidence": float,
                "scores": dict,
                "reasoning": str
            }
        """
        try:
            logger.info(f"계약서 분류 시작: {contract_id}")

            # 1. chunks.json 로드
            import json
            with open(chunks_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            
            logger.info(f"청크 로드: {len(chunks)}개")

            # 2. 주요 청크 추출 (처음 10개)
            key_chunks = chunks[:10]

            # 3. 5종 표준계약서와 유사도 계산
            similarity_scores = self._calculate_similarity_scores_from_chunks(
                key_chunks,
                knowledge_base_loader
            )

            # 4. Hybrid Gating: 점수 차이에 따라 분류 방법 선택
            result = self._classify_with_gating(
                contract_id=contract_id,
                key_chunks=key_chunks,
                similarity_scores=similarity_scores
            )

            logger.info(f"분류 완료: {contract_id} -> {result['predicted_type']} (신뢰도: {result['confidence']:.2%})")
            return result

        except Exception as e:
            logger.error(f"분류 실패: {contract_id} - {e}")
            raise

    def _calculate_similarity_scores_from_chunks(
        self,
        key_chunks: List[Dict[str, Any]],
        knowledge_base_loader
    ) -> Dict[str, float]:
        """
        chunks 기반 유사도 계산

        Args:
            key_chunks: 주요 청크 리스트
            knowledge_base_loader: 지식베이스 로더

        Returns:
            유형별 유사도 점수
        """
        scores = {}

        # 주요 청크의 text_norm을 결합
        query_text = " ".join([chunk.get("text_norm", "") for chunk in key_chunks])
        query_embedding = self._get_embedding(query_text)

        # 각 유형별로 유사도 계산
        for contract_type in self.CONTRACT_TYPES.keys():
            try:
                # 지식베이스에서 해당 유형의 청크 로드
                chunks = knowledge_base_loader.load_chunks(contract_type)

                if not chunks:
                    logger.warning(f"청크가 없음: {contract_type}")
                    scores[contract_type] = 0.0
                    continue

                # 상위 N개 청크와 유사도 계산
                similarities = []
                for chunk in chunks[:20]:  # 상위 20개만 비교
                    chunk_embedding = chunk.get("embedding")
                    if chunk_embedding:
                        sim = self._cosine_similarity(query_embedding, chunk_embedding)
                        similarities.append(sim)

                # 평균 유사도
                avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
                scores[contract_type] = avg_similarity

            except Exception as e:
                logger.error(f"유사도 계산 실패: {contract_type} - {e}")
                scores[contract_type] = 0.0

        logger.debug(f"유사도 점수: {scores}")
        return scores

    def _calculate_similarity_scores(
        self,
        key_articles: List[Dict[str, str]],
        knowledge_base_loader
    ) -> Dict[str, float]:
        """
        5종 표준계약서와 유사도 계산

        Args:
            key_articles: 주요 조항 리스트
            knowledge_base_loader: 지식베이스 로더

        Returns:
            유형별 유사도 점수
        """
        scores = {}

        # 주요 조항 전체를 하나의 쿼리로 결합
        query_text = " ".join([art["full_text"] for art in key_articles])
        query_embedding = self._get_embedding(query_text)

        # 각 유형별로 유사도 계산
        for contract_type in self.CONTRACT_TYPES.keys():
            try:
                # 지식베이스에서 해당 유형의 청크 로드
                chunks = knowledge_base_loader.load_chunks(contract_type)

                if not chunks:
                    logger.warning(f"청크가 없음: {contract_type}")
                    scores[contract_type] = 0.0
                    continue

                # 상위 N개 청크와 유사도 계산
                similarities = []
                for chunk in chunks[:20]:  # 상위 20개만 비교
                    chunk_embedding = chunk.get("embedding")
                    if chunk_embedding:
                        sim = self._cosine_similarity(query_embedding, chunk_embedding)
                        similarities.append(sim)

                # 평균 유사도
                avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
                scores[contract_type] = avg_similarity

            except Exception as e:
                logger.error(f"유사도 계산 실패: {contract_type} - {e}")
                scores[contract_type] = 0.0

        logger.debug(f"유사도 점수: {scores}")
        return scores

    def _classify_with_gating(
        self,
        contract_id: str,
        key_chunks: List[Dict[str, Any]],
        similarity_scores: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Hybrid Gating 분류: 점수 차이에 따라 임베딩 또는 LLM 사용

        Args:
            contract_id: 계약서 ID
            key_chunks: 주요 청크
            similarity_scores: 유사도 점수

        Returns:
            분류 결과 딕셔너리
        """
        # 1위와 2위 점수 차이 계산
        sorted_scores = sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True)
        top1_type, top1_score = sorted_scores[0]
        top2_type, top2_score = sorted_scores[1]
        
        score_gap = top1_score - top2_score
        
        logger.info(f"유사도 점수 - 1위: {top1_type}({top1_score:.3f}), 2위: {top2_type}({top2_score:.3f}), gap: {score_gap:.3f}")
        
        # Gating 로직
        if score_gap >= self.SCORE_GAP_THRESHOLD:
            # 명확함 → 임베딩 결과 사용
            logger.info(f"✓ 임베딩 기반 결정 (gap={score_gap:.3f} >= {self.SCORE_GAP_THRESHOLD}): {top1_type}")
            
            return {
                "contract_id": contract_id,
                "predicted_type": top1_type,
                "confidence": top1_score,
                "scores": similarity_scores,
                "reasoning": f"임베딩 유사도 차이가 충분함 (gap={score_gap:.3f}). 1위: {self.CONTRACT_TYPES[top1_type]}",
                "classification_method": "embedding",
                "score_gap": score_gap
            }
        else:
            # 애매함 → LLM few-shot 판단
            logger.info(f"⚠ LLM 정밀 분류 필요 (gap={score_gap:.3f} < {self.SCORE_GAP_THRESHOLD})")
            
            predicted_type, confidence, reasoning = self._llm_classify_with_fewshot(
                key_chunks,
                similarity_scores
            )
            
            return {
                "contract_id": contract_id,
                "predicted_type": predicted_type,
                "confidence": confidence,
                "scores": similarity_scores,
                "reasoning": reasoning,
                "classification_method": "llm_fewshot",
                "score_gap": score_gap
            }

    def _llm_classify_with_fewshot(
        self,
        key_chunks: List[Dict[str, Any]],
        similarity_scores: Dict[str, float]
    ) -> Tuple[str, float, str]:
        """
        Few-shot 기반 LLM 분류 (역할-키워드 중심)

        Args:
            key_chunks: 주요 청크
            similarity_scores: 유사도 점수

        Returns:
            (predicted_type, confidence, reasoning)
        """
        # 청크에서 텍스트 추출
        chunks_text = "\n\n".join([
            f"[청크 {i+1}]\n제목: {chunk.get('title', '(제목 없음)')}\n내용: {chunk.get('text_norm', chunk.get('text_raw', ''))[:300]}..."
            for i, chunk in enumerate(key_chunks[:5])
        ])

        scores_text = "\n".join([
            f"- {self.CONTRACT_TYPES[t]}: {score:.3f}"
            for t, score in sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True)
        ])

        prompt = f"""당신은 데이터 계약서 분류 전문가입니다.

다음은 5가지 데이터 계약 유형의 특징과 출력 예시입니다:

{self.FEWSHOT_EXAMPLES}

---

이제 사용자가 업로드한 계약서의 주요 내용을 분석해주세요:

{chunks_text}

임베딩 유사도 점수 (참고용):
{scores_text}

**분석 지침**:
1. 역할 구조를 파악하세요 (제공자↔이용자, 위탁자↔수탁자, 중개자 포함 여부)
2. 핵심 패턴을 찾으세요:
   - 제공형: "대상데이터", "이용허락", "대가지급", "반환/폐기"
   - 생성형: "생성 의무", "제작", "납품", "검수"
   - 가공형: "가공 업무", "변환", "정제", "품질 기준"
   - 중개형: "중개", "플랫폼", "제공자/이용자로서"
3. 데이터 흐름 방향을 확인하세요 (제공, 생성, 가공, 중개)

**출력 형식** (반드시 JSON만 출력):
{{
  "type": "[provide|create|process|brokerage_provider|brokerage_user]",
  "confidence": [0.0-1.0],
  "reason": "[역할 구조와 핵심 패턴 기반 판단 근거]"
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "당신은 데이터 계약서 분류 전문가입니다. 역할 구조와 핵심 패턴을 중심으로 정확히 판단하고, 반드시 JSON 형식으로만 응답합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=600,
                response_format={"type": "json_object"}  # JSON 모드 강제
            )

            answer = response.choices[0].message.content.strip()
            logger.debug(f"LLM 응답:\n{answer}")

            # JSON 파싱
            import json
            try:
                result = json.loads(answer)
                predicted_type = result.get("type")
                confidence = float(result.get("confidence", 0.6))
                reasoning = result.get("reason", "")
                
                # 유효성 검증
                if predicted_type not in self.CONTRACT_TYPES:
                    raise ValueError(f"잘못된 유형: {predicted_type}")
                    
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"JSON 파싱 실패: {e}, 폴백 파싱 시도")
                # 폴백: 텍스트 파싱
                predicted_type = None
                confidence = 0.6
                reasoning = answer

                for line in answer.split("\n"):
                    if "type" in line.lower() or "유형" in line:
                        for t in self.CONTRACT_TYPES.keys():
                            if t in line:
                                predicted_type = t
                                break
                    elif "confidence" in line.lower() or "신뢰도" in line:
                        try:
                            import re
                            conf_match = re.search(r'0\.\d+', line)
                            if conf_match:
                                confidence = float(conf_match.group())
                        except:
                            pass
                    elif "reason" in line.lower() or "이유" in line:
                        reasoning = line.split(":", 1)[-1].strip()

            # 예외 처리: LLM이 유형을 명시하지 않은 경우
            if not predicted_type:
                predicted_type = max(similarity_scores.items(), key=lambda x: x[1])[0]
                confidence = max(similarity_scores.values())
                reasoning = f"LLM 파싱 실패. 최고 유사도 기반 분류: {reasoning}"
                logger.warning(f"LLM 응답 파싱 실패, 폴백 사용: {predicted_type}")

            return predicted_type, confidence, reasoning

        except Exception as e:
            logger.error(f"LLM 분류 실패: {e}")
            # Fallback: 유사도 기반
            predicted_type = max(similarity_scores.items(), key=lambda x: x[1])[0]
            confidence = max(similarity_scores.values())
            reasoning = f"LLM 호출 실패. 유사도 기반 분류."
            return predicted_type, confidence, reasoning

    def _llm_classify_from_chunks(
        self,
        key_chunks: List[Dict[str, Any]],
        similarity_scores: Dict[str, float]
    ) -> Tuple[str, float, str]:
        """
        청크 기반 LLM 분류 (레거시, 하위 호환용)

        Args:
            key_chunks: 주요 청크
            similarity_scores: 유사도 점수

        Returns:
            (predicted_type, confidence, reasoning)
        """
        # 청크를 조항 형식으로 변환
        key_articles = []
        for i, chunk in enumerate(key_chunks[:5]):  # 상위 5개만 사용
            key_articles.append({
                "number": str(i + 1),
                "title": chunk.get("title", ""),
                "content": chunk.get("text_norm", chunk.get("text_raw", ""))
            })
        
        # 기존 _llm_classify 메서드 호출
        return self._llm_classify(key_articles, similarity_scores)
    
    def _llm_classify(
        self,
        key_articles: List[Dict[str, str]],
        similarity_scores: Dict[str, float]
    ) -> Tuple[str, float, str]:
        """
        LLM으로 최종 분류

        Args:
            key_articles: 주요 조항
            similarity_scores: 유사도 점수

        Returns:
            (predicted_type, confidence, reasoning)
        """
        # 프롬프트 구성
        articles_text = "\n".join([
            f"제{art['number']}조 {art['title']}: {art['content'][:200]}..."
            for art in key_articles
        ])

        scores_text = "\n".join([
            f"- {self.CONTRACT_TYPES[t]}: {score:.3f}"
            for t, score in sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True)
        ])

        prompt = f"""다음은 사용자가 업로드한 계약서의 주요 조항입니다:

{articles_text}

5종 데이터 표준계약서와의 유사도 점수:
{scores_text}

위 정보를 바탕으로 이 계약서가 어떤 유형인지 판단해주세요.

가능한 유형:
1. provide: 데이터 제공 계약 (데이터 제공자 → 이용자)
2. create: 데이터 생성 계약 (데이터 생성 위탁)
3. process: 데이터 가공 계약 (데이터 가공 위탁)
4. brokerage_provider: 데이터 중개 계약 (제공자용)
5. brokerage_user: 데이터 중개 계약 (이용자용)

다음 형식으로 답변해주세요:
유형: [provide|create|process|brokerage_provider|brokerage_user]
신뢰도: [0.0-1.0 사이의 숫자]
이유: [간단한 판단 근거]
"""

        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "당신은 데이터 계약서 분류 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )

            answer = response.choices[0].message.content.strip()

            # 응답 파싱
            predicted_type = None
            confidence = 0.5
            reasoning = answer

            for line in answer.split("\n"):
                if line.startswith("유형:"):
                    type_text = line.split(":", 1)[1].strip()
                    for t in self.CONTRACT_TYPES.keys():
                        if t in type_text:
                            predicted_type = t
                            break
                elif line.startswith("신뢰도:"):
                    try:
                        conf_text = line.split(":", 1)[1].strip()
                        confidence = float(conf_text.split()[0])
                    except:
                        pass
                elif line.startswith("이유:"):
                    reasoning = line.split(":", 1)[1].strip()

            # 예외 처리: LLM이 유형을 명시하지 않은 경우
            if not predicted_type:
                # 가장 높은 유사도 점수의 유형 사용
                predicted_type = max(similarity_scores.items(), key=lambda x: x[1])[0]
                confidence = max(similarity_scores.values())
                reasoning = f"LLM 파싱 실패. 최고 유사도 기반 분류: {reasoning}"

            return predicted_type, confidence, reasoning

        except Exception as e:
            logger.error(f"LLM 분류 실패: {e}")
            # Fallback: 유사도 기반
            predicted_type = max(similarity_scores.items(), key=lambda x: x[1])[0]
            confidence = max(similarity_scores.values())
            reasoning = f"LLM 호출 실패. 유사도 기반 분류."
            return predicted_type, confidence, reasoning

    def _get_embedding(self, text: str) -> List[float]:
        """텍스트 임베딩 생성 (EmbeddingService 사용)"""
        try:
            from backend.shared.services import get_embedding_service
            
            embedding_service = get_embedding_service()
            embedding = embedding_service.get_embedding(text)
            
            if embedding is None:
                raise ValueError("임베딩 생성 실패")
            
            return embedding
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            raise

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """코사인 유사도 계산"""
        import numpy as np

        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))


# Celery Task 정의
@celery_app.task(name="classification.classify_contract", queue="classification")
def classify_contract_task(contract_id: str):
    """
    Celery Task: 계약서 분류

    Args:
        contract_id: 계약서 ID

    Returns:
        분류 결과
    """
    db = SessionLocal()
    try:
        logger.info(f"[Celery Task] 계약서 분류 시작: {contract_id}")

        # DB에서 계약서 조회
        contract = db.query(ContractDocument).filter(
            ContractDocument.contract_id == contract_id
        ).first()

        if not contract:
            raise ValueError(f"계약서를 찾을 수 없습니다: {contract_id}")

        # chunks.json 경로 가져오기
        chunks_path = contract.parsed_metadata.get("chunks_path")
        if not chunks_path:
            raise ValueError(f"chunks.json 경로가 없습니다: {contract_id}")
        
        if not Path(chunks_path).exists():
            raise ValueError(f"chunks.json 파일이 없습니다: {chunks_path}")

        # Classification Agent 실행
        agent = ClassificationAgent()
        from backend.shared.services import get_knowledge_base_loader
        kb_loader = get_knowledge_base_loader()

        result = agent.classify(
            contract_id=contract_id,
            chunks_path=chunks_path,
            knowledge_base_loader=kb_loader
        )

        # 분류 결과 DB 저장
        classification = ClassificationResult(
            contract_id=contract_id,
            predicted_type=result["predicted_type"],
            confidence=result["confidence"],
            scores=result["scores"],
            reasoning=result["reasoning"],
            confirmed_type=result["predicted_type"]
        )
        db.add(classification)

        # 계약서 상태 업데이트 (사용자 확인 대기)
        contract.status = "classified"
        db.commit()

        logger.info(f"[Celery Task] 분류 완료 및 저장: {contract_id}")
        logger.info(f"사용자 확인 대기 중... (분류 유형: {result['predicted_type']})")
        
        # 사용자가 /api/classification/{contract_id}/confirm 호출 후
        # /api/consistency/{contract_id}/start로 검증을 시작해야 함

        return {
            "success": True,
            "contract_id": contract_id,
            "predicted_type": result["predicted_type"],
            "confidence": result["confidence"]
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery Task] 분류 실패: {contract_id} - {e}")

        # 계약서 상태를 error로 업데이트
        contract = db.query(ContractDocument).filter(
            ContractDocument.contract_id == contract_id
        ).first()
        if contract:
            contract.status = "classification_error"
            db.commit()

        raise

    finally:
        db.close()
