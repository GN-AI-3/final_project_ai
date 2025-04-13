"""
Response Generator for LangGraph Supervisor
"""
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("langgraph_supervisor.nodes.response_generator")

def create_response_generator(max_response_length: int = 8000):
    """
    Create a response generator node that combines results from multiple agents.
    
    Args:
        max_response_length: Maximum length of the generated response
        
    Returns:
        function: Response generator function
    """
    # Track execution metrics
    metrics = {
        "execution_time": 0,
        "errors": 0
    }
    
    def _extract_agent_content(agent_result: Dict[str, Any]) -> Optional[str]:
        """
        Extract content from an agent result.
        
        Args:
            agent_result: Result from an agent
            
        Returns:
            str: Extracted content or None if extraction failed
        """
        if not agent_result.get("success", False):
            return None
        
        result = agent_result.get("result")
        if result is None:
            return None
            
        # Handle different result formats
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            # Try common response field names
            for field in ["response", "content", "answer", "message", "output"]:
                if field in result and result[field]:
                    return result[field]
                    
            # If no recognized fields, return the whole dict as string
            return str(result)
        elif isinstance(result, list):
            # Join list items if they're strings
            if all(isinstance(item, str) for item in result):
                return "\n".join(result)
            return str(result)
        else:
            return str(result)
    
    def _combine_agent_results(agent_results: List[Dict[str, Any]]) -> str:
        """
        Combine results from multiple agents based on priority.
        
        Args:
            agent_results: List of agent results
            
        Returns:
            str: Combined response
        """
        # Filter out failed results
        valid_results = [r for r in agent_results if r.get("success", False)]
        
        if not valid_results:
            return "I'm sorry, I couldn't generate a response at this time."
        
        # Extract content from each result
        contents = []
        for result in valid_results:
            content = _extract_agent_content(result)
            if content:
                agent_name = result.get("agent", "unknown")
                contents.append((agent_name, content))
        
        if not contents:
            return "I'm sorry, I couldn't extract any valid response content."
        
        # If only one result, return it directly
        if len(contents) == 1:
            return contents[0][1]
            
        # Combine multiple results
        combined = "I have multiple responses for you:\n\n"
        for agent_name, content in contents:
            combined += f"From {agent_name}:\n{content}\n\n"
            
        return combined
    
    def _format_agent_response(response: str, max_length: int = 8000) -> str:
        """
        Format the agent response, ensuring it doesn't exceed max length.
        
        Args:
            response: Response to format
            max_length: Maximum length of the response
            
        Returns:
            str: Formatted response
        """
        if not response:
            return "I'm sorry, I couldn't generate a response at this time."
            
        # Trim response if needed
        if len(response) > max_length:
            trimmed = response[:max_length - 100]
            return trimmed + "...\n\n(Response truncated due to length)"
            
        return response
    
    def response_generator(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a response by combining results from multiple agents.
        
        Args:
            state: Current workflow state
            
        Returns:
            Dict: Updated workflow state with the generated response
        """
        start_time = time.time()
        request_id = state.get("request_id", str(uuid.uuid4()))
        user_id = state.get("user_id", "default_user")
        
        logger.info(f"[{request_id}] Generating response for user {user_id}")
        
        try:
            # Get agent results from state
            agent_results = state.get("agent_results", [])
            
            if not agent_results:
                logger.warning(f"[{request_id}] No agent results found in state")
                response = "I'm sorry, I don't have any results to provide a response."
            else:
                # Combine agent results
                combined_response = _combine_agent_results(agent_results)
                
                # Format the response
                response = _format_agent_response(combined_response, max_response_length)
                
                logger.info(f"[{request_id}] Generated response of length {len(response)}")
            
            # Update metrics
            metrics["execution_time"] = time.time() - start_time
            
            # Extract selected agents for the response metadata
            selected_agents = state.get("selected_agents", [])
            
            # Create a list of agent names that succeeded
            successful_agents = [
                result["agent"] for result in agent_results 
                if result.get("success", False)
            ]
            
            # Return updated state with response
            return {
                **state,
                "response": response,
                "response_metadata": {
                    "selected_agents": selected_agents,
                    "successful_agents": successful_agents,
                    "timestamp": time.time()
                },
                "metrics": {
                    **state.get("metrics", {}),
                    "response_generator": {
                        "execution_time": metrics["execution_time"],
                        "errors": metrics["errors"]
                    }
                }
            }
            
        except Exception as e:
            metrics["errors"] += 1
            logger.error(f"[{request_id}] Error generating response: {str(e)}")
            
            # Return error state
            return {
                **state,
                "error": f"Error generating response: {str(e)}",
                "response": "I'm sorry, I encountered an error while generating your response.",
                "metrics": {
                    **state.get("metrics", {}),
                    "response_generator": {
                        "execution_time": time.time() - start_time,
                        "errors": metrics["errors"]
                    }
                }
            }
    
    return response_generator 