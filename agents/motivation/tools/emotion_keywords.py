"""
감정 키워드 분석 도구
"""
import logging
import re
from typing import Dict, List, Optional

# 로깅 설정
logger = logging.getLogger(__name__)

class EmotionKeywordsTool:
    """감정 분석을 위한 키워드 기반 도구"""
    
    # 감정별 키워드 (검증용)
    EMOTION_KEYWORDS = {
        "happy": ["기쁘", "행복", "좋아", "즐거", "신나", "좋은 소식", "축하", "성공", "기분 좋", "happy", "joy", "glad", "delighted", "pleasure"],
        "sad": ["슬프", "우울", "속상", "마음이 아프", "눈물", "절망", "비통", "상심", "서글프", "하기 싫", "sad", "depressed", "unhappy", "sorrow"],
        "angry": ["화가 나", "분노", "짜증", "열받", "화난", "격분", "성나", "노여움", "불쾌", "angry", "mad", "upset", "annoyed", "furious"],
        "anxious": ["불안", "걱정", "초조", "긴장", "스트레스", "두려움", "겁나", "염려", "근심", "anxious", "worried", "nervous", "stress", "fear"],
        "frustrated": ["좌절", "실망", "포기", "안되", "안 돼", "실패", "안타깝", "힘들", "어렵", "지치", "frustrated", "disappointed", "discouraged"],
        "motivated": ["동기", "의욕", "열정", "하고싶", "도전", "성취", "목표", "시작하", "결심", "계획", "motivated", "inspired", "eager", "determined"],
        "tired": ["피곤", "지침", "힘들", "에너지", "쉬", "휴식", "졸림", "잠", "쏟아지", "체력", "tired", "exhausted", "sleepy", "fatigue", "rest"],
        "neutral": ["질문", "알려줘", "어떻게", "무엇", "어디", "언제", "누구", "왜", "정보", "question", "info", "what", "when", "how", "where"]
    }
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """
        텍스트를 정규화합니다.
        - 모든 공백 제거
        - 소문자로 변환 (영문)
        
        Args:
            text: 정규화할 텍스트
            
        Returns:
            str: 정규화된 텍스트
        """
        # 공백 제거
        normalized = re.sub(r'\s+', '', text)
        # 소문자 변환 (영문)
        normalized = normalized.lower()
        return normalized
    
    @staticmethod
    def check_keywords(message: str, emotion: str) -> bool:
        """
        메시지에 특정 감정과 관련된 키워드가 있는지 확인합니다.
        대소문자와 공백을 무시하고 검색합니다.
        
        Args:
            message: 사용자 메시지
            emotion: 확인할 감정
            
        Returns:
            bool: 키워드가 발견되면 True, 아니면 False
        """
        if emotion not in EmotionKeywordsTool.EMOTION_KEYWORDS:
            return False
        
        # 메시지 정규화
        normalized_message = EmotionKeywordsTool.normalize_text(message)
        
        keywords = EmotionKeywordsTool.EMOTION_KEYWORDS[emotion]
        for keyword in keywords:
            # 키워드 정규화
            normalized_keyword = EmotionKeywordsTool.normalize_text(keyword)
            if normalized_keyword in normalized_message:
                return True
                
        return False
    
    @staticmethod
    def find_alternative_emotion(message: str) -> Optional[str]:
        """
        메시지에 가장 많은 키워드가 있는 감정을 찾습니다.
        대소문자와 공백을 무시하고 검색합니다.
        
        Args:
            message: 사용자 메시지
            
        Returns:
            Optional[str]: 찾은 감정 또는 None
        """
        max_matches = 0
        best_emotion = None
        
        # 메시지 정규화
        normalized_message = EmotionKeywordsTool.normalize_text(message)
        
        for emotion, keywords in EmotionKeywordsTool.EMOTION_KEYWORDS.items():
            # 각 키워드에 대해 정규화하여 검사
            matches = 0
            for keyword in keywords:
                normalized_keyword = EmotionKeywordsTool.normalize_text(keyword)
                if normalized_keyword in normalized_message:
                    matches += 1
            
            if matches > max_matches:
                max_matches = matches
                best_emotion = emotion
                
        return best_emotion if max_matches > 0 else None
    
    @staticmethod
    def validate_with_keywords(emotion: str, message: str, intensity: float) -> Optional[str]:
        """
        키워드를 사용하여 감정을 검증합니다.
        대소문자와 공백을 무시하고 검색합니다.
        
        Args:
            emotion: 검증할 감정
            message: 사용자 메시지
            intensity: 감정 강도
            
        Returns:
            Optional[str]: 대안 감정 (문제가 없으면 None)
        """
        if emotion == "neutral":
            return None
            
        # 키워드 검사
        found_keywords = EmotionKeywordsTool.check_keywords(message, emotion)
        
        # 키워드가 없고 강도가 높은 경우 대안 찾기
        if not found_keywords and intensity > 0.6:
            alternative_emotion = EmotionKeywordsTool.find_alternative_emotion(message)
            if alternative_emotion and alternative_emotion != emotion:
                logger.info(f"키워드 검증: 감정 '{emotion}'은(는) 메시지와 일치하지 않을 수 있음. 대안: '{alternative_emotion}'")
                return alternative_emotion
                
        return None 