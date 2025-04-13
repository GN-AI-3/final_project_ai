"""
Emotion analyzer node for LangGraph Supervisor
Analyzes user messages for emotional content and updates the workflow state
"""
import logging
import time
from typing import Dict, Any, List

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from langgraph_supervisor.state import SupervisorState

logger = logging.getLogger(__name__)

def create_emotion_analyzer(llm: ChatOpenAI):
    """
    Creates a node that analyzes the emotional content of user messages
    
    Args:
        llm: The language model to use for emotion analysis
        
    Returns:
        Function that takes a state and returns an updated state with emotion analysis
    """
    
    emotion_prompt = """
    Analyze the following user message for emotional content. 
    Identify the primary emotion (e.g., happiness, sadness, anger, fear, surprise, disgust, neutral) 
    and assign an emotion score from -10 to +10 where:
    
    - Negative scores (-10 to -1) indicate negative emotions (sadness, anger, fear, disgust)
    - Zero (0) indicates neutral emotion
    - Positive scores (1 to 10) indicate positive emotions (happiness, excitement, gratitude)
    
    The intensity of the score represents the strength of the emotion.
    
    Return your analysis as a JSON object with the following format:
    {
        "emotion_type": "primary emotion name",
        "emotion_score": score_value,
        "explanation": "brief explanation of your analysis"
    }
    
    User message: {message}
    """
    
    async def emotion_analyzer(state: SupervisorState) -> Dict[str, Any]:
        """
        Analyzes the emotional content of a user message
        
        Args:
            state: The current workflow state
            
        Returns:
            Updated state with emotion analysis
        """
        start_time = time.time()
        
        try:
            if not state.message:
                logger.warning(f"No message to analyze in request {state.request_id}")
                return {"emotion_type": "neutral", "emotion_score": 0}
            
            # Skip emotion analysis for very short messages
            if len(state.message.strip()) < 5:
                logger.info(f"Message too short for emotion analysis: {state.message}")
                return {"emotion_type": "neutral", "emotion_score": 0}
            
            # Format the prompt with the user's message
            formatted_prompt = emotion_prompt.format(message=state.message)
            
            # Call the language model
            response = await llm.ainvoke(
                [HumanMessage(content=formatted_prompt)]
            )
            
            # Extract the content from the response
            content = response.content
            
            # Parse the JSON response
            try:
                import json
                import re
                
                # Extract JSON from the response text if it's embedded in other text
                json_match = re.search(r'{.*}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    emotion_data = json.loads(json_str)
                else:
                    # Fallback if regex fails
                    emotion_data = json.loads(content)
                
                emotion_type = emotion_data.get("emotion_type", "neutral")
                emotion_score = float(emotion_data.get("emotion_score", 0))
                explanation = emotion_data.get("explanation", "")
                
                # Ensure the score is within the expected range
                emotion_score = max(-10, min(10, emotion_score))
                
                logger.info(
                    f"Emotion analysis for request {state.request_id}: "
                    f"Type={emotion_type}, Score={emotion_score}, Explanation: {explanation}"
                )
                
                # Update conversation context with emotion data
                if "emotions" not in state.conversation_context:
                    state.conversation_context["emotions"] = []
                
                # Add the current emotion to the history
                state.conversation_context["emotions"].append({
                    "timestamp": time.time(),
                    "message": state.message,
                    "emotion_type": emotion_type,
                    "emotion_score": emotion_score
                })
                
                # Keep only the last 10 emotions
                if len(state.conversation_context["emotions"]) > 10:
                    state.conversation_context["emotions"] = state.conversation_context["emotions"][-10:]
                
                # Calculate emotion trend
                if len(state.conversation_context["emotions"]) > 1:
                    previous_scores = [e["emotion_score"] for e in state.conversation_context["emotions"][:-1]]
                    avg_previous = sum(previous_scores) / len(previous_scores)
                    trend = emotion_score - avg_previous
                    state.conversation_context["emotion_trend"] = trend
                
                # Return the updated state
                return {
                    "emotion_type": emotion_type,
                    "emotion_score": emotion_score,
                    "used_nodes": state.used_nodes + ["emotion_analyzer"]
                }
                
            except Exception as e:
                logger.error(f"Error parsing emotion analysis result: {str(e)}")
                logger.error(f"Raw response: {content}")
                return {"emotion_type": "neutral", "emotion_score": 0}
            
        except Exception as e:
            logger.error(f"Error in emotion analysis: {str(e)}")
            return {"emotion_type": "neutral", "emotion_score": 0}
        finally:
            elapsed_time = time.time() - start_time
            logger.debug(f"Emotion analysis completed in {elapsed_time:.2f}s")
    
    return emotion_analyzer 