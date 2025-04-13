"""
Agent Selector for LangGraph Supervisor

This module provides a function to create an agent selector node that determines
which agents to run based on the user's message.
"""
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger("langgraph_supervisor.nodes.agent_selector")

def create_agent_selector(
    llm: BaseChatModel,
    available_agents: List[str],
    max_agents: int = 3
):
    """
    Create an agent selector node that decides which agents to run based on the user's message.
    
    Args:
        llm: LLM to use for agent selection
        available_agents: List of available agent names
        max_agents: Maximum number of agents to select
        
    Returns:
        function: Agent selector function
    """
    # Track execution metrics
    metrics = {
        "execution_time": 0,
        "errors": 0
    }
    
    # Create prompt template for agent selection
    agent_selection_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an agent selector that determines which specialized agents should handle a user's query.
        
Available agents:
{agent_descriptions}

Your task is to analyze the user's message and select the most appropriate agent(s) to handle it.
- Choose at most {max_agents} agents.
- Only select agents from the available list.
- For each selected agent, briefly explain why you've chosen it.
- Return your answer in a JSON format with an "agents" list containing the selected agent names.

Example output:
```json
{
  "agents": ["Agent1", "Agent2"],
  "explanation": "Agent1 is selected because the query relates to scheduling. Agent2 is selected to provide more detailed information."
}
```"""),
        ("human", "{message}")
    ])
    
    def _get_agent_descriptions(agents: List[str]) -> str:
        """Generate descriptions for each available agent."""
        descriptions = []
        for agent in agents:
            if "food" in agent.lower():
                descriptions.append(f"- {agent}: Handles food-related queries, meal planning, and nutrition information.")
            elif "schedule" in agent.lower():
                descriptions.append(f"- {agent}: Manages scheduling, calendar events, and time-related questions.")
            elif "routine" in agent.lower():
                descriptions.append(f"- {agent}: Handles daily routines, habits, and productivity-related queries.")
            else:
                descriptions.append(f"- {agent}: Handles general queries.")
        
        return "\n".join(descriptions)
    
    def agent_selector(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Select agents based on the user's message.
        
        Args:
            state: Current workflow state
            
        Returns:
            Dict: Updated workflow state with selected agents
        """
        start_time = time.time()
        request_id = state.get("request_id", str(uuid.uuid4()))
        user_id = state.get("user_id", "default_user")
        message = state.get("message", "")
        
        logger.info(f"[{request_id}] Selecting agents for user {user_id}")
        
        try:
            if not message:
                logger.warning(f"[{request_id}] No message found in state")
                return {
                    **state,
                    "selected_agents": [],
                    "error": "No message provided for agent selection"
                }
            
            # Generate agent descriptions
            agent_descriptions = _get_agent_descriptions(available_agents)
            
            # Format prompt with message and agent descriptions
            prompt = agent_selection_prompt.format_messages(
                message=message,
                agent_descriptions=agent_descriptions,
                max_agents=max_agents
            )
            
            # Call LLM to select agents
            logger.info(f"[{request_id}] Calling LLM for agent selection")
            llm_response = llm.invoke(prompt)
            
            # Extract agent names from response
            response_text = llm_response.content
            
            # Parse the response to extract agent names
            # This is a simplified version - in production, you'd want more robust parsing
            import json
            import re
            
            # Try to extract JSON from the response
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # If no JSON code block, try to find JSON directly
                json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response_text
            
            try:
                selection_data = json.loads(json_str)
                selected_agents = selection_data.get("agents", [])
                explanation = selection_data.get("explanation", "No explanation provided")
            except json.JSONDecodeError:
                logger.warning(f"[{request_id}] Failed to parse JSON from LLM response")
                # Fallback: try to extract agent names directly from text
                selected_agents = [
                    agent for agent in available_agents 
                    if agent in response_text
                ]
                explanation = "Extracted agent names directly from text (JSON parsing failed)"
            
            # Validate selected agents
            valid_selected_agents = [agent for agent in selected_agents if agent in available_agents]
            
            # Cap at max_agents
            if len(valid_selected_agents) > max_agents:
                valid_selected_agents = valid_selected_agents[:max_agents]
                
            # Log selection results
            logger.info(f"[{request_id}] Selected agents: {', '.join(valid_selected_agents)}")
            
            # Update metrics
            metrics["execution_time"] = time.time() - start_time
            
            # Return updated state with selected agents
            return {
                **state,
                "selected_agents": valid_selected_agents,
                "agent_selection_metadata": {
                    "explanation": explanation,
                    "raw_llm_response": response_text,
                    "timestamp": time.time()
                },
                "metrics": {
                    **state.get("metrics", {}),
                    "agent_selector": {
                        "execution_time": metrics["execution_time"],
                        "errors": metrics["errors"]
                    }
                }
            }
            
        except Exception as e:
            metrics["errors"] += 1
            logger.error(f"[{request_id}] Error selecting agents: {str(e)}")
            
            # Return error state
            return {
                **state,
                "selected_agents": [],
                "error": f"Error selecting agents: {str(e)}",
                "metrics": {
                    **state.get("metrics", {}),
                    "agent_selector": {
                        "execution_time": time.time() - start_time,
                        "errors": metrics["errors"]
                    }
                }
            }
    
    return agent_selector 