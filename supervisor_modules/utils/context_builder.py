"""
컨텍스트 빌더 모듈
에이전트에게 전달할 문맥 정보를 생성하고 관리하는 기능을 제공합니다.
"""

import json
import logging
import time
import traceback
from typing import Dict, Any, List, Optional
import re

from langchain_openai import ChatOpenAI
from langchain.schema.messages import SystemMessage, HumanMessage
from langsmith.run_helpers import traceable

from supervisor_modules.utils.logger_setup import get_logger
from common_prompts.prompts import AGENT_CONTEXT_BUILDING_PROMPT

# 로거 설정
logger = get_logger(__name__)

# 메시지에서 참조 번호를 추출하는 함수
def extract_references_from_message(message: str) -> list:
    """
    사용자 메시지에서 참조된 번호를 추출합니다.
    
    Args:
        message: 사용자 메시지
        
    Returns:
        List[int]: 참조된 번호 목록
    """
    all_refs = []
    
    # 숫자 + 번/번째 패턴
    num_refs = re.findall(r'(\d+)\s*(?:번|번째|항목|넘버|순서|번호)', message)
    all_refs.extend([int(num) for num in num_refs if num.isdigit()])
    
    # 단순 숫자 패턴 (컨텍스트와 함께 사용되는 경우)
    explanation_context = ['설명', '알려', '자세히', '정보', '방법', '어떻게', '무엇', '뭐야', '뭐니', '알려줘', '보여줘']
    if any(term in message for term in explanation_context):
        simple_nums = re.findall(r'(\d+)', message)
        for num in simple_nums:
            if num.isdigit() and 1 <= int(num) <= 10 and int(num) not in all_refs:
                all_refs.append(int(num))
    
    # 한글 서수사
    kor_num_pattern = r'(첫|두|세|네|다섯|여섯|일곱|여덟|아홉|열)(?:\s*(?:번째|번|항목|번호)|$)'
    kor_num_matches = re.findall(kor_num_pattern, message)
    
    kor_num_map = {
        '첫': 1, '두': 2, '세': 3, '네': 4, '다섯': 5,
        '여섯': 6, '일곱': 7, '여덟': 8, '아홉': 9, '열': 10
    }
    
    all_refs.extend([kor_num_map.get(word, 0) for word in kor_num_matches])
    
    # 영어 서수
    eng_ordinal_pattern = r'\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th)\b'
    eng_ordinal_matches = re.findall(eng_ordinal_pattern, message.lower())
    
    eng_ordinal_map = {
        'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
        'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
        '1st': 1, '2nd': 2, '3rd': 3, '4th': 4, '5th': 5,
        '6th': 6, '7th': 7, '8th': 8, '9th': 9, '10th': 10
    }
    
    all_refs.extend([eng_ordinal_map.get(word, 0) for word in eng_ordinal_matches])
    
    # 영어 서수 약어 패턴 (중복 제거를 위해 위의 패턴에 통합)
    
    # 한글 숫자 단어
    kor_num_words = {
        '하나': 1, '한': 1, '둘': 2, '두': 2, '셋': 3, '세': 3,
        '넷': 4, '네': 4, '다섯': 5, '여섯': 6, '일곱': 7, 
        '여덟': 8, '아홉': 9, '열': 10
    }
    
    for word, num in kor_num_words.items():
        if word in message:
            all_refs.append(num)
    
    # 불릿 포인트 시작 패턴 (•, -, * 등)
    bullet_pattern = r'[•\-\*]\s*(\d+)'
    bullet_matches = re.findall(bullet_pattern, message)
    all_refs.extend([int(num) for num in bullet_matches if num.isdigit() and 1 <= int(num) <= 10])
    
    # 중복 제거 및 정렬
    unique_refs = sorted(list(set([ref for ref in all_refs if ref > 0])))
    
    # 결과 로깅
    if unique_refs:
        print(f"[CONTEXT_BUILDER] 추출된 숫자 참조: {unique_refs}")
    
    return unique_refs

