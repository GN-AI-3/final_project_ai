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
        qdrant_url = os.getenv("QDRANT_URL")
        api_key = os.getenv("QDRANT_API_KEY")
        
        if qdrant_url and api_key:
            client = QdrantClient(url=qdrant_url, api_key=api_key)
            logger.info("✅ QDrant 클라이언트 초기화 성공 (URL 연결)")
        else:
            # 로컬 개발용 기본값
            client = QdrantClient(host="localhost", port=6333)
            logger.info("✅ QDrant 클라이언트 초기화 성공 (로컬 연결)")
            
        return client
    except Exception as e:
        logger.error(f"❌ QDrant 클라이언트 초기화 실패: {str(e)}")
        # 기본 클라이언트 반환 (에러 처리용)
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
        
        # 최근 7일 이내 데이터 필터링
        one_week_ago = datetime.now() - timedelta(days=7)
        timestamp_filter = one_week_ago.timestamp()
        
        # 사용자 데이터 검색
        search_result = client.search(
            collection_name="chat_insights",
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
        
        # 관련 대화 검색 (벡터 검색)
        search_result = client.search(
            collection_name="chat_insights",
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