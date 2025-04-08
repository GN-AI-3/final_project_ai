from typing import Dict, Any, List, Optional, Type, Callable
from langchain_openai import ChatOpenAI
from langchain.tools import Tool
from langchain.prompts import ChatPromptTemplate
import inspect
import json
from .state import AgentState

class BaseAgent:
    """기본 에이전트 클래스"""
    
    DEFAULT_MODEL = "gpt-4o-mini"
    
    def __init__(self, model_name: str = DEFAULT_MODEL):
        """초기화"""
        self.model_name = model_name
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0
        )
        self.functions = []
        self._initialize_tools()
        
    def _initialize_tools(self):
        """@tool 데코레이터가 붙은 모든 메서드를 자동으로 수집하여 Tool 객체로 변환"""
        # 클래스 내의 모든 메서드를 검사
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            # @tool 데코레이터가 있는지 확인
            if hasattr(method, '_tool_metadata'):
                # Tool 객체 생성
                tool = Tool(
                    name=method._tool_metadata.get('name', name),
                    description=method._tool_metadata.get('description', ''),
                    func=method
                )
                self.functions.append(tool)
        
        # LLM에 도구 바인딩
        self.llm = self.llm.bind_tools(self.functions)
    
    def bind_llm(self, llm: ChatOpenAI):
        """외부에서 LLM을 바인딩"""
        self.llm = llm
        self.llm = self.llm.bind_tools(self.functions)
    
    def get_tools(self) -> List[Tool]:
        """도구 목록 반환"""
        return self.functions
    
    async def process(self, state: AgentState) -> AgentState:
        """기본 처리 메서드 - 서브 클래스에서 오버라이드"""
        return state 