# 대화 내역에서 목록을 추출하는 함수
def extract_list_from_chat_history(chat_history: List[dict]) -> dict:
    """
    채팅 내역에서 번호가 매겨진 목록을 추출합니다.
    
    Args:
        chat_history: 채팅 내역의 리스트
        
    Returns:
        Dict[int, str]: 키는 번호, 값은 항목 내용
    """
    # 마지막 assistant 메시지부터 역순으로 검색
    for chat in reversed(chat_history):
        if chat.get('role') == 'assistant':
            message = chat.get('content', '')
            
            # 다양한 리스트 패턴 탐지
            # 1. 기본 숫자 패턴: 1. 항목, 1) 항목, (1) 항목
            number_items = re.findall(r'(?:^|\n)[ \t]*(\d+)[ \t]*[\.\)\]:][ \t]*(.*?)(?=\n[ \t]*\d+[ \t]*[\.\)\]:]|\n\n|$)', message, re.DOTALL)
            
            # 2. 불릿 포인트 패턴: •/- 항목
            bullet_items = re.findall(r'(?:^|\n)[ \t]*[•\-\*][ \t]*(\d+)[:\.\)]?[ \t]*(.*?)(?=\n[ \t]*[•\-\*]|\n\n|$)', message, re.DOTALL)
            
            # 3. 영어 서수 패턴: First, Second, 등
            eng_ordinal_pattern = r'(?:^|\n)[ \t]*((?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)|(?:\d+)(?:st|nd|rd|th))[ \t]*[\.\):][ \t]*(.*?)(?=\n[ \t]*(?:(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)|(?:\d+)(?:st|nd|rd|th))|\n\n|$)'
            eng_ordinal_items = re.findall(eng_ordinal_pattern, message, re.IGNORECASE | re.DOTALL)
            
            # 4. 한글 서수 패턴: 첫 번째, 두 번째 등
            kor_ordinal_pattern = r'(?:^|\n)[ \t]*((?:첫|두|세|네|다섯|여섯|일곱|여덟|아홉|열)[ \t]*(?:번째|번))[ \t]*[\.\):]?[ \t]*(.*?)(?=\n[ \t]*(?:(?:첫|두|세|네|다섯|여섯|일곱|여덟|아홉|열)[ \t]*(?:번째|번))|\n\n|$)'
            kor_ordinal_items = re.findall(kor_ordinal_pattern, message, re.DOTALL)
            
            # 결과 처리 딕셔너리
            list_items = {}
            
            # 숫자 항목 처리
            for num_str, content in number_items:
                try:
                    num = int(num_str)
                    if 1 <= num <= 10:  # 합리적인 범위 내 번호만 처리
                        list_items[num] = content.strip()
                except ValueError:
                    continue
            
            # 불릿 항목 처리
            for num_str, content in bullet_items:
                try:
                    num = int(num_str)
                    if 1 <= num <= 10:
                        list_items[num] = content.strip()
                except ValueError:
                    continue
            
            # 영어 서수 항목 처리
            eng_ordinal_map = {
                'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
                'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10
            }
            
            for ordinal, content in eng_ordinal_items:
                ordinal_lower = ordinal.lower()
                
                # 직접 매핑 확인
                if ordinal_lower in eng_ordinal_map:
                    num = eng_ordinal_map[ordinal_lower]
                    list_items[num] = content.strip()
                    continue
                
                # 숫자+서수 접미사 처리
                ordinal_match = re.match(r'(\d+)(st|nd|rd|th)', ordinal_lower)
                if ordinal_match:
                    try:
                        num = int(ordinal_match.group(1))
                        if 1 <= num <= 10:
                            list_items[num] = content.strip()
                    except ValueError:
                        continue
            
            # 한글 서수 항목 처리
            kor_ordinal_map = {
                '첫': 1, '두': 2, '세': 3, '네': 4, '다섯': 5,
                '여섯': 6, '일곱': 7, '여덟': 8, '아홉': 9, '열': 10
            }
            
            for ordinal, content in kor_ordinal_items:
                for kor_num, num in kor_ordinal_map.items():
                    if ordinal.startswith(kor_num):
                        list_items[num] = content.strip()
                        break
            
            # 추출된 항목이 있으면 반환
            if list_items:
                print(f"[CONTEXT_BUILDER] 채팅 내역에서 추출한 목록 항목: {list_items}")
                return list_items
    
    return {}

