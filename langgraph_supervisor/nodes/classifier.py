"""
Classifier Component for the LangGraph Supervisor
"""
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Callable

from langchain_core.language_models import BaseLanguageModel

logger = logging.getLogger("langgraph_supervisor.nodes.classifier")

def create_classifier(
    llm: BaseLanguageModel,
    agents: List[str],
    categories: Optional[List[str]] = None,
    agent_descriptions: Optional[Dict[str, str]] = None
) -> Callable:
    """
    Creates a classifier function that determines which agents should handle a user message.
    
    Args:
        llm: Language model to use for classification
        agents: List of available agent names
        categories: Optional list of categories for classification
        agent_descriptions: Optional descriptions of each agent's capabilities
        
    Returns:
        Callable: A function that classifies user messages
    """
    agent_descriptions = agent_descriptions or {}
    categories = categories or []
    
    # Create agent description text
    agent_desc_text = ""
    for agent_name in agents:
        desc = agent_descriptions.get(agent_name, f"Agent that handles {agent_name} related queries")
        agent_desc_text += f"- {agent_name}: {desc}\n"
    
    # Create category text if categories are provided
    category_text = ""
    if categories:
        category_text = "Categories:\n" + "\n".join([f"- {cat}" for cat in categories])
    
    def classifier(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classifies a user message to determine appropriate agents and categories.
        
        Args:
            state: Current workflow state
            
        Returns:
            Dict: Updated state with classification results
        """
        request_id = state.get("request_id", str(uuid.uuid4()))
        user_id = state.get("user_id", "default_user")
        message = state.get("message", "")
        
        if not message:
            logger.warning(f"Empty message received for classification, request_id: {request_id}")
            return {
                **state,
                "selected_agents": [agents[0]],  # Default to first agent
                "categories": []
            }
        
        logger.info(f"Classifying message for user {user_id}, request_id: {request_id}")
        start_time = time.time()
        
        try:
            # Prepare prompt for the LLM
            prompt = f"""
You are a classifier that analyzes user messages to determine which specialized agents should handle the request.

Available agents:
{agent_desc_text}

{category_text}

User message: "{message}"

Based on the user message, determine:
1. Which agent(s) should handle this request? Choose from: {', '.join(agents)}
2. What categories does this message fall into? {f'Choose from: {", ".join(categories)}' if categories else 'List any relevant categories.'}

Respond in JSON format:
{{
  "selected_agents": ["agent_name"],
  "categories": ["category1", "category2"]
}}

Only include agents that are directly relevant to handling this request.
"""
            
            # Get classification from LLM
            response = llm.invoke(prompt)
            
            # Extract JSON from response
            import json
            import re
            
            # Find JSON content in the response
            json_match = re.search(r'({.*})', response.content.replace('\n', ' '), re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                logger.warning(f"Could not extract JSON from LLM response, falling back to default agent. Request_id: {request_id}")
                result = {"selected_agents": [agents[0]], "categories": []}
            
            # Validate selected agents
            selected_agents = [agent for agent in result.get("selected_agents", []) if agent in agents]
            if not selected_agents:
                selected_agents = [agents[0]]  # Default to first agent if none selected
                
            # Extract categories
            result_categories = result.get("categories", [])
            if categories:
                # Filter to only valid categories if a list was provided
                result_categories = [cat for cat in result_categories if cat in categories]
            
            execution_time = time.time() - start_time
            logger.info(f"Classification completed in {execution_time:.2f}s. Selected agents: {selected_agents}, categories: {result_categories}")
            
            # Update metrics
            metrics = state.get("metrics", {})
            metrics["classifier_time"] = execution_time
            
            return {
                **state,
                "selected_agents": selected_agents,
                "categories": result_categories,
                "metrics": metrics
            }
            
        except Exception as e:
            logger.error(f"Error in classifier: {str(e)}")
            
            # Default to first agent on error
            return {
                **state,
                "selected_agents": [agents[0]],
                "categories": [],
                "error": f"Classification error: {str(e)}"
            }
    
    return classifier 