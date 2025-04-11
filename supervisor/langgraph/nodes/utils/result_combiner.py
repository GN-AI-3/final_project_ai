"""
결과 통합 노드
주 에이전트와 보조 에이전트 결과를 통합하는 노드 함수
중요 메시지를 분류하고 Qdrant에 저장하는 기능 추가
"""

import logging
import traceback
import time
import json
import os
from typing import Dict, Any, List, Optional, Tuple
from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models
from dotenv import load_dotenv
from supervisor.langgraph.state import GymGGunState

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logger = logging.getLogger('supervisor.langgraph.nodes.utils.result_combiner')

# Qdrant와 Sentence Transformer 초기화
try:
    # Qdrant 클라이언트 초기화 - 로그 추가 
    logger.info("Qdrant 클라이언트 초기화 시작...")
    
    # API 키 확인 및 로깅
    api_key = os.getenv("QDRANT_API_KEY")
    logger.info(f"QDRANT_API_KEY 존재 여부: {bool(api_key)}, 길이: {len(api_key) if api_key else 0}")
    
    # Qdrant 클라이언트 초기화 - 안정적인 연결 설정
    qdrant_client = QdrantClient(
        url="https://9429a5d7-55d9-43fa-8ad7-8e6cfcd37e22.europe-west3-0.gcp.cloud.qdrant.io:6333", 
        api_key=api_key,
        timeout=30  # 타임아웃 값 증가
    )
    
    # 간단한 Qdrant 연결 테스트
    try:
        collections = qdrant_client.get_collections()
        logger.info(f"Qdrant 연결 성공! 컬렉션 목록: {[c.name for c in collections.collections]}")
    except Exception as e:
        logger.error(f"Qdrant 연결 테스트 실패: {str(e)}")
        # 연결 테스트에 실패해도 계속 진행 (나중에 다시 시도할 수 있음)
    
    # Sentence Transformer 모델 초기화
    logger.info("Sentence Transformer 모델 초기화 시작...")
    try:
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        logger.info("Sentence Transformer 모델 초기화 성공")
    except Exception as e:
        logger.error(f"Sentence Transformer 초기화 실패: {str(e)}")
        model = None
    
    # LLM 초기화
    llm = ChatOpenAI(
        temperature=0.3,
        model=os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")
    )
    
    # Qdrant 컬렉션 생성 또는 확인
    def create_or_check_collection():
        """중요 대화 데이터를 저장할 컬렉션 생성 또는 확인"""
        try:
            collections = qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if "important_conversations" not in collection_names:
                logger.info("'important_conversations' 컬렉션이 없어 새로 생성합니다...")
                qdrant_client.create_collection(
                    collection_name="important_conversations",
                    vectors_config=models.VectorParams(
                        size=384,  # all-MiniLM-L6-v2 모델의 임베딩 크기
                        distance=models.Distance.COSINE
                    )
                )
                logger.info("Qdrant 컬렉션 'important_conversations' 생성 완료")
            else:
                logger.info("Qdrant 컬렉션 'important_conversations' 이미 존재")
                
            return True
        except Exception as e:
            logger.error(f"Qdrant 컬렉션 생성/확인 중 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    # 시작 시 컬렉션 생성 또는 확인
    collection_ready = create_or_check_collection()
    if collection_ready:
        logger.info("Qdrant 및 Sentence Transformer 초기화 완료, 저장 준비 완료")
    else:
        logger.warning("Qdrant 컬렉션 준비 실패, 저장 기능이 비활성화될 수 있습니다")
    
except Exception as e:
    logger.error(f"Qdrant 또는 Sentence Transformer 초기화 오류: {str(e)}")
    logger.error(traceback.format_exc())
    qdrant_client = None
    model = None
    llm = None  # LLM도 초기화 실패로 설정

def is_important_message(message: str, response: str) -> Tuple[bool, str]:
    """LLM을 사용하여 중요한 메시지인지 판단"""
    try:
        if not llm:
            return False, "LLM이 초기화되지 않았습니다."
        
        prompt = f"""
        다음 사용자 메시지와 AI 응답이 향후 참조할 가치가 있는 중요한 대화인지 판단해주세요.
        중요한 대화는 구체적인 정보나 지식을 담고 있거나, 사용자의 목표, 선호도 또는 진행 상황에 관한 중요한 정보를 포함합니다.

        사용자 메시지: {message}
        AI 응답: {response}

        다음 JSON 형식으로 응답해주세요:
        {{
            "is_important": true/false,
            "reason": "중요하다고 판단한 이유 또는 중요하지 않다고 판단한 이유",
            "category": "exercise/food/diet/schedule/motivation/general 중 하나"
        }}
        """
        
        result = llm.invoke(prompt)
        try:
            parsed_result = json.loads(result.content)
            is_important = parsed_result.get("is_important", False)
            reason = parsed_result.get("reason", "")
            logger.info(f"중요 메시지 분류 결과: {is_important}, 이유: {reason[:50]}...")
            return is_important, reason
        except json.JSONDecodeError:
            logger.error(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {result.content}")
            return False, "JSON 파싱 오류"
            
    except Exception as e:
        logger.error(f"중요 메시지 분류 중 오류: {str(e)}")
        return False, str(e)

def save_to_qdrant(state: GymGGunState, is_important: bool, reason: str) -> bool:
    """중요 대화를 Qdrant에 저장"""
    try:
        # Qdrant 클라이언트나 모델이 없으면 저장 불가
        if not qdrant_client:
            logger.warning("Qdrant 클라이언트가 초기화되지 않아 저장할 수 없습니다")
            return False
            
        if not model:
            logger.warning("Sentence Transformer 모델이 초기화되지 않아 저장할 수 없습니다")
            return False
            
        if not is_important:
            logger.info("중요하지 않은 메시지는 저장하지 않습니다")
            return False
            
        message = state.message
        response = state.response
        email = state.email
        response_type = state.response_type
        
        # 메시지 데이터 유효성 검사
        if not message or not response:
            logger.warning("메시지나 응답이 비어 있어 저장할 수 없습니다")
            return False
            
        # 컨텍스트 정보 생성
        context_text = f"""
        사용자 메시지: {message}
        응답 타입: {response_type}
        AI 응답: {response}
        중요도 이유: {reason}
        """
        
        # 텍스트 임베딩 생성
        logger.info("텍스트 임베딩 생성 중...")
        embedding = model.encode(context_text)
        logger.info(f"임베딩 생성 완료, 크기: {len(embedding)}")
        
        # 고유 ID 생성 (이메일과 타임스탬프 활용)
        import hashlib
        import time
        unique_id = hashlib.md5(f"{email}_{time.time()}".encode()).hexdigest()
        
        # Qdrant에 저장
        logger.info(f"Qdrant에 대화 저장 중 (ID: {unique_id})...")
        
        # 페이로드 데이터 준비
        payload = {
            "email": email if email else "anonymous",
            "message": message,
            "response": response,
            "response_type": response_type,
            "timestamp": time.time(),
            "importance_reason": reason
        }
        
        # 저장 시도
        try:
            qdrant_client.upsert(
                collection_name="important_conversations",
                points=[
                    models.PointStruct(
                        id=unique_id,
                        vector=embedding.tolist(),
                        payload=payload
                    )
                ]
            )
            logger.info(f"중요 대화 Qdrant에 저장 완료 - ID: {unique_id}")
            return True
        except Exception as e:
            logger.error(f"Qdrant 데이터 저장 중 오류: {str(e)}")
            logger.error(traceback.format_exc())
            
            # 컬렉션 재생성 시도
            logger.info("컬렉션 재생성 시도...")
            if create_or_check_collection():
                try:
                    # 컬렉션 재생성 후 다시 저장 시도
                    qdrant_client.upsert(
                        collection_name="important_conversations",
                        points=[
                            models.PointStruct(
                                id=unique_id,
                                vector=embedding.tolist(),
                                payload=payload
                            )
                        ]
                    )
                    logger.info(f"재시도 성공! 중요 대화 Qdrant에 저장 완료 - ID: {unique_id}")
                    return True
                except Exception as e2:
                    logger.error(f"Qdrant 데이터 재저장 시도 중 오류: {str(e2)}")
                    return False
            else:
                logger.error("컬렉션 재생성 실패, 저장 불가")
                return False
        
    except Exception as e:
        logger.error(f"Qdrant 저장 처리 중 일반 오류: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def combine_agent_responses(agent_results: List[Dict[str, Any]], llm=None) -> Dict[str, Any]:
    """여러 에이전트의 응답을 통합하는 함수"""
    if not agent_results:
        return {
            "response": "응답을 생성하지 못했습니다.",
            "type": "general"
        }
    
    # 하나의 결과만 있으면 그대로 반환
    if len(agent_results) == 1:
        return agent_results[0]
    
    try:
        # 응답 텍스트와 카테고리 추출
        responses_by_category = {}
        for result in agent_results:
            category = result.get("type", "unknown")
            response_text = result.get("response", "")
            
            if category and response_text:
                responses_by_category[category] = response_text
        
        # LLM을 사용하여 응답 통합
        if llm and len(responses_by_category) > 1:
            logger.info(f"LLM을 사용하여 {len(responses_by_category)}개 응답 통합 시작")
            
            # 통합 프롬프트 생성
            prompt = """
            다음은 여러 AI 에이전트가 제공한 응답입니다. 
            이 응답들을 통합하여 자연스러운 하나의 답변으로 만들어주세요.
            중복된 내용은 제거하고, 각 응답의 중요한 정보는 모두 포함시켜야 합니다.
            
            통합된 답변에는 각 에이전트별 정보를 구분할 수 있도록 각 섹션 시작 부분에 【에이전트 유형 응답】 형식의 헤더를 포함시켜 주세요.
            
            """
            
            # 각 에이전트 응답을 프롬프트에 추가
            for category, text in responses_by_category.items():
                prompt += f"\n[{category} 에이전트 응답]\n{text}\n"
            
            prompt += """
            위 응답들을 자연스럽게 통합한 하나의 답변을 제공해주세요.
            각 에이전트 응답 섹션은 【AGENT명 응답】 형식으로 시작해야 합니다. 예: 【EXERCISE 응답】, 【FOOD 응답】
            """
            
            try:
                # LLM을 사용하여 응답 통합
                result = llm.invoke(prompt)
                combined_text = result.content
                logger.info(f"LLM 응답 통합 완료 - 길이: {len(combined_text)}")
                
                return {
                    "response": combined_text,
                    "type": "multi",
                    "categories": list(responses_by_category.keys())
                }
            except Exception as e:
                logger.error(f"LLM 응답 통합 중 오류: {str(e)}")
                # LLM 실패 시 수동 통합으로 폴백
        
        # LLM이 없거나 실패한 경우 수동으로 통합
        combined_text = ""
        for category, text in responses_by_category.items():
            if combined_text:
                combined_text += f"\n\n【{category.upper()} 응답】\n{text}"
            else:
                combined_text = f"【{category.upper()} 응답】\n{text}"
        
        logger.info(f"수동 응답 통합 완료 - 길이: {len(combined_text)}")
        
        return {
            "response": combined_text,
            "type": "multi",
            "categories": list(responses_by_category.keys())
        }
            
    except Exception as e:
        logger.error(f"응답 통합 중 일반 오류: {str(e)}")
        
        # 오류 시 기본값 제공
        return {
            "response": "여러 에이전트의 응답을 통합하는 중 오류가 발생했습니다.",
            "type": "error",
            "error": str(e)
        }

def result_combiner(state: GymGGunState) -> GymGGunState:
    """주 에이전트와 보조 에이전트 결과를 통합"""
    try:
        start_time = time.time()
        logger.info("결과 통합 노드 시작")
        
        # 에이전트 결과 가져오기
        agent_results = getattr(state, "agent_results", [])
        
        # 결과가 있으면 통합
        if agent_results and len(agent_results) > 1:
            logger.info(f"{len(agent_results)}개 에이전트 결과 통합 시작")
            
            # 응답 통합
            combined_result = combine_agent_responses(agent_results, llm)
            
            # 상태 업데이트
            state.response = combined_result.get("response", "응답을 생성하지 못했습니다.")
            state.response_type = combined_result.get("type", "multi")
            
            # 메트릭에 카테고리 정보 저장
            state.metrics["response_categories"] = combined_result.get("categories", [])
            
            logger.info(f"응답 통합 완료 - 타입: {state.response_type}, 길이: {len(state.response)}")
        elif not state.response and agent_results and len(agent_results) == 1:
            # 하나의 결과만 있고 아직 응답이 설정되지 않은 경우
            result = agent_results[0]
            state.response = result.get("response", "응답을 생성하지 못했습니다.")
            state.response_type = result.get("type", "general")
            logger.info(f"단일 에이전트 응답 설정 - 타입: {state.response_type}")
        
        # 응답이 있으면 중요 메시지 분류 및 Qdrant 저장
        if state.response and state.message:
            try:
                # 중요 메시지인지 확인
                logger.info("중요 메시지 분석 시작...")
                is_important, reason = is_important_message(state.message, state.response)
                
                if is_important:
                    logger.info(f"중요 메시지 감지됨 - 이유: {reason[:50]}...")
                    
                    # Qdrant에 저장
                    logger.info("Qdrant에 저장 시도 중...")
                    save_success = save_to_qdrant(state, is_important, reason)
                    if save_success:
                        logger.info("✅ 중요 메시지 Qdrant에 저장 완료")
                        # 성공 정보를 메트릭에 기록
                        state.metrics["qdrant_save_success"] = True
                    else:
                        logger.warning("❌ 중요 메시지 Qdrant 저장 실패")
                        # 실패 정보를 메트릭에 기록
                        state.metrics["qdrant_save_success"] = False
                else:
                    logger.info(f"중요하지 않은 메시지로 분류됨 - 이유: {reason[:50]}...")
                    state.metrics["is_important_message"] = False
            except Exception as e:
                logger.error(f"중요 메시지 처리 중 오류: {str(e)}")
                logger.error(traceback.format_exc())
                # 중요 메시지 처리 실패 정보를 메트릭에 기록
                state.metrics["important_message_error"] = str(e)
                # 주요 기능이 아니므로 오류 발생해도 계속 진행
        
        # 메트릭에 실행 시간 기록
        execution_time = time.time() - start_time
        state.metrics["result_combiner_time"] = execution_time
        logger.info(f"결과 통합 완료 - 실행 시간: {execution_time:.2f}초")
        
        return state
        
    except Exception as e:
        error_msg = f"결과 통합 중 오류: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # 오류 정보 설정
        state.error = error_msg
        if not state.response:
            state.response = "죄송합니다. 응답을 생성하는 중에 문제가 발생했습니다."
            state.response_type = "error"
        
        return state 