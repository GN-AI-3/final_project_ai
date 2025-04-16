#!/usr/bin/env python3
"""
Qdrant 클라이언트 유틸리티
벡터 데이터베이스 쿼리 및 관리를 위한 유틸리티 함수 제공
"""

import os
import logging
import json
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import traceback

import qdrant_client
from qdrant_client.http import models
from dotenv import load_dotenv
from openai import OpenAI

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("qdrant_utils/logs/qdrant_client.log", mode='a')
    ]
)
logger = logging.getLogger(__name__)

# 로그 디렉토리 생성
os.makedirs("qdrant_utils/logs", exist_ok=True)

# 환경변수 로드
load_dotenv()

# 설정값 로드
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_URL = "https://9429a5d7-55d9-43fa-8ad7-8e6cfcd37e22.europe-west3-0.gcp.cloud.qdrant.io:6333"
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "chat_insights")

# OpenAI 클라이언트 초기화
openai_client = OpenAI(api_key=OPENAI_API_KEY)

class QdrantManager:
    """
    Qdrant 벡터 데이터베이스 관리 클래스
    벡터 저장, 검색, 컬렉션 관리 등의 기능 제공
    """
    
    def __init__(self, collection_name: str = QDRANT_COLLECTION):
        """
        Qdrant 클라이언트 초기화
        
        Args:
            collection_name: 사용할 컬렉션 이름
        """
        self.collection_name = collection_name
        self.client = None
        self.init_client()
        
    def init_client(self) -> bool:
        """
        Qdrant 클라이언트 초기화
        
        Returns:
            bool: 초기화 성공 여부
        """
        try:
            self.client = qdrant_client.QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY
            )
            # 컬렉션 존재 확인
            self.ensure_collection_exists()
            logger.info(f"Qdrant 클라이언트 초기화 성공 (컬렉션: {self.collection_name})")
            return True
        except Exception as e:
            logger.error(f"Qdrant 클라이언트 초기화 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def ensure_collection_exists(self):
        """컬렉션 존재 확인 및 없으면 생성"""
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                logger.info(f"컬렉션 '{self.collection_name}'이 없어 새로 생성합니다.")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=1536,  # OpenAI text-embedding-3-small 모델의 차원
                        distance=models.Distance.COSINE
                    )
                )
                
                # 컬렉션 스키마 - 필드 인덱싱 설정
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="user_email",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="date",
                    field_schema=models.PayloadSchemaType.DATETIME
                )
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="persona_type",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="event_type",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                
            return True
        except Exception as e:
            logger.error(f"컬렉션 확인/생성 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    async def generate_embeddings(self, text: str) -> List[float]:
        """
        텍스트에 대한 임베딩을 생성합니다.
        
        Args:
            text: 임베딩을 생성할 텍스트
            
        Returns:
            List[float]: 임베딩 벡터
        """
        try:
            response = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"임베딩 생성 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return [0.0] * 1536  # OpenAI 임베딩 차원에 맞춰 0으로 채운 벡터 반환
    
    async def add_point(self, 
                       id: str, 
                       vector: List[float], 
                       payload: Dict[str, Any]) -> bool:
        """
        벡터 포인트를 추가합니다.
        
        Args:
            id: 포인트 ID
            vector: 임베딩 벡터
            payload: 메타데이터
            
        Returns:
            bool: 추가 성공 여부
        """
        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            logger.info(f"ID {id}의 포인트가 추가되었습니다.")
            return True
        except Exception as e:
            logger.error(f"포인트 추가 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    async def search_points(self, 
                          query_vector: List[float], 
                          filter_params: Optional[Dict[str, Any]] = None, 
                          limit: int = 5) -> List[Dict[str, Any]]:
        """
        벡터 검색을 수행합니다.
        
        Args:
            query_vector: 검색할 쿼리 벡터
            filter_params: 필터링 파라미터
            limit: 반환할 결과 수
            
        Returns:
            List[Dict[str, Any]]: 검색 결과
        """
        try:
            filter_obj = None
            if filter_params:
                filter_conditions = []
                
                # 사용자 이메일 필터
                if "user_email" in filter_params:
                    filter_conditions.append(
                        models.FieldCondition(
                            key="user_email",
                            match=models.MatchValue(value=filter_params["user_email"])
                        )
                    )
                
                # 날짜 범위 필터
                if "date_from" in filter_params and "date_to" in filter_params:
                    filter_conditions.append(
                        models.FieldCondition(
                            key="date",
                            range=models.DatetimeRange(
                                gte=filter_params["date_from"],
                                lte=filter_params["date_to"]
                            )
                        )
                    )
                
                # 성향 유형 필터
                if "persona_type" in filter_params:
                    filter_conditions.append(
                        models.FieldCondition(
                            key="persona_type",
                            match=models.MatchValue(value=filter_params["persona_type"])
                        )
                    )
                
                # 이벤트 유형 필터
                if "event_type" in filter_params:
                    filter_conditions.append(
                        models.FieldCondition(
                            key="event_type",
                            match=models.MatchValue(value=filter_params["event_type"])
                        )
                    )
                
                if filter_conditions:
                    filter_obj = models.Filter(
                        must=filter_conditions
                    )
            
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=filter_obj,
                limit=limit
            )
            
            # 결과 변환
            results = []
            for result in search_result:
                result_dict = {
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload
                }
                results.append(result_dict)
            
            logger.info(f"{len(results)}개의 검색 결과를 찾았습니다.")
            return results
        except Exception as e:
            logger.error(f"벡터 검색 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    async def search_by_text(self, 
                           query_text: str, 
                           filter_params: Optional[Dict[str, Any]] = None, 
                           limit: int = 5) -> List[Dict[str, Any]]:
        """
        텍스트로 벡터 검색을 수행합니다.
        
        Args:
            query_text: 검색할 텍스트
            filter_params: 필터링 파라미터
            limit: 반환할 결과 수
            
        Returns:
            List[Dict[str, Any]]: 검색 결과
        """
        query_vector = await self.generate_embeddings(query_text)
        return await self.search_points(query_vector, filter_params, limit)
    
    async def get_points_by_user(self, user_email: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        특정 사용자의 모든 포인트를 가져옵니다.
        
        Args:
            user_email: 사용자 이메일
            limit: 반환할 결과 수
            
        Returns:
            List[Dict[str, Any]]: 포인트 목록
        """
        try:
            filter_obj = models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_email",
                        match=models.MatchValue(value=user_email)
                    )
                ]
            )
            
            search_result = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=filter_obj,
                limit=limit
            )
            
            # 결과 변환
            results = []
            for result in search_result[0]:
                result_dict = {
                    "id": result.id,
                    "payload": result.payload
                }
                results.append(result_dict)
            
            logger.info(f"사용자 {user_email}의 {len(results)}개 포인트를 찾았습니다.")
            return results
        except Exception as e:
            logger.error(f"사용자 포인트 조회 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    async def delete_points_by_filter(self, filter_params: Dict[str, Any]) -> bool:
        """
        필터 조건에 맞는 포인트를 삭제합니다.
        
        Args:
            filter_params: 필터링 파라미터
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            filter_conditions = []
            
            # 사용자 이메일 필터
            if "user_email" in filter_params:
                filter_conditions.append(
                    models.FieldCondition(
                        key="user_email",
                        match=models.MatchValue(value=filter_params["user_email"])
                    )
                )
            
            # 날짜 범위 필터
            if "date_from" in filter_params and "date_to" in filter_params:
                filter_conditions.append(
                    models.FieldCondition(
                        key="date",
                        range=models.DatetimeRange(
                            gte=filter_params["date_from"],
                            lte=filter_params["date_to"]
                        )
                    )
                )
            
            if not filter_conditions:
                logger.error("삭제를 위한 필터 조건이 지정되지 않았습니다.")
                return False
            
            filter_obj = models.Filter(
                must=filter_conditions
            )
            
            result = self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=filter_obj
                )
            )
            
            logger.info(f"{result.deleted} 개의 포인트가 삭제되었습니다.")
            return True
        except Exception as e:
            logger.error(f"포인트 삭제 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        컬렉션 정보를 가져옵니다.
        
        Returns:
            Dict[str, Any]: 컬렉션 정보
        """
        try:
            collection_info = self.client.get_collection(
                collection_name=self.collection_name
            )
            
            # 컬렉션 크기 가져오기
            collection_stats = {
                "name": collection_info.config.params.name,
                "vector_size": collection_info.config.params.vectors.size,
                "distance": collection_info.config.params.vectors.distance,
                "points_count": collection_info.points_count,
                "vectors_count": collection_info.vectors_count,
                "indexed_vectors_count": getattr(collection_info, "indexed_vectors_count", 0),
            }
            
            logger.info(f"컬렉션 정보 조회 완료: {collection_stats}")
            return collection_stats
        except Exception as e:
            logger.error(f"컬렉션 정보 조회 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return {"error": str(e)}

# 비동기 API 사용 예시
async def example_usage():
    """Qdrant 매니저 사용 예시"""
    manager = QdrantManager()
    
    # 벡터 생성 및 저장
    text = "이 사용자는 운동을 좋아하고 매일 아침 조깅을 하는 습관이 있습니다."
    vector = await manager.generate_embeddings(text)
    
    # 벡터 저장
    success = await manager.add_point(
        id="example_point_1",
        vector=vector,
        payload={
            "user_email": "example@example.com",
            "date": datetime.now().isoformat(),
            "persona_type": "active",
            "description": text,
            "habits": ["morning jogging", "healthy diet"],
            "interests": ["fitness", "health"]
        }
    )
    
    if success:
        # 저장된 벡터 검색
        results = await manager.search_by_text(
            query_text="운동 습관",
            filter_params={"user_email": "example@example.com"},
            limit=5
        )
        
        for result in results:
            print(f"ID: {result['id']}, Score: {result['score']}")
            print(f"Payload: {json.dumps(result['payload'], ensure_ascii=False)}")
    
    # 컬렉션 정보 조회
    collection_info = manager.get_collection_info()
    print(f"Collection Info: {collection_info}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage()) 