"""
감정 분석 도구 모듈
"""
import json
import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import os
import re

from agents.motivation.tools.emotion_validation import EmotionValidationTool
from agents.motivation.tools.emotion_keywords import EmotionKeywordsTool

# 로깅 설정
logger = logging.getLogger(__name__)

# 감정 분석 프롬프트
EMOTION_DETECTION_PROMPT = """
사용자의 메시지를 읽고, 주된 감정과 강도를 추론하세요.
가능한 감정: happy (행복), sad (슬픔), angry (분노), anxious (불안), frustrated (좌절), motivated (동기부여), tired (피곤함), neutral (중립)
형식: JSON {"emotion": "감정", "intensity": 숫자(0.0~1.0)}

감정 강도는 다음 척도를 따릅니다:
0.0-0.3: 약한 감정
0.4-0.6: 중간 강도의 감정
0.7-1.0: 강한 감정

메시지에서 감정이 명확하게 드러나지 않으면 "neutral"로 분류하고 강도를 0.0~0.3 사이로 설정하세요.
"""

# 허용된 감정 목록
VALID_EMOTIONS = [
    "happy", "sad", "angry", "anxious", 
    "frustrated", "motivated", "tired", "neutral"
]

class EmotionDetectionTool:
    """사용자 메시지에서 감정을 감지하는 도구"""
    
    @staticmethod
    def get_tool_config() -> Dict[str, Any]:
        """
        감정 감지 도구 구성을 반환합니다.
        
        Returns:
            Dict[str, Any]: 도구 구성
        """
        return {
            "type": "function",
            "function": {
                "name": "detect_emotion",
                "description": "사용자 메시지에서 감정을 분석합니다",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "emotion": {
                            "type": "string",
                            "description": "감지된 감정 (happy, sad, angry, anxious, frustrated, motivated, tired, neutral 중 하나)"
                        },
                        "intensity": {
                            "type": "number",
                            "description": "감정 강도 (0.0에서 1.0 사이)"
                        }
                    },
                    "required": ["emotion", "intensity"]
                }
            }
        }
    
    @staticmethod
    def validate_emotion(emotion_data: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        감정 분석 결과를 검증합니다.
        
        Args:
            emotion_data: 감정 분석 결과 (emotion, intensity)
            message: 원본 사용자 메시지
            
        Returns:
            Dict[str, Any]: 검증된 감정 데이터
        """
        # 원본 데이터 저장
        original_emotion = emotion_data.get("emotion", "neutral")
        original_intensity = emotion_data.get("intensity", 0.0)
        
        # 감정 검증
        if original_emotion not in VALID_EMOTIONS:
            # 유효하지 않은 감정인 경우 가장 가까운 유효 감정 찾기
            closest_emotion = "neutral"
            for valid_emotion in VALID_EMOTIONS:
                if valid_emotion in original_emotion or original_emotion in valid_emotion:
                    closest_emotion = valid_emotion
                    break
            
            logger.warning(f"유효하지 않은 감정 '{original_emotion}'이 감지되어 '{closest_emotion}'으로 수정됨")
            emotion_data["emotion"] = closest_emotion
        
        # 강도 검증
        intensity = original_intensity
        if not isinstance(intensity, (int, float)):
            try:
                intensity = float(intensity)
            except (ValueError, TypeError):
                intensity = 0.5
                logger.warning(f"유효하지 않은 강도 값 '{original_intensity}'이 감지되어 0.5로 수정됨")
        
        # 강도 범위 조정
        if intensity < 0.0:
            intensity = 0.0
            logger.warning(f"강도 값 {original_intensity}가 허용 범위보다 작아 0.0으로 조정됨")
        elif intensity > 1.0:
            intensity = 1.0
            logger.warning(f"강도 값 {original_intensity}가 허용 범위보다 커 1.0으로 조정됨")
        
        emotion_data["intensity"] = intensity
        
        # 키워드 기반 검증 (EmotionKeywordsTool 사용)
        emotion = emotion_data["emotion"]
        alternative_emotion = EmotionKeywordsTool.validate_with_keywords(
            emotion, message, intensity
        )
        
        # 대안 감정이 제안된 경우 로그 기록
        if alternative_emotion:
            logger.info(f"키워드 검증: 감정 '{emotion}'에서 '{alternative_emotion}'으로 조정 제안")
            # 여기서는 로그만 남기고 실제로 감정을 변경하지는 않음
        
        return emotion_data
    
    @staticmethod
    def analyze_emotion(message: str) -> Dict[str, Any]:
        """
        LLM을 사용하여 메시지에서 감정을 분석합니다.
        LangChain을 사용하여 Smith 디버깅을 지원합니다.
        
        Args:
            message: 사용자 메시지
            
        Returns:
            Dict[str, Any]: 감정 분석 결과 (emotion, intensity)
        """
        try:
            # OpenAI API 키 확인
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
                return {"emotion": "neutral", "intensity": 0.0}
            
            # LangChain 모델 초기화
            model = ChatOpenAI(
                model="gpt-3.5-turbo",
                temperature=0.3,
                openai_api_key=api_key
            )
            
            # 프롬프트 템플릿 생성
            prompt = ChatPromptTemplate.from_messages([
                ("system", EMOTION_DETECTION_PROMPT),
                ("human", message)
            ])
            
            # 프롬프트 포맷팅
            formatted_prompt = prompt.format_messages()
            
            # API 호출
            response = model.invoke(formatted_prompt)
            content = response.content
            
            # 응답 로깅 (디버깅용)
            logger.debug(f"OpenAI 응답: {content}")
            
            try:
                # JSON 형식을 추출하기 위한 정규 표현식 적용
                json_pattern = r'\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\}'
                json_match = re.search(json_pattern, content)
                
                if json_match:
                    json_str = json_match.group(0)
                    logger.debug(f"추출된 JSON 문자열: {json_str}")
                    
                    try:
                        # 추출된 JSON 파싱 시도
                        result = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        # 중괄호가 있지만 유효한 JSON이 아닌 경우
                        logger.warning(f"JSON 파싱 오류: {e}, 문자열: {json_str}")
                        
                        # 따옴표 문제 수정 시도
                        fixed_json_str = json_str.replace("'", '"')
                        try:
                            result = json.loads(fixed_json_str)
                            logger.info("따옴표 수정 후 JSON 파싱 성공")
                        except json.JSONDecodeError:
                            # 여전히 실패하면 수동 파싱 시도
                            result = EmotionDetectionTool._manual_parse_json(content)
                else:
                    # JSON 형식이 없는 경우, 텍스트에서 감정과 강도를 직접 추출 시도
                    logger.warning(f"응답에서 JSON 형식을 찾을 수 없습니다: {content}")
                    result = EmotionDetectionTool._manual_parse_json(content)
                
                # 결과 검증
                if not result or "emotion" not in result or "intensity" not in result:
                    logger.warning(f"API 응답에 필요한 필드가 없습니다: {content}")
                    return {"emotion": "neutral", "intensity": 0.0}
                
                # 1차 검증: EmotionValidationTool 사용
                cleaned_result = EmotionValidationTool.clean_result(result)
                
                # 2차 검증: 추가 검증 및 키워드 확인
                validated_emotion = EmotionDetectionTool.validate_emotion(cleaned_result, message)
                
                return validated_emotion
                
            except Exception as json_err:
                logger.error(f"응답 파싱 오류: {str(json_err)}, 응답: {content}")
                return {"emotion": "neutral", "intensity": 0.0}
            
        except Exception as e:
            logger.error(f"감정 분석 중 오류 발생: {str(e)}")
            return {"emotion": "neutral", "intensity": 0.0}
    
    @staticmethod
    def _manual_parse_json(content: str) -> Dict[str, Any]:
        """
        정규식을 사용하여 JSON을 수동으로 파싱합니다.
        
        Args:
            content: 응답 내용
            
        Returns:
            Dict[str, Any]: 파싱된 결과
        """
        try:
            # 감정과 강도를 직접 추출하는 대체 로직
            emotion_match = re.search(r'emotion["\'s:]+([a-zA-Z]+)', content, re.IGNORECASE)
            intensity_match = re.search(r'intensity["\'s:]+([0-9.]+)', content, re.IGNORECASE)
            
            emotion = emotion_match.group(1).lower() if emotion_match else "neutral"
            try:
                intensity = float(intensity_match.group(1)) if intensity_match else 0.0
            except (ValueError, AttributeError):
                intensity = 0.0
            
            logger.info(f"수동 파싱 결과: 감정={emotion}, 강도={intensity}")
            return {"emotion": emotion, "intensity": intensity}
        except Exception as e:
            logger.error(f"수동 파싱 중 오류: {str(e)}")
            return {"emotion": "neutral", "intensity": 0.0}
    
    @staticmethod
    def process_response(tool_call=None, message=None):
        """
        도구 호출 응답과 필요시 메시지를 직접 분석하여 감정 데이터를 반환합니다.
        
        Args:
            tool_call: 감정 분석 도구 호출 응답
            message: 직접 분석할 메시지 (도구 호출 실패시)
            
        Returns:
            emotion_data: {'emotion': str, 'intensity': float} 형식의 감정 데이터
        """
        logger.info("감정 분석 응답 처리 시작")
        
        # 기본값 설정 - 중립 감정, 0 강도
        emotion_data = {"emotion": "neutral", "intensity": 0}
        
        try:
            # 우선 도구 호출 검증
            if tool_call and isinstance(tool_call, dict):
                # arguments가 문자열이면 JSON으로 파싱
                if isinstance(tool_call.get("arguments"), str):
                    try:
                        args = json.loads(tool_call["arguments"])
                        if isinstance(args, dict) and "emotion" in args and "intensity" in args:
                            emotion_data = {
                                "emotion": args["emotion"],
                                "intensity": float(args["intensity"])
                            }
                    except json.JSONDecodeError:
                        logger.warning("도구 호출 인자 JSON 파싱 실패")
                        
                # arguments가 이미 딕셔너리인 경우
                elif isinstance(tool_call.get("arguments"), dict):
                    args = tool_call["arguments"]
                    if "emotion" in args and "intensity" in args:
                        emotion_data = {
                            "emotion": args["emotion"],
                            "intensity": float(args["intensity"])
                        }
            
            # 메시지 직접 분석 (필요한 경우)
            if message and (not emotion_data or emotion_data["emotion"] == "neutral"):
                logger.info("메시지 직접 감정 분석 시도")
                analysis_result = EmotionDetectionTool.analyze_emotion(message)
                if analysis_result and isinstance(analysis_result, dict):
                    emotion_data = analysis_result
                    
            # 최종 감정 데이터 검증
            emotion_data = EmotionValidationTool.validate_emotion(emotion_data)
            logger.info(f"처리된 감정 데이터: {emotion_data}")
            return emotion_data
            
        except (KeyError, ValueError, AttributeError, json.JSONDecodeError) as e:
            logger.error(f"감정 분석 응답 처리 오류: {str(e)}")
            # 오류 시 기본 감정 데이터 반환
            return {"emotion": "neutral", "intensity": 0}