@traceable(run_type="chain", name="에이전트 문맥 정보 빌더")
async def build_agent_context(
    message: str,
    categories: List[str],
    chat_history: List[Dict[str, Any]],
    user_traits: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    각 에이전트(카테고리)에 맞는 문맥 정보를 구성합니다.
    
    Args:
        message: 사용자 메시지
        categories: 분류된 카테고리 목록
        chat_history: 대화 내역
        user_traits: 사용자 성향 정보 (선택 사항)
        
    Returns:
        Dict[str, str]: 카테고리별 문맥 정보
    """
    start_time = time.time()
    
    try:
        # 카테고리가 없으면 빈 딕셔너리 반환
        if not categories:
            logger.warning("카테고리가 없어 문맥 정보를 생성하지 않습니다.")
            return {}
        
        logger.info(f"에이전트 문맥 정보 생성 시작: {categories}")
        
        # 대화 내역 포맷팅
        formatted_history = ""
        if chat_history:
            for entry in chat_history[-10:]:  # 최근 10개 메시지만 사용
                role = "사용자" if entry.get("role", "") == "user" else "AI"
                content = entry.get("content", "")
                formatted_history += f"{role}: {content}\n"
        
        # 성향 정보 포맷팅
        user_traits_text = "정보 없음"
        print(f"\n[CONTEXT_BUILDER] 사용자 특성 정보: {user_traits}")
        if user_traits:
            traits_parts = []
            if "persona_type" in user_traits:
                traits_parts.append(f"성향: {user_traits['persona_type']}")
            if "goals" in user_traits and user_traits["goals"]:
                traits_parts.append(f"목표: {', '.join(user_traits['goals'])}")
            if "exercise_info" in user_traits and user_traits["exercise_info"]:
                exercise_info = user_traits["exercise_info"]
                if "preferences" in exercise_info and exercise_info["preferences"]:
                    traits_parts.append(f"선호 운동: {', '.join(exercise_info['preferences'])}")
                if "intensity" in exercise_info:
                    traits_parts.append(f"운동 강도: {exercise_info['intensity']}")
            if "diet_info" in user_traits and user_traits["diet_info"]:
                diet_info = user_traits["diet_info"]
                if "preferences" in diet_info and diet_info["preferences"]:
                    traits_parts.append(f"선호 음식: {', '.join(diet_info['preferences'])}")
                if "restrictions" in diet_info and diet_info["restrictions"]:
                    traits_parts.append(f"식이 제한: {', '.join(diet_info['restrictions'])}")
                if "habits" in diet_info and diet_info["habits"]:
                    traits_parts.append(f"식사 습관: {', '.join(diet_info['habits'])}")
            
            user_traits_text = "; ".join(traits_parts)
            print(f"[CONTEXT_BUILDER] 포맷팅된 사용자 특성 정보: '{user_traits_text}'")
        else:
            print(f"[CONTEXT_BUILDER] 사용자 특성 정보 없음")
        
        # 프롬프트 변수 설정
        prompt_vars = {
            "message": message,
            "chat_history": formatted_history,
            "user_traits": user_traits_text
        }
        
        # 모델에 전달할 프롬프트 포맷팅
        formatted_prompt = AGENT_CONTEXT_BUILDING_PROMPT.format(**prompt_vars)
        
        # 디버그용 상세 로그 추가
        print("\n[CONTEXT_BUILDER] ===== 입력 데이터 상세 로깅 시작 =====")
        print(f"[CONTEXT_BUILDER] 메시지: '{message}'")
        print(f"[CONTEXT_BUILDER] 카테고리: {categories}")
        print(f"[CONTEXT_BUILDER] 대화 내역 ({len(chat_history)}개 항목):")
        for i, entry in enumerate(chat_history[-5:]):  # 최근 5개만 로깅
            role = entry.get("role", "")
            content = entry.get("content", "")[:100] + ("..." if len(entry.get("content", "")) > 100 else "")
            print(f"[CONTEXT_BUILDER]   {i+1}. {role}: {content}")
        
        # 메시지 특성 분석 (문맥 판단에 사용)
        print("[CONTEXT_BUILDER] ----- 메시지 특성 분석 -----")
        
        # 1. 후속 질문 패턴 확인
        is_follow_up = False
        short_query = len(message.strip()) <= 25
        has_pronoun = any(p in message.lower() for p in ["그", "이", "저", "그것", "이것", "저것", "그거", "이거"])
        has_number_reference = any(char.isdigit() for char in message) and any(term in message for term in ["번", "번째", "항목"])
        omitted_subject = not any(subject in message for subject in ["운동", "식단", "일정", "계획", "웨이트", "트레이닝"])
        
        if (short_query and (has_pronoun or has_number_reference or omitted_subject)):
            is_follow_up = True
            print(f"[CONTEXT_BUILDER] 후속 질문 감지: 짧은 쿼리({short_query}), 대명사({has_pronoun}), 숫자 참조({has_number_reference}), 주어 생략({omitted_subject})")
        
        # 2. 이전 AI 응답에 목록이 있는지 확인
        has_list_in_previous = False
        for entry in reversed(chat_history):
            if entry.get("role") == "assistant":
                content = entry.get("content", "")
                if re.search(r'\d+\.\s', content):
                    has_list_in_previous = True
                    print(f"[CONTEXT_BUILDER] 이전 응답에 목록 감지됨")
                break
        
        # 3. 추가적인 메시지 분석 로깅
        print(f"[CONTEXT_BUILDER] 메시지 길이: {len(message)}")
        print(f"[CONTEXT_BUILDER] 명령어 패턴: {'예' if any(cmd in message for cmd in ['알려줘', '설명해줘', '추천해줘']) else '아니오'}")
        print(f"[CONTEXT_BUILDER] 질문 패턴: {'예' if any(q in message for q in ['?', '어떻', '무엇', '어디', '언제', '왜']) else '아니오'}")
        print("[CONTEXT_BUILDER] ----------------------------")
        
        print(f"[CONTEXT_BUILDER] 포맷팅된 프롬프트:\n{formatted_prompt[:500]}...")
        print("[CONTEXT_BUILDER] ===== 입력 데이터 상세 로깅 끝 =====\n")
        
        # LangChain 모델 초기화
        chat_model = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.2
        )
        
        # 모델 호출
        response = chat_model.invoke([
            SystemMessage(content="당신은 대화 내용을 분석하고 에이전트에 필요한 문맥 정보를 정확하고 간결하게 추출하는 전문가입니다."),
            HumanMessage(content=formatted_prompt)
        ])
        
        # 응답 파싱
        response_text = response.content.strip()
        print(f"[CONTEXT_BUILDER] 모델 응답: {response_text}")
        
        try:
            # JSON 추출 (필요한 경우)
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_text = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_text = response_text
                
            # JSON 파싱
            context_info = json.loads(json_text)
            print(f"[CONTEXT_BUILDER] JSON 파싱 성공: {context_info}")
            
            # 메시지에서 숫자 참조 검사
            ref_indexes = extract_references_from_message(message)
            
            # 숫자 참조가 있으면 직접 목록 항목 찾아서 처리
            if ref_indexes:
                print(f"[CONTEXT_BUILDER] 숫자 참조 감지: {ref_indexes}")
                
                # 대화 내역에서 목록 추출
                list_items = extract_list_from_chat_history(chat_history)
                print(f"[CONTEXT_BUILDER] 추출된, 목록 항목: {list_items}")
                
                # 참조된 항목 있는지 확인
                if list_items:
                    # 모든 LLM 응답 무시하고 직접 구성
                    context_info = {}  # 기존 LLM 응답 초기화
                    
                    # 참조된 항목들 찾기
                    referenced_items = []
                    for ref_idx in ref_indexes:
                        for num, content in list_items.items():
                            if str(num) == str(ref_idx):
                                referenced_items.append((ref_idx, content))
                                break
                    
                    if referenced_items:
                        print(f"[CONTEXT_BUILDER] 참조된 항목 찾음: {referenced_items}")
                        
                        # 카테고리 추론
                        list_category = "general"
                        
                        # 메시지 내용 또는 참조된 항목의 내용을 기반으로 카테고리 결정
                        message_text = " ".join([content for _, content in referenced_items]) + " " + message
                        message_lower = message_text.lower()
                        
                        if any(term in message_lower for term in ["운동", "근육", "스트레칭", "트레이닝", "헬스", "운동법"]):
                            list_category = "exercise"
                        elif any(term in message_lower for term in ["식단", "음식", "식사", "영양", "칼로리", "요리"]):
                            list_category = "food"
                        elif any(term in message_lower for term in ["일정", "계획", "스케줄", "약속", "날짜", "시간"]):
                            list_category = "schedule"
                        elif any(term in message_lower for term in ["동기", "목표", "의지", "습관", "마음", "동기부여"]):
                            list_category = "motivation"
                        
                        # 단일 항목 참조인 경우
                        if len(referenced_items) == 1:
                            ref_idx, content = referenced_items[0]
                            context_info[list_category] = f"'{content}'에 대한 자세한 설명이 필요합니다."
                        # 다중 항목 참조인 경우
                        else:
                            items_text = ", ".join([f"'{content}'" for _, content in referenced_items])
                            context_info[list_category] = f"{items_text}에 대한 자세한 설명이 필요합니다."
                        
                        print(f"[CONTEXT_BUILDER] 직접 생성한 문맥 정보: {context_info}")
                    else:
                        print(f"[CONTEXT_BUILDER] 참조된 항목을 찾지 못함")
            
            # 기본 카테고리 확인
            valid_categories = ["exercise", "food", "schedule", "motivation", "general"]
            
            # 관련 카테고리만 필터링 및 유효하지 않은 값 제거
            filtered_context = {}
            
            # 모델 응답에서 한글 카테고리명을 영어 카테고리명으로 매핑
            category_mapping = {
                "운동": "exercise",
                "식단": "food", 
                "일정": "schedule",
                "동기부여": "motivation",
                "일반": "general"
            }
            
            # 간단한 카테고리 매핑 처리 (복잡한 패턴 매칭 없이)
            for key, value in context_info.items():
                # 카테고리 매핑 확인
                category = category_mapping.get(key, key)
                
                if category in valid_categories:
                    # LLM의 응답을 있는 그대로 사용 (JSON 문자열 값)
                    if isinstance(value, str) and value is not None and value != "null":
                        filtered_context[category] = value
                    # 딕셔너리 구조인 경우 (이전 방식과의 호환성 유지)
                    elif isinstance(value, dict):
                        # 간단히 사용자 의도 키 또는 다른 키-값 중 하나 사용
                        if "사용자 의도" in value and value["사용자 의도"]:
                            filtered_context[category] = value["사용자 의도"]
                        # 참조된 항목이 있는 경우
                        elif "참조된 항목" in value and value["참조된 항목"]:
                            referenced_item = value["참조된 항목"]
                            filtered_context[category] = f"이전 대화에서 언급된 '{referenced_item}'에 대한 정보가 필요합니다."
                        # 다른 첫 번째 유효한 값 사용
                        else:
                            for k, v in value.items():
                                if v and v != "null":
                                    filtered_context[category] = v
                                    break
            
            # 다른 카테고리에 대한 백업 처리
            if 'food' in categories and not filtered_context.get('food'):
                filtered_context['food'] = "식단 관련 정보가 필요합니다."
                
            if 'schedule' in categories and not filtered_context.get('schedule'):
                filtered_context['schedule'] = "일정 관련 정보가 필요합니다."
                
            if 'motivation' in categories and not filtered_context.get('motivation'):
                filtered_context['motivation'] = "동기부여 관련 정보가 필요합니다."
            
            # 상기 카테고리가 없으면 기본 문맥 추가
            if not filtered_context:
                filtered_context["general"] = "사용자의 일반적인 질문에 답변하세요."
            
            logger.info(f"에이전트 문맥 정보 생성 완료: {list(filtered_context.keys())} (소요시간: {time.time() - start_time:.2f}초)")
            print(f"[CONTEXT_BUILDER] 최종 문맥 정보: {filtered_context}")
            
            # 디버깅용 로깅
            for category, context_value in filtered_context.items():
                logger.debug(f"카테고리 '{category}' 문맥 정보: {context_value}")
                
            return filtered_context
            
        except json.JSONDecodeError as e:
            logger.error(f"문맥 정보 JSON 파싱 실패: {str(e)}")
            logger.error(f"원본 응답: {response_text}")
            # 실패 시 기본 문맥 생성
            return {category: f"{category} 카테고리 문맥 정보를 생성하지 못했습니다." for category in categories}
            
    except Exception as e:
        logger.error(f"문맥 정보 생성 중 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        # 오류 시 기본 문맥 생성
        return {category: f"{category} 카테고리 문맥 정보를 생성하지 못했습니다." for category in categories}

# 문맥 정보를 에이전트 호출에 맞게 포맷팅하는 함수
def format_context_for_agent(context_info: Dict[str, str], agent_type: str) -> str:
    """
    에이전트에 맞는 문맥 정보를 포맷팅합니다.
    
    Args:
        context_info: 카테고리별 문맥 정보
        agent_type: 에이전트 타입
        
    Returns:
        str: 포맷팅된 문맥 정보
    """
    print(f"\n[FORMAT_CONTEXT] 에이전트 '{agent_type}'에 대한 문맥 정보 포맷팅")
    print(f"[FORMAT_CONTEXT] 사용 가능한 문맥 정보: {list(context_info.keys())}")
    
    # 해당 에이전트의 문맥 정보가 있으면 사용
    if agent_type in context_info:
        print(f"[FORMAT_CONTEXT] '{agent_type}' 에이전트의 문맥 정보 사용: '{context_info[agent_type][:50]}...'")
        return context_info[agent_type]
    
    # 'general' 카테고리 정보가 있으면 사용
    if "general" in context_info:
        print(f"[FORMAT_CONTEXT] '{agent_type}' 에이전트 정보 없음, 'general' 정보 사용: '{context_info['general'][:50]}...'")
        return context_info["general"]
    
    # 둘 다 없으면 기본 메시지 반환
    print(f"[FORMAT_CONTEXT] '{agent_type}' 및 'general' 정보 모두 없음, 기본 메시지 사용")
    return "이전 대화 정보가 없습니다." 