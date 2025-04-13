"""
State Management for the LangGraph Supervisor
"""
import logging
import os
import uuid
import time
from typing import Any, Dict, List, Optional, TypedDict, Union
from dataclasses import dataclass, field

logger = logging.getLogger("langgraph_supervisor.state")

class AgentResult(TypedDict, total=False):
    """Type definition for an agent's execution result."""
    agent: str
    success: bool
    result: Any
    error: Optional[str]
    execution_time: float

class WorkflowState(TypedDict, total=False):
    """Type definition for the LangGraph Supervisor workflow state."""
    # Input fields
    request_id: str
    user_id: str
    message: str
    chat_history: List[Dict[str, Any]]
    
    # Processing fields
    selected_agents: List[str]
    agent_results: List[AgentResult]
    
    # Output fields
    response: str
    
    # Metadata fields
    error: Optional[str]
    metrics: Dict[str, Any]
    start_time: float
    end_time: Optional[float]
    
    # Internal fields
    agent_selection_metadata: Dict[str, Any]
    response_metadata: Dict[str, Any]

@dataclass
class SupervisorState(WorkflowState):
    """State for the LangGraph Supervisor workflows with additional fields specific to the supervisor"""
    request_id: str = ""
    user_id: str = ""  # User ID for context
    message: str = ""  # Current user message
    emotion_type: Optional[str] = None  # Emotion type (fatigue, sadness, anger, happiness, etc)
    emotion_score: float = 0.0  # Emotion score (positive for positive emotions, negative for negative emotions)
    conversation_context: Dict[str, Any] = field(default_factory=dict)  # 대화 맥락 저장
    chat_history: List[Dict[str, str]] = field(default_factory=list)  # Chat history
    categories: List[str] = field(default_factory=list)  # Categories the message belongs to
    selected_agents: List[str] = field(default_factory=list)  # Agents selected for execution
    agent_inputs: Dict[str, Any] = field(default_factory=dict)  # Inputs for each agent
    agent_outputs: Dict[str, Any] = field(default_factory=dict)  # Outputs from each agent
    agent_errors: Dict[str, str] = field(default_factory=dict)  # Errors from agents
    response: str = ""  # Final response
    used_nodes: List[str] = field(default_factory=list)  # Nodes used in the workflow

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary representation suitable for the workflow"""
        return {
            **super().to_dict(),
            "request_id": self.request_id,
            "user_id": self.user_id,
            "message": self.message,
            "emotion_type": self.emotion_type,
            "emotion_score": self.emotion_score,
            "conversation_context": self.conversation_context,
            "chat_history": self.chat_history,
            "categories": self.categories,
            "selected_agents": self.selected_agents,
            "agent_inputs": self.agent_inputs,
            "agent_outputs": self.agent_outputs,
            "agent_errors": self.agent_errors,
            "response": self.response,
            "used_nodes": self.used_nodes,
        }
    
    @classmethod
    def from_dict(cls, state_dict: Dict[str, Any]) -> "SupervisorState":
        """딕셔너리에서 상태를 생성"""
        state = cls()
        for key, value in state_dict.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state

class StateManager:
    """
    Manages the state for the LangGraph Supervisor workflows.
    
    This class handles storing and retrieving conversation history,
    tracking workflow state, and maintaining user session information.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the StateManager.
        
        Args:
            storage_path: Path to store conversation history (optional)
        """
        self.storage_path = storage_path
        
        # Create storage directory if specified and doesn't exist
        if self.storage_path and not os.path.exists(self.storage_path):
            try:
                os.makedirs(self.storage_path)
                logger.info(f"Created state storage directory at {self.storage_path}")
            except Exception as e:
                logger.warning(f"Failed to create storage directory: {str(e)}")
                self.storage_path = None
    
    def initialize_state(
        self, 
        message: str, 
        user_id: str = "default_user",
        request_id: Optional[str] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> WorkflowState:
        """
        Initialize a new state for a workflow run.
        
        Args:
            message: User message to process
            user_id: Identifier for the user
            request_id: Unique identifier for this request
            chat_history: Prior conversation history
            
        Returns:
            WorkflowState: Initial state for the workflow
        """
        if request_id is None:
            request_id = str(uuid.uuid4())
        
        if chat_history is None:
            chat_history = []
        
        return {
            "request_id": request_id,
            "user_id": user_id,
            "message": message,
            "chat_history": chat_history,
            "selected_agents": [],
            "agent_results": [],
            "response": "",
            "error": None,
            "metrics": {},
            "start_time": time.time(),
            "end_time": None
        }
    
    def save_chat_history(
        self, 
        user_id: str,
        message: str,
        response: str,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Save the chat history with the new message and response.
        
        Args:
            user_id: User identifier
            message: User message
            response: System response
            chat_history: Existing chat history
            
        Returns:
            List: Updated chat history
        """
        if chat_history is None:
            chat_history = []
        
        # Add the new message and response to history
        updated_history = chat_history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": response}
        ]
        
        # Save to persistent storage if configured
        if self.storage_path:
            try:
                user_file = os.path.join(self.storage_path, f"{user_id}_history.json")
                import json
                with open(user_file, 'w') as f:
                    json.dump(updated_history, f)
                logger.debug(f"Saved chat history for user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to save chat history: {str(e)}")
        
        return updated_history
    
    def load_chat_history(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Load chat history for a user from storage.
        
        Args:
            user_id: User identifier
            
        Returns:
            List: Chat history or empty list if not found
        """
        if not self.storage_path:
            return []
        
        user_file = os.path.join(self.storage_path, f"{user_id}_history.json")
        
        if not os.path.exists(user_file):
            return []
        
        try:
            import json
            with open(user_file, 'r') as f:
                history = json.load(f)
            logger.debug(f"Loaded chat history for user {user_id}")
            return history
        except Exception as e:
            logger.warning(f"Failed to load chat history: {str(e)}")
            return []

def create_initial_state(
    message: str,
    user_id: str = "default_user",
    chat_history: Optional[List[Dict[str, Any]]] = None,
    request_id: Optional[str] = None
) -> WorkflowState:
    """
    Create an initial workflow state.
    
    Args:
        message: User message to process
        user_id: ID of the user making the request
        chat_history: Previous chat history
        request_id: Unique ID for the request (generated if not provided)
        
    Returns:
        WorkflowState: Initial state for the workflow
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
    
    if chat_history is None:
        chat_history = []
    
    return {
        "request_id": request_id,
        "user_id": user_id,
        "message": message,
        "chat_history": chat_history,
        "selected_agents": [],
        "agent_results": [],
        "response": "",
        "error": None,
        "metrics": {},
        "start_time": time.time(),
        "end_time": None
    }

def update_metrics(
    state: WorkflowState,
    component_name: str,
    execution_time: float,
    errors: int = 0
) -> WorkflowState:
    """
    Update metrics for a component in the workflow state.
    
    Args:
        state: Current workflow state
        component_name: Name of the component
        execution_time: Execution time in seconds
        errors: Number of errors encountered
        
    Returns:
        WorkflowState: Updated workflow state
    """
    metrics = state.get("metrics", {})
    
    component_metrics = metrics.get(component_name, {})
    component_metrics["execution_time"] = execution_time
    component_metrics["errors"] = errors
    
    metrics[component_name] = component_metrics
    
    return {
        **state,
        "metrics": metrics
    }

def add_error(
    state: WorkflowState,
    error_message: str,
    component_name: Optional[str] = None
) -> WorkflowState:
    """
    Add an error message to the workflow state.
    
    Args:
        state: Current workflow state
        error_message: Error message to add
        component_name: Optional name of the component that generated the error
        
    Returns:
        WorkflowState: Updated workflow state
    """
    if component_name:
        error_message = f"[{component_name}] {error_message}"
    
    return {
        **state,
        "error": error_message,
        "response": state.get("response") or "I'm sorry, I encountered an error while processing your message."
    }

def finalize_state(state: WorkflowState) -> WorkflowState:
    """
    Finalize the workflow state for output.
    
    Args:
        state: Current workflow state
        
    Returns:
        WorkflowState: Finalized workflow state
    """
    return {
        **state,
        "end_time": time.time(),
        "execution_time": time.time() - state.get("start_time", time.time())
    } 