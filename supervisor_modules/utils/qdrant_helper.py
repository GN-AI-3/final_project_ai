"""
QDrant 헬퍼 모듈
QDrant에서 사용자 인사이트 데이터를 검색하고 프롬프트에 활용하기 위한 유틸리티 함수를 제공합니다.
"""

import os
import logging
from typing import Dict, Any, List, Optional
import json
from datetime import datetime, timedelta

from qdrant_client import QdrantClient
from qdrant_client.http import models

from supervisor_modules.utils.logger_setup import get_logger

# 로거 설정
logger = get_logger(__name__)

# QDrant 클라이언트 초기화
def get_qdrant_client() -> QdrantClient:
    """QDrant 클라이언트를 초기화하고 반환합니다."""
    try:
        # qdrant_utils에 정의된 값 사용
        qdrant_url = os.getenv("QDRANT_URL", "https://9429a5d7-55d9-43fa-8ad7-8e6cfcd37e22.europe-west3-0.gcp.cloud.qdrant.io:6333")
        api_key = os.getenv("QDRANT_API_KEY")
        
        if api_key:
            client = QdrantClient(url=qdrant_url, api_key=api_key)
            logger.info(f"✅ QDrant 클라이언트 초기화 성공 (URL: {qdrant_url})")
        else:
            # API 키가 없으면 URL만으로 시도
            client = QdrantClient(url=qdrant_url)
            logger.info(f"✅ QDrant 클라이언트 초기화 성공 (API 키 없음, URL: {qdrant_url})")
            
        return client
    except Exception as e:
        logger.error(f"❌ QDrant 클라이언트 초기화 실패: {str(e)}")
        # 로컬 개발용 fallback
        try:
            client = QdrantClient(host="localhost", port=6333)
            logger.info("✅ QDrant 클라이언트 초기화 성공 (로컬 연결)")
            return client
        except Exception:
            logger.error("❌ 로컬 QDrant 연결도 실패, 더미 클라이언트 반환")
            # 연결 실패 시 더미 클라이언트 반환
            return QdrantClient(host="localhost", port=6333)

async def get_user_insights(email: str) -> Dict[str, Any]:
    """
    QDrant에서 사용자 인사이트 정보를 검색합니다.
    
    Args:
        email: 사용자 이메일
        
    Returns:
        Dict[str, Any]: 사용자 인사이트 정보
    """
    try:
        client = get_qdrant_client()
        
        # 컬렉션 이름 - 환경 변수에서 가져오기
        collection_name = os.getenv("QDRANT_COLLECTION", "chat_insights")
        
        # 최근 7일 이내 데이터 필터링
        one_week_ago = datetime.now() - timedelta(days=7)
        timestamp_filter = one_week_ago.timestamp()
        
        # 사용자 데이터 검색
        search_result = client.search(
            collection_name=collection_name,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_email",
                        match=models.MatchValue(value=email)
                    ),
                    models.FieldCondition(
                        key="timestamp",
                        range=models.Range(
                            gte=timestamp_filter
                        )
                    )
                ]
            ),
            limit=5  # 최근 5개 인사이트만 가져옴
        )
        
        if not search_result:
            logger.info(f"사용자 {email}에 대한 인사이트 정보가 없습니다.")
            return {
                "user_insights": "특별한 인사이트 정보가 없습니다.",
                "recent_events": "최근 특별한 이벤트가 없습니다.",
                "user_persona": "사용자 페르소나 정보가 없습니다."
            }
        
        # 결과 합치기
        user_insights = []
        recent_events = []
        user_personas = []
        
        for point in search_result:
            payload = point.payload
            if "insights" in payload:
                user_insights.append(payload["insights"])
            if "events" in payload:
                recent_events.append(payload["events"])
            if "persona" in payload:
                user_personas.append(payload["persona"])
        
        # 정보 통합
        return {
            "user_insights": "\n".join(user_insights) if user_insights else "특별한 인사이트 정보가 없습니다.",
            "recent_events": "\n".join(recent_events) if recent_events else "최근 특별한 이벤트가 없습니다.",
            "user_persona": "\n".join(list(set(user_personas))) if user_personas else "사용자 페르소나 정보가 없습니다."
        }
        
    except Exception as e:
        logger.error(f"QDrant 데이터 검색 중 오류 발생: {str(e)}")
        return {
            "user_insights": "인사이트 정보를 가져오는 중 오류가 발생했습니다.",
            "recent_events": "이벤트 정보를 가져오는 중 오류가 발생했습니다.",
            "user_persona": "페르소나 정보를 가져오는 중 오류가 발생했습니다."
        }

