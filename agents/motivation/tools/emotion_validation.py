"""
감정 분석 결과 유효성 검사 도구
"""
import logging
from typing import Dict, Any

# 로깅 설정
logger = logging.getLogger(__name__)

class EmotionValidationTool:
    """감정 분석 결과를 정제하고 검증하는 도구"""

    # 유효한 감정 리스트
    VALID_EMOTIONS = {
        "happy", "sad", "angry", "anxious", "frustrated",
        "motivated", "tired", "neutral"
    }

    @staticmethod
    def clean_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """
        감정 분석 결과를 정제하고 유효성 검사를 수행합니다.

        Args:
            result (Dict[str, Any]): LLM에서 반환된 감정 분석 결과

        Returns:
            Dict[str, Any]: 정제된 emotion, intensity 값
        """
        # 감정 정제
        emotion = result.get("emotion", "neutral")
        if not isinstance(emotion, str):
            logger.warning(f"emotion이 문자열이 아님: {emotion}")
            emotion = "neutral"
        emotion = emotion.strip().lower()
        if emotion not in EmotionValidationTool.VALID_EMOTIONS or " " in emotion or len(emotion) > 20:
            logger.warning(f"유효하지 않은 감정 값: '{emotion}' → 'neutral'로 대체됨")
            emotion = "neutral"

        # 강도 정제
        try:
            intensity = float(result.get("intensity", 0.0))
            intensity = max(0.0, min(intensity, 1.0))  # 0.0~1.0 범위 제한
        except (ValueError, TypeError):
            logger.warning(f"강도 값 오류 또는 형식 오류: {result.get('intensity')}")
            intensity = 0.0

        return {
            "emotion": emotion,
            "intensity": intensity
        } 