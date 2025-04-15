import os

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


class PromptManager:
    """프롬프트 관리 클래스"""
    
    @staticmethod
    def load_system_prompt() -> str:
        """시스템 프롬프트를 로드합니다.
        
        Returns:
            str: 시스템 프롬프트 문자열
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_file_path = os.path.join(current_dir, "..", "prompt_kr.txt")
        
        with open(prompt_file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    
    @staticmethod
    def create_prompt_template(system_prompt: str) -> ChatPromptTemplate:
        """프롬프트 템플릿을 생성합니다.
        
        Args:
            system_prompt: 시스템 프롬프트 문자열
            
        Returns:
            ChatPromptTemplate: 생성된 프롬프트 템플릿
        """
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]) 