async def search_relevant_conversations(email: str, query: str) -> str:
    """
    QDrant에서 사용자의 질문과 관련된 과거 대화를 검색합니다.
    
    Args:
        email: 사용자 이메일
        query: 검색 쿼리 (사용자 질문)
        
    Returns:
        str: 관련 과거 대화 내용
    """
    try:
        client = get_qdrant_client()
        
        # 컬렉션 이름 - 환경 변수에서 가져오기
        collection_name = os.getenv("QDRANT_COLLECTION", "chat_insights")
        
        # 관련 대화 검색 (벡터 검색)
        search_result = client.search(
            collection_name=collection_name,
            query_vector=("text", query),  # 텍스트 기반 벡터 검색
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_email",
                        match=models.MatchValue(value=email)
                    )
                ]
            ),
            limit=3  # 상위 3개 결과만 가져옴
        )
        
        if not search_result:
            return "관련된 과거 대화 정보가 없습니다."
        
        # 관련 대화 내용 합치기
        relevant_conversations = []
        
        for point in search_result:
            payload = point.payload
            if "raw_conversation" in payload:
                relevant_conversations.append(f"과거 대화:\n{payload['raw_conversation']}")
            elif "summary" in payload:
                relevant_conversations.append(f"대화 요약:\n{payload['summary']}")
        
        return "\n\n".join(relevant_conversations)
        
    except Exception as e:
        logger.error(f"관련 대화 검색 중 오류 발생: {str(e)}")
        return "관련된 과거 대화 정보를 가져오는 중 오류가 발생했습니다."

async def get_user_events(email: str) -> str:
    """
    QDrant에서 사용자의 이벤트 정보만 검색합니다.
    
    Args:
        email: 사용자 이메일
        
    Returns:
        str: 사용자 이벤트 정보를 문자열로 반환
    """
    # 개발 환경에서 Qdrant를 사용하지 않는 경우를 위한 확인
    if os.getenv("DISABLE_QDRANT", "false").lower() == "true":
        logger.info("Qdrant 기능이 비활성화되어 있습니다.")
        return ""
        
    try:
        # 연결 시도
        try:
            client = get_qdrant_client()
            
            # 서버 연결 테스트
            client.get_collections()
            logger.info(f"Qdrant 서버 연결 성공, 사용자 '{email}' 검색 시작")
        except Exception as conn_err:
            logger.warning(f"Qdrant 서버 연결 실패: {str(conn_err)}. 빈 이벤트 정보 반환.")
            return ""
        
        # 최근 7일 이내 데이터 필터링
        one_week_ago = datetime.now() - timedelta(days=7)
        timestamp_filter = one_week_ago.timestamp()
        
        # 컬렉션 이름 - 환경 변수에서 가져오기
        collection_name = os.getenv("QDRANT_COLLECTION", "chat_insights")
        
        # 컬렉션 존재 여부 확인
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if collection_name not in collection_names:
            logger.warning(f"'{collection_name}' 컬렉션이 존재하지 않습니다. 빈 이벤트 정보 반환.")
            return ""
        
        logger.info(f"컬렉션 '{collection_name}' 확인됨, 데이터 검색 시작")
        
        # 사용자 데이터 검색 - 간소화된 필터로 먼저 시도 (타임스탬프 필터 제외)
        try:
            search_result = client.scroll(
                collection_name=collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="user_email",
                            match=models.MatchValue(value=email)
                        )
                    ]
                ),
                limit=10  # 더 많은 결과 가져오기
            )[0]
            
            logger.info(f"{len(search_result)}개의 검색 결과 찾음")
            
            # 검색 결과 목록 로깅 (최대 3개)
            if search_result:
                for i, point in enumerate(search_result[:3]):
                    if hasattr(point, 'id'):
                        logger.info(f"결과 {i+1}: ID={point.id}")
                    if hasattr(point, 'payload'):
                        payload_keys = list(point.payload.keys())
                        logger.info(f"결과 {i+1} 페이로드 키: {payload_keys}")
        except Exception as search_err:
            logger.warning(f"Qdrant 데이터 조회 실패: {str(search_err)}. 빈 이벤트 정보 반환.")
            return ""
        
        if not search_result:
            logger.info(f"사용자 {email}에 대한 이벤트 정보가 없습니다.")
            return ""
        
        # 이벤트 정보만 추출
        events_data = []
        logger.info("이벤트 정보 추출 시작")
        
        for i, point in enumerate(search_result):
            payload = point.payload
            logger.info(f"결과 {i+1} 페이로드 키: {list(payload.keys())}")
            
            # events 키 직접 확인
            if "events" in payload:
                events_value = payload["events"]
                logger.info(f"events 필드 찾음: 타입={type(events_value).__name__}")
                
                # events가 문자열인 경우 - 로깅 및 파싱
                if isinstance(events_value, str):
                    logger.info(f"events 문자열: {events_value[:50]}...")
                    try:
                        events_json = json.loads(events_value)
                        logger.info(f"events JSON 파싱 성공: {type(events_json).__name__}")
                        
                        # {"events": [{...}, {...}]} 형식
                        if isinstance(events_json, dict) and "events" in events_json:
                            logger.info(f"events.events 항목 발견: {len(events_json['events'])}개")
                            for event in events_json["events"]:
                                event_info = {
                                    "type": event.get("event_type", "알 수 없음"),
                                    "description": event.get("description", ""),
                                    "importance": event.get("importance", "중간")
                                }
                                events_data.append(event_info)
                        
                        # [{...}, {...}] 형식
                        elif isinstance(events_json, list):
                            logger.info(f"events 배열 발견: {len(events_json)}개")
                            for event in events_json:
                                if isinstance(event, dict):
                                    event_info = {
                                        "type": event.get("event_type", "알 수 없음"),
                                        "description": event.get("description", ""),
                                        "importance": event.get("importance", "중간")
                                    }
                                    events_data.append(event_info)
                    except json.JSONDecodeError as e:
                        logger.warning(f"events JSON 파싱 실패: {e}")
                        # 파싱 실패 시 문자열 그대로 추가
                        events_data.append({"raw": events_value})
                
                # events가 딕셔너리인 경우
                elif isinstance(events_value, dict):
                    logger.info(f"events 딕셔너리 구조: {list(events_value.keys())}")
                    
                    # {"events": [{...}, {...}]} 형식
                    if "events" in events_value and isinstance(events_value["events"], list):
                        logger.info(f"events.events 배열: {len(events_value['events'])}개")
                        for event in events_value["events"]:
                            if isinstance(event, dict):
                                event_info = {
                                    "type": event.get("event_type", "알 수 없음"),
                                    "description": event.get("description", ""),
                                    "importance": event.get("importance", "중간")
                                }
                                events_data.append(event_info)
                    
                    # {"event_type": "...", "description": "..."} 형식
                    elif "event_type" in events_value or "description" in events_value:
                        logger.info("단일 이벤트 형식 발견")
                        event_info = {
                            "type": events_value.get("event_type", "알 수 없음"),
                            "description": events_value.get("description", ""),
                            "importance": events_value.get("importance", "중간")
                        }
                        events_data.append(event_info)
                
                # events가 리스트인 경우
                elif isinstance(events_value, list):
                    logger.info(f"events 리스트: {len(events_value)}개 항목")
                    for event in events_value:
                        if isinstance(event, dict):
                            event_info = {
                                "type": event.get("event_type", "알 수 없음"),
                                "description": event.get("description", ""),
                                "importance": event.get("importance", "중간")
                            }
                            events_data.append(event_info)
            
            # combined_text 확인 
            if "combined_text" in payload:
                combined_text = payload["combined_text"]
                logger.info(f"combined_text 필드 발견: {combined_text[:50]}...")
                
                # 이벤트 마커 검색
                if "이벤트:" in combined_text or "events:" in combined_text:
                    logger.info("combined_text에서 이벤트 마커 발견")
        
        # 결과 요약
        if events_data:
            logger.info(f"총 {len(events_data)}개의 이벤트를 추출했습니다.")
            
            # 이벤트 정보를 텍스트로 변환
            events_text = []
            for event in events_data:
                if "raw" in event:
                    events_text.append(event["raw"])
                else:
                    events_text.append(f"[{event['type']}] {event['description']} (중요도: {event['importance']})")
            
            return "\n".join(events_text)
        else:
            logger.info("추출된 이벤트 정보가 없습니다.")
            return ""
        
    except Exception as e:
        logger.error(f"QDrant 이벤트 데이터 검색 중 오류 발생: {str(e)}")
        # 오류 발생 시 빈 문자열 반환 - 기능 실패가 전체 흐름에 영향을 주지 않도록
        return "" 