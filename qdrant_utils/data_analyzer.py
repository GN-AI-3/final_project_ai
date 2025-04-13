#!/usr/bin/env python3
"""
데이터 분석기 - PostgreSQL의 채팅 메시지를 가져와 성향 분석 및 사건 정리 후 Qdrant에 저장

실행 방법:
- 단일 실행: python -m qdrant_utils.data_analyzer
- 스케줄러에 등록하여 매일 00시에 실행
"""

import os
import asyncio
import logging
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import qdrant_client
from qdrant_client.http import models
import openai
from openai import OpenAI
import schedule
import time

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("qdrant_utils/logs/data_analyzer.log", mode='a')
    ]
)
logger = logging.getLogger(__name__)

# 환경변수 로드
load_dotenv()

# 설정값 로드
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_URL = "https://9429a5d7-55d9-43fa-8ad7-8e6cfcd37e22.europe-west3-0.gcp.cloud.qdrant.io:6333"
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "chat_insights")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY)

class DataAnalyzer:
    """
    채팅 데이터 분석기 클래스
    PostgreSQL에서 데이터를 가져와 분석하고 Qdrant에 저장합니다.
    """
    
    def __init__(self):
        """초기화 및 DB 연결 설정"""
        self.pg_conn = None
        self.qdrant_client = None
        self.last_analyzed_date = None
        
        # 로그 디렉토리 생성
        os.makedirs("qdrant_utils/logs", exist_ok=True)
        
        # Qdrant 클라이언트 초기화
        try:
            self.qdrant_client = qdrant_client.QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY
            )
            # 컬렉션 존재 확인 및 생성
            collections = self.qdrant_client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if QDRANT_COLLECTION not in collection_names:
                logger.info(f"컬렉션 '{QDRANT_COLLECTION}'이 없어 새로 생성합니다.")
                self.qdrant_client.create_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=models.VectorParams(
                        size=1536,  # OpenAI text-embedding-3-small 모델의 차원
                        distance=models.Distance.COSINE
                    )
                )
                
                # 컬렉션 스키마 - 필드 인덱싱 설정
                self.qdrant_client.create_payload_index(
                    collection_name=QDRANT_COLLECTION,
                    field_name="user_email",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                self.qdrant_client.create_payload_index(
                    collection_name=QDRANT_COLLECTION,
                    field_name="date",
                    field_schema=models.PayloadSchemaType.DATETIME
                )
                self.qdrant_client.create_payload_index(
                    collection_name=QDRANT_COLLECTION,
                    field_name="persona_type",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                self.qdrant_client.create_payload_index(
                    collection_name=QDRANT_COLLECTION,
                    field_name="event_type",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                
            logger.info("Qdrant 연결 성공")
        except Exception as e:
            logger.error(f"Qdrant 연결 오류: {str(e)}")
            logger.error(traceback.format_exc())
    
    def connect_postgres(self):
        """PostgreSQL 연결"""
        try:
            self.pg_conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                dbname=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD
            )
            logger.info("PostgreSQL 연결 성공")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL 연결 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def close_postgres(self):
        """PostgreSQL 연결 종료"""
        if self.pg_conn:
            self.pg_conn.close()
            logger.info("PostgreSQL 연결 종료")
    
    def get_chat_messages(self, from_date: datetime, to_date: datetime) -> List[Dict[str, Any]]:
        """
        특정 기간의 채팅 메시지를 PostgreSQL에서 가져옵니다.
        
        Args:
            from_date: 조회 시작 날짜
            to_date: 조회 종료 날짜
            
        Returns:
            List[Dict[str, Any]]: 채팅 메시지 목록
        """
        if not self.pg_conn:
            if not self.connect_postgres():
                return []
        
        try:
            with self.pg_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                SELECT 
                    cm.content, 
                    cm.role, 
                    cm.created_at,
                    m.email as user_email
                FROM 
                    chat_message cm
                JOIN 
                    member m ON cm.member_id = m.id
                WHERE 
                    cm.created_at BETWEEN %s AND %s
                ORDER BY 
                    m.email, cm.created_at
                """
                cursor.execute(query, (from_date, to_date))
                records = cursor.fetchall()
                
                logger.info(f"{len(records)}개의 채팅 메시지를 가져왔습니다.")
                return [dict(record) for record in records]
        except Exception as e:
            logger.error(f"채팅 메시지 조회 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    def group_messages_by_user(self, messages: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        사용자별로 메시지를 그룹화합니다.
        
        Args:
            messages: 채팅 메시지 목록
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: 사용자별 채팅 메시지
        """
        grouped = {}
        
        for msg in messages:
            email = msg.get("user_email")
            if not email:
                continue
                
            if email not in grouped:
                grouped[email] = []
                
            grouped[email].append(msg)
        
        return grouped
    
    def format_messages_for_analysis(self, messages: List[Dict[str, Any]]) -> str:
        """
        분석을 위해 메시지를 포맷팅합니다.
        
        Args:
            messages: 메시지 목록
            
        Returns:
            str: 분석을 위해 포맷팅된 메시지
        """
        formatted = []
        
        # 시간순으로 정렬
        sorted_msgs = sorted(messages, key=lambda x: x.get("created_at"))
        
        for msg in sorted_msgs:
            timestamp = msg.get("created_at").strftime("%Y-%m-%d %H:%M:%S")
            role = "사용자" if msg.get("role") == "user" else "AI"
            content = msg.get("content", "")
            
            # 추가 컨텍스트 정보가 있으면 포함
            extra_info = ""
            if msg.get("final_response") and msg.get("role") == "assistant":
                content = msg.get("final_response")
            
            if msg.get("member_input") and msg.get("role") == "user":
                content = msg.get("member_input")
            
            if msg.get("selected_agents"):
                extra_info += f" [선택된 에이전트: {msg.get('selected_agents')}]"
            
            formatted.append(f"[{timestamp}] {role}: {content}{extra_info}")
        
        return "\n".join(formatted)
    
    async def analyze_persona(self, messages: str, email: str) -> Dict[str, Any]:
        """
        사용자의 성향을 분석합니다.
        
        Args:
            messages: 포맷팅된 메시지
            email: 사용자 이메일
            
        Returns:
            Dict[str, Any]: 성향 분석 결과
        """
        try:
            # OpenAI API를 사용한 성향 분석
            prompt = f"""
사용자 {email}의 대화 내역을 분석하여 사용자의 성향과 관심사를 파악해 주세요.
다음 형식으로 JSON 응답을 제공해 주세요:

```
{{
    "persona_type": "성향 유형(적극적, 소극적, 열정적, 정보추구형, 동기부여형 등)",
    "habits": ["습관1 예: 운동 꾸준히 하는 편", "습관2 예: 야식 자주 먹음", "습관3"],
    "interests": ["관심사1", "관심사2", "관심사3"],
    "communication_style": "소통 스타일(간결한, 상세한, 질문이 많은, 감정적인 등)",
    "goals": ["목표1", "목표2"],
    "challenges": ["어려움1", "어려움2"],
    "summary": "사용자 성향 요약 (2-3문장)"
}}
```

사용자 대화 내역:
{messages}
"""
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 사용자 성향을 분석하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=800
            )
            
            # 응답 파싱
            response_text = response.choices[0].message.content
            # JSON 추출
            json_text = response_text
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_text = response_text.split("```")[1].split("```")[0].strip()
            
            # 결과 파싱
            result = json.loads(json_text)
            logger.info(f"사용자 {email} 성향 분석 완료: {result.get('persona_type')}")
            
            return {
                "persona_type": result.get("persona_type", "Unknown"),
                "habits": result.get("habits", []),
                "interests": result.get("interests", []),
                "communication_style": result.get("communication_style", "Unknown"),
                "goals": result.get("goals", []),
                "challenges": result.get("challenges", []),
                "summary": result.get("summary", "")
            }
            
        except Exception as e:
            logger.error(f"성향 분석 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "persona_type": "Unknown",
                "habits": [],
                "interests": [],
                "communication_style": "Unknown",
                "goals": [],
                "challenges": [],
                "summary": f"분석 오류: {str(e)}"
            }
    
    async def analyze_events(self, messages: str, email: str) -> Dict[str, Any]:
        """
        대화에서 주요 사건을 추출하고 라벨링합니다.
        
        Args:
            messages: 포맷팅된 메시지
            email: 사용자 이메일
            
        Returns:
            Dict[str, Any]: 사건 분석 결과
        """
        try:
            # OpenAI API를 사용한 사건 분석 및 라벨링
            prompt = f"""
사용자 {email}의 대화 내역을 분석하여 주요 사건과 이슈를 추출하고 라벨링해 주세요.
다음 형식으로 JSON 응답을 제공해 주세요:

```
{{
    "events": [
        {{
            "event_type": "이벤트 타입(운동계획, 식단상담, 건강이슈, 동기부여, 일정변경 등)",
            "description": "이벤트 상세 설명 (예: 이번 주 월수금 운동함, PT 시작함)",
            "labels": ["라벨1", "라벨2"],
            "importance": "중요도(낮음, 중간, 높음)",
            "action_required": true/false
        }},
        ...
    ],
    "top_topics": ["주제1", "주제2", "주제3"],
    "sentiment": "전반적인 감정(부정적, 중립적, 긍정적)",
    "summary": "대화 주요 사건 요약 (3-5문장)"
}}
```

대화에서 가장 중요한 정보와 사건을 추출하되, 개인정보(이름, 주소 등)는 보호해 주세요.
운동 계획, 식단, 건강 목표, 어려움 등에 집중해 주세요.
실제 행동이나 사건을 구체적으로 기술해주세요. (예: "이번 주 월수금 운동함", "PT 시작함", "식단 조절 시작함")

사용자 대화 내역:
{messages}
"""
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 대화에서 주요 사건과 정보를 추출하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            # 응답 파싱
            response_text = response.choices[0].message.content
            # JSON 추출
            json_text = response_text
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_text = response_text.split("```")[1].split("```")[0].strip()
            
            # 결과 파싱
            result = json.loads(json_text)
            logger.info(f"사용자 {email} 사건 분석 완료: {len(result.get('events', []))}개 이벤트 추출")
            
            return {
                "events": result.get("events", []),
                "top_topics": result.get("top_topics", []),
                "sentiment": result.get("sentiment", "Unknown"),
                "summary": result.get("summary", "")
            }
            
        except Exception as e:
            logger.error(f"사건 분석 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "events": [],
                "top_topics": [],
                "sentiment": "Unknown",
                "summary": f"분석 오류: {str(e)}"
            }
    
    async def generate_embeddings(self, text: str) -> List[float]:
        """
        텍스트에 대한 임베딩을 생성합니다.
        
        Args:
            text: 임베딩을 생성할 텍스트
            
        Returns:
            List[float]: 임베딩 벡터
        """
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"임베딩 생성 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return [0.0] * 1536  # OpenAI 임베딩 차원에 맞춰 0으로 채운 벡터 반환
    
    async def store_analysis_results(self, user_email: str, persona_result: Dict, events_result: Dict) -> bool:
        """
        분석 결과를 PostgreSQL에 저장합니다.
        
        Args:
            user_email: 사용자 이메일
            persona_result: 성향 분석 결과
            events_result: 사건 분석 결과
            
        Returns:
            bool: 저장 성공 여부
        """
        if not self.pg_conn:
            if not self.connect_postgres():
                return False
                
        # 결과값 추출
        persona_type = persona_result.get('persona_type', '')
        habits = persona_result.get('habits', [])
        interests = persona_result.get('interests', [])
        communication_style = persona_result.get('communication_style', '')
        goals = persona_result.get('goals', [])
        challenges = persona_result.get('challenges', [])
        persona_summary = persona_result.get('summary', '')
        
        events = events_result.get('events', [])
        top_topics = events_result.get('top_topics', [])
        sentiment = events_result.get('sentiment', '')
        events_summary = events_result.get('summary', '')
        
        try:
            with self.pg_conn.cursor() as cursor:
                # 사용자 ID 조회
                cursor.execute("SELECT id FROM member WHERE email = %s", (user_email,))
                user_id = cursor.fetchone()[0] if cursor.rowcount > 0 else None
                
                if not user_id:
                    logger.error(f"사용자 {user_email}를 찾을 수 없습니다.")
                    return False
                
                # 기존 분석 결과 확인
                cursor.execute(
                    "SELECT id FROM analysis_results WHERE user_id = %s AND analysis_date = CURRENT_DATE",
                    (user_id,)
                )
                
                analysis_exists = cursor.rowcount > 0
                
                if analysis_exists:
                    # 기존 분석 결과 업데이트
                    query = """
                    UPDATE analysis_results SET
                        persona_type = %s,
                        habits = %s,
                        interests = %s,
                        communication_style = %s,
                        goals = %s,
                        challenges = %s,
                        persona_summary = %s,
                        events = %s,
                        top_topics = %s,
                        sentiment = %s,
                        events_summary = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE
                        user_id = %s AND analysis_date = CURRENT_DATE
                    """
                    
                    cursor.execute(
                        query,
                        (
                            persona_type,
                            json.dumps(habits, ensure_ascii=False),
                            json.dumps(interests, ensure_ascii=False),
                            communication_style,
                            json.dumps(goals, ensure_ascii=False),
                            json.dumps(challenges, ensure_ascii=False),
                            persona_summary,
                            json.dumps(events, ensure_ascii=False),
                            json.dumps(top_topics, ensure_ascii=False),
                            sentiment,
                            events_summary,
                            user_id
                        )
                    )
                else:
                    # 새 분석 결과 삽입
                    query = """
                    INSERT INTO analysis_results (
                        user_id, 
                        analysis_date, 
                        persona_type, 
                        habits,
                        interests, 
                        communication_style, 
                        goals, 
                        challenges,
                        persona_summary, 
                        events, 
                        top_topics, 
                        sentiment, 
                        events_summary,
                        created_at, 
                        updated_at
                    ) VALUES (
                        %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                    
                    cursor.execute(
                        query,
                        (
                            user_id,
                            persona_type,
                            json.dumps(habits, ensure_ascii=False),
                            json.dumps(interests, ensure_ascii=False),
                            communication_style,
                            json.dumps(goals, ensure_ascii=False),
                            json.dumps(challenges, ensure_ascii=False),
                            persona_summary,
                            json.dumps(events, ensure_ascii=False),
                            json.dumps(top_topics, ensure_ascii=False),
                            sentiment,
                            events_summary
                        )
                    )
                
                self.pg_conn.commit()
                logger.info(f"사용자 {user_email}의 분석 결과가 PostgreSQL에 저장되었습니다.")
                return True
                
        except Exception as e:
            logger.error(f"분석 결과 저장 오류: {str(e)}")
            logger.error(traceback.format_exc())
            self.pg_conn.rollback()
            return False
    
    async def analyze_daily_data(self, target_date: Optional[datetime] = None):
        """
        특정 날짜의 데이터를 분석합니다.
        
        Args:
            target_date: 분석할 날짜 (None인 경우 어제 날짜)
        """
        if target_date is None:
            target_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        
        from_date = target_date
        to_date = target_date.replace(hour=23, minute=59, second=59)
        
        logger.info(f"{from_date.strftime('%Y-%m-%d')} 데이터 분석 시작")
        
        # 채팅 메시지 가져오기
        messages = self.get_chat_messages(from_date, to_date)
        if not messages:
            logger.info(f"{from_date.strftime('%Y-%m-%d')}에 분석할 메시지가 없습니다.")
            return
        
        # 사용자별로 메시지 그룹화
        grouped_messages = self.group_messages_by_user(messages)
        
        # 각 사용자별 분석 수행
        for email, user_messages in grouped_messages.items():
            logger.info(f"사용자 {email} 분석 시작 - {len(user_messages)}개 메시지")
            
            # 분석용으로 메시지 포맷팅
            formatted_messages = self.format_messages_for_analysis(user_messages)
            
            # 성향 분석
            persona_analysis = await self.analyze_persona(formatted_messages, email)
            
            # 사건 분석 및 라벨링
            event_analysis = await self.analyze_events(formatted_messages, email)
            
            # 분석 결과 저장
            success = await self.store_analysis_results(
                user_email=email,
                persona_result=persona_analysis,
                events_result=event_analysis
            )
            
            if success:
                logger.info(f"사용자 {email} 분석 결과 저장 완료")
            else:
                logger.error(f"사용자 {email} 분석 결과 저장 실패")
        
        logger.info(f"{from_date.strftime('%Y-%m-%d')} 데이터 분석 완료")
    
    def run_scheduled_analysis(self):
        """매일 자정에 전날 데이터 분석을 실행합니다."""
        logger.info("스케줄링된 데이터 분석이 시작되었습니다.")
        
        yesterday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        asyncio.run(self.analyze_daily_data(yesterday))
    
    def start_scheduler(self):
        """스케줄러를 시작합니다."""
        # 매일 자정에 분석 실행
        schedule.every().day.at("00:00").do(self.run_scheduled_analysis)
        
        logger.info("스케줄러가 시작되었습니다. 매일 00:00에 분석이 실행됩니다.")
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1분마다 체크

async def run_analysis_for_date_range(start_date: datetime, end_date: datetime):
    """
    특정 날짜 범위의 데이터를 분석합니다.
    
    Args:
        start_date: 시작 날짜
        end_date: 종료 날짜
    """
    analyzer = DataAnalyzer()
    
    current_date = start_date
    while current_date <= end_date:
        logger.info(f"{current_date.strftime('%Y-%m-%d')} 데이터 분석 실행")
        await analyzer.analyze_daily_data(current_date)
        current_date += timedelta(days=1)
    
    logger.info("날짜 범위 분석 완료")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="채팅 데이터 분석 도구")
    parser.add_argument("--mode", choices=["schedule", "run", "range"], default="run",
                       help="실행 모드 (schedule: 스케줄러 실행, run: 어제 데이터 분석, range: 특정 범위 분석)")
    parser.add_argument("--start-date", help="분석 시작 날짜 (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="분석 종료 날짜 (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    analyzer = DataAnalyzer()
    
    if args.mode == "schedule":
        # 스케줄러 모드
        analyzer.start_scheduler()
    elif args.mode == "range" and args.start_date and args.end_date:
        # 날짜 범위 모드
        try:
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
            end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
            asyncio.run(run_analysis_for_date_range(start_date, end_date))
        except ValueError:
            logger.error("날짜 형식 오류. YYYY-MM-DD 형식으로 입력하세요.")
    else:
        # 기본 모드 - 어제 데이터 분석
        asyncio.run(analyzer.analyze_daily_data()) 