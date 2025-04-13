"""
Parallel Agent Executor for LangGraph Supervisor
"""
import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Callable, Optional

logger = logging.getLogger("langgraph_supervisor.nodes.parallel_executor")

def create_parallel_agent_executor(agent_instances: Dict[str, Any] = None):
    """
    Create a parallel agent executor node that runs multiple agents concurrently.
    
    Args:
        agent_instances: Dictionary mapping agent names to their callable instances
        
    Returns:
        function: Parallel agent executor function
    """
    if agent_instances is None:
        # Default empty registry - should be provided in actual implementation
        agent_instances = {}
    
    # Track execution metrics
    metrics = {
        "execution_time": 0,
        "errors": 0,
        "agent_metrics": {}
    }
    
    async def execute_agent(agent_name: str, agent_fn: Callable, state: Dict[str, Any], request_id: str):
        """
        Execute a single agent and return its results.
        
        Args:
            agent_name: Name of the agent
            agent_fn: Agent function to execute
            state: Current workflow state
            request_id: Unique request identifier
            
        Returns:
            Dict: Agent execution results
        """
        agent_start_time = time.time()
        agent_metrics = {"execution_time": 0, "errors": 0}
        
        try:
            logger.info(f"[{request_id}] Executing agent: {agent_name}")
            
            # Execute the agent with the current state
            result = await agent_fn(state)
            
            # Record execution time
            agent_metrics["execution_time"] = time.time() - agent_start_time
            
            logger.info(f"[{request_id}] Agent {agent_name} completed in {agent_metrics['execution_time']:.2f}s")
            
            return {
                "agent": agent_name,
                "result": result,
                "metrics": agent_metrics,
                "success": True
            }
            
        except Exception as e:
            agent_metrics["errors"] += 1
            execution_time = time.time() - agent_start_time
            agent_metrics["execution_time"] = execution_time
            
            logger.error(f"[{request_id}] Error executing agent {agent_name}: {str(e)}")
            
            return {
                "agent": agent_name,
                "error": str(e),
                "metrics": agent_metrics,
                "success": False
            }
    
    async def parallel_agent_executor(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute selected agents in parallel and aggregate their results.
        
        Args:
            state: Current workflow state
            
        Returns:
            Dict: Updated workflow state with agent results
        """
        start_time = time.time()
        request_id = state.get("request_id", str(uuid.uuid4()))
        selected_agents = state.get("selected_agents", [])
        user_id = state.get("user_id", "default_user")
        
        logger.info(f"[{request_id}] Starting parallel execution of {len(selected_agents)} agents for user {user_id}")
        
        try:
            # Check if there are any selected agents
            if not selected_agents:
                logger.warning(f"[{request_id}] No agents selected for execution")
                return {
                    **state,
                    "agent_results": [],
                    "metrics": {
                        **state.get("metrics", {}),
                        "parallel_executor": {
                            "execution_time": 0,
                            "errors": 0,
                            "agent_metrics": {}
                        }
                    }
                }
            
            # Filter out agents that are not in the registry
            available_agents = [agent for agent in selected_agents if agent in agent_instances]
            
            if len(available_agents) < len(selected_agents):
                missing_agents = set(selected_agents) - set(available_agents)
                logger.warning(f"[{request_id}] Some agents are not available: {missing_agents}")
            
            # If no agents are available, return an error
            if not available_agents:
                logger.error(f"[{request_id}] None of the selected agents are available")
                return {
                    **state,
                    "error": "None of the selected agents are available",
                    "agent_results": [],
                    "metrics": {
                        **state.get("metrics", {}),
                        "parallel_executor": {
                            "execution_time": time.time() - start_time,
                            "errors": 1,
                            "agent_metrics": {}
                        }
                    }
                }
            
            # Create tasks for each agent
            agent_tasks = [
                execute_agent(agent_name, agent_instances[agent_name], state, request_id)
                for agent_name in available_agents
            ]
            
            # Execute all agents in parallel
            agent_results = await asyncio.gather(*agent_tasks)
            
            # Update agent metrics
            agent_metrics = {}
            for result in agent_results:
                agent_name = result["agent"]
                agent_metrics[agent_name] = result["metrics"]
            
            metrics["agent_metrics"] = agent_metrics
            metrics["execution_time"] = time.time() - start_time
            
            logger.info(f"[{request_id}] Completed parallel execution in {metrics['execution_time']:.2f}s")
            
            # Update the state with the agent results
            return {
                **state,
                "agent_results": agent_results,
                "metrics": {
                    **state.get("metrics", {}),
                    "parallel_executor": {
                        "execution_time": metrics["execution_time"],
                        "errors": metrics["errors"],
                        "agent_metrics": metrics["agent_metrics"]
                    }
                }
            }
            
        except Exception as e:
            metrics["errors"] += 1
            logger.error(f"[{request_id}] Error in parallel execution: {str(e)}")
            
            # Update the state with error information
            return {
                **state,
                "error": f"Error in parallel execution: {str(e)}",
                "agent_results": [],
                "metrics": {
                    **state.get("metrics", {}),
                    "parallel_executor": {
                        "execution_time": time.time() - start_time,
                        "errors": metrics["errors"],
                        "agent_metrics": metrics["agent_metrics"]
                    }
                }
            }
    
    return parallel_agent_executor 