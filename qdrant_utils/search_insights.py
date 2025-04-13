#!/usr/bin/env python3
"""
사용자 인사이트 검색 유틸리티

사용 방법:
python -m qdrant_utils.search_insights --email user@example.com --query "운동 습관" 
"""

import asyncio
import argparse
import json
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# 프로젝트 루트 디렉토리를 추가하여 import가 작동하도록 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_utils.qdrant_client import QdrantManager

async def search_user_insights(
    email: Optional[str] = None,
    query: Optional[str] = None,
    days: Optional[int] = None,
    limit: int = 5,
    persona_type: Optional[str] = None,
    event_type: Optional[str] = None,
    output_file: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    사용자 인사이트를 검색합니다.
    
    Args:
        email: 검색할 사용자 이메일
        query: 검색 쿼리
        days: 최근 몇 일 데이터 검색 (None인 경우 모든 날짜)
        limit: 반환할 최대 결과 수
        persona_type: 검색할 성향 유형
        event_type: 검색할 이벤트 유형
        output_file: 결과를 저장할 파일 경로
        
    Returns:
        List[Dict[str, Any]]: 검색 결과
    """
    manager = QdrantManager()
    
    filter_params = {}
    
    # 이메일 필터 추가
    if email:
        filter_params["user_email"] = email
    
    # 날짜 필터 추가
    if days:
        now = datetime.now()
        from_date = now - timedelta(days=days)
        filter_params["date_from"] = from_date.isoformat()
        filter_params["date_to"] = now.isoformat()
    
    # 성향 필터 추가
    if persona_type:
        filter_params["persona_type"] = persona_type
    
    # 이벤트 유형 필터 추가
    if event_type:
        filter_params["event_type"] = event_type
    
    # 쿼리가 있으면 벡터 검색 수행
    if query:
        results = await manager.search_by_text(
            query_text=query,
            filter_params=filter_params,
            limit=limit
        )
    else:
        # 쿼리가 없으면 사용자 데이터만 조회
        if email:
            results = await manager.get_points_by_user(
                user_email=email,
                limit=limit
            )
        else:
            print("이메일이나 검색 쿼리가 필요합니다.")
            return []
    
    # 결과 출력
    if results:
        print(f"\n총 {len(results)}개의 인사이트를 찾았습니다.\n")
        
        for i, result in enumerate(results, 1):
            print(f"=== 인사이트 {i} ===")
            print(f"ID: {result['id']}")
            
            if 'score' in result:
                print(f"유사도 점수: {result['score']:.4f}")
            
            payload = result['payload']
            
            # 중요 정보 출력
            print(f"사용자: {payload.get('user_email', '알 수 없음')}")
            print(f"날짜: {payload.get('date', '알 수 없음')}")
            
            if 'persona_type' in payload:
                print(f"성향 유형: {payload.get('persona_type', '알 수 없음')}")
            
            if 'summary' in payload:
                print(f"\n요약: {payload.get('summary')}")
            
            # 해빗/관심사/이벤트 정보 출력
            if 'habits' in payload and payload['habits']:
                print("\n습관:")
                for habit in payload['habits']:
                    print(f"- {habit}")
            
            if 'interests' in payload and payload['interests']:
                print("\n관심사:")
                for interest in payload['interests']:
                    print(f"- {interest}")
            
            if 'events' in payload and payload['events']:
                print("\n주요 이벤트:")
                for event in payload['events']:
                    event_type = event.get('event_type', '알 수 없음')
                    description = event.get('description', '설명 없음')
                    importance = event.get('importance', '중간')
                    
                    print(f"- [{event_type}] {description} (중요도: {importance})")
            
            print("\n")
    
    # 출력 파일 저장
    if output_file and results:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"결과가 '{output_file}' 파일에 저장되었습니다.")
        except Exception as e:
            print(f"파일 저장 오류: {str(e)}")
    
    return results

def parse_arguments():
    """명령줄 인자를 파싱합니다."""
    parser = argparse.ArgumentParser(description="Qdrant에서 사용자 인사이트 검색")
    
    parser.add_argument("--email", type=str, help="검색할 사용자 이메일")
    parser.add_argument("--query", type=str, help="검색 쿼리")
    parser.add_argument("--days", type=int, help="최근 몇 일 데이터 검색")
    parser.add_argument("--limit", type=int, default=5, help="반환할 최대 결과 수")
    parser.add_argument("--persona-type", type=str, help="검색할 성향 유형")
    parser.add_argument("--event-type", type=str, help="검색할 이벤트 유형")
    parser.add_argument("--output", type=str, help="결과를 저장할 파일 경로")
    
    return parser.parse_args()

async def main():
    """메인 함수"""
    args = parse_arguments()
    
    await search_user_insights(
        email=args.email,
        query=args.query,
        days=args.days,
        limit=args.limit,
        persona_type=args.persona_type,
        event_type=args.event_type,
        output_file=args.output
    )

if __name__ == "__main__":
    asyncio.run(main()) 