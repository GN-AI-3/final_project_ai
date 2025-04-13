"""
Message Classifier for LangGraph Supervisor
"""
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("langgraph_supervisor.nodes.message_classifier")

def create_message_classifier(
    categories: List[str] = None,
    llm = None
):
    """
    Create a message classifier node that determines which agent categories
    should process the user message.
    
    Args:
        categories: List of available agent categories
        llm: Language model to use for classification
        
    Returns:
        function: Message classifier function
    """
    if categories is None:
        categories = ["general", "food", "schedule", "routine"]
    
    # Track execution metrics
    metrics = {
        "execution_time": 0,
        "errors": 0
    }
    
    async def message_classifier(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify the user message into categories to determine which agents to invoke.
        
        Args:
            state: Current workflow state
            
        Returns:
            Dict: Updated workflow state with categories
        """
        start_time = time.time()
        request_id = state.get("request_id", str(uuid.uuid4()))
        user_id = state.get("user_id", "default_user")
        message = state.get("message", "")
        
        logger.info(f"[{request_id}] Processing message classification for user {user_id}")
        
        try:
            # For now, use a simple keyword-based classification
            # In a production system, you'd want to use the LLM for this
            selected_categories = []
            
            # Simple keyword matching for demonstration
            message_lower = message.lower()
            
            if "food" in message_lower or "eat" in message_lower or "meal" in message_lower or "diet" in message_lower:
                selected_categories.append("food")
            
            if "schedule" in message_lower or "appointment" in message_lower or "meeting" in message_lower:
                selected_categories.append("schedule")
                
            if "routine" in message_lower or "daily" in message_lower or "habit" in message_lower:
                selected_categories.append("routine")
            
            # If no specific categories matched, use general
            if not selected_categories:
                selected_categories.append("general")
            
            logger.info(f"[{request_id}] Classified message into categories: {selected_categories}")
            
            # If we have an LLM, we could use a more sophisticated approach
            if llm is not None:
                # This is where you would implement LLM-based classification
                # For now, we'll just log that we could do this
                logger.debug(f"[{request_id}] LLM-based classification could be used here")
            
            # Update metrics
            metrics["execution_time"] = time.time() - start_time
            
            # Update the state with the selected categories
            return {
                **state,
                "categories": selected_categories,
                "metrics": {
                    **state.get("metrics", {}),
                    "message_classifier": {
                        "execution_time": metrics["execution_time"],
                        "errors": metrics["errors"]
                    }
                }
            }
            
        except Exception as e:
            metrics["errors"] += 1
            logger.error(f"[{request_id}] Error in message classification: {str(e)}")
            
            # Update the state with error information
            return {
                **state,
                "error": f"Error in message classification: {str(e)}",
                "metrics": {
                    **state.get("metrics", {}),
                    "message_classifier": {
                        "execution_time": time.time() - start_time,
                        "errors": metrics["errors"]
                    }
                }
            }
    
    return message_classifier 