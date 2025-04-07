from typing import List, Dict, Any, Optional

from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain.memory import ConversationBufferMemory

from tools import get_user_schedule, add_reservation, modify_reservation
from utils.date_manager import DateManager
from utils.prompt_manager import PromptManager


class ScheduleChatbot:
    def __init__(self):
        self._initialize_llm()
        self._initialize_tools()
        self._initialize_prompt()
        self._initialize_memory()
        self._initialize_agent()
        self.chat_history = []

    def _initialize_llm(self) -> None:
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            streaming=True
        )

    def _initialize_tools(self) -> None:
        self.tools = [get_user_schedule, add_reservation, modify_reservation]
        self.functions = [convert_to_openai_function(t) for t in self.tools]

    def _initialize_prompt(self) -> None:
        system_prompt = PromptManager.load_system_prompt()
        formatted_date, _ = DateManager.get_formatted_date()
        system_prompt = f"오늘은 {formatted_date}입니다.\n\n{system_prompt}\n\n 예약은 오늘 이후의 날짜로만 가능해요."
        self.prompt = PromptManager.create_prompt_template(system_prompt)

    def _initialize_memory(self) -> None:
        self.memory = ConversationBufferMemory(
            return_messages=True,
            memory_key="chat_history"
        )
        # context도 메모리에 같이 저장 (초기화 시 함께 설정)
        self.memory.chat_memory.context = {}

    def _initialize_agent(self) -> None:
        agent = (
            {
                "input": lambda x: x["input"],
                "agent_scratchpad": lambda x: format_to_openai_function_messages(
                    x["intermediate_steps"]
                ),
                "chat_history": lambda x: x["chat_history"],
            }
            | self.prompt
            | self.llm.bind(functions=self.functions)
            | OpenAIFunctionsAgentOutputParser()
        )
        self.agent_executor = AgentExecutor(agent=agent, tools=self.tools, verbose=False)

    def process_message(self, message: str) -> str:
        try:
            context = getattr(self.memory.chat_memory, "context", {})

            # 누락된 슬롯에 응답하는 경우
            if context.get("waiting_for_slots"):
                for slot in context["waiting_for_slots"]:
                    context["collected_slots"][slot] = message
                    break  # 한 턴에 하나씩 수집

                # 아직 누락된 게 남아 있다면 계속 질문
                remaining = [
                    s for s in context["waiting_for_slots"]
                    if s not in context["collected_slots"]
                ]
                if remaining:
                    context["waiting_for_slots"] = remaining
                    self.memory.chat_memory.context = context
                    return f"{remaining[0]} 정보를 알려주시겠어요?"

                # 모든 슬롯 수집 완료 → 직접 함수 호출
                func_name = context["tool_name"]
                func_args = context["collected_slots"]

                # context 초기화
                self.memory.chat_memory.context = {}

                # 직접 함수 호출
                for tool in self.tools:
                    if tool.__name__ == func_name:
                        result = tool(**func_args)
                        self.memory.chat_memory.add_user_message(message)
                        self.memory.chat_memory.add_ai_message(result)
                        return result

            # 일반 메시지 처리
            result = self.agent_executor.invoke({
                "input": message,
                "chat_history": self.memory.chat_memory.messages
            })

            # 대화 저장
            self.memory.chat_memory.add_user_message(message)
            self.memory.chat_memory.add_ai_message(result["output"])

            # tool call 분석
            intermediate_steps = result.get("intermediate_steps", [])
            if intermediate_steps:
                ai_msg, _ = intermediate_steps[-1]
                if isinstance(ai_msg, AIMessage) and hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
                    tool_call = ai_msg.tool_calls[0]
                    args = tool_call.get("args", {})
                    missing_slots = [
                        k for k, v in args.items()
                        if v in [None, "", "null"]
                    ]
                    # 예외 처리로 required fields 필터링 가능 (지금은 다 체크)
                    if missing_slots:
                        # context 저장
                        context = {
                            "waiting_for_slots": missing_slots,
                            "collected_slots": {
                                k: v for k, v in args.items() if k not in missing_slots
                            },
                            "tool_name": tool_call["name"]
                        }
                        self.memory.chat_memory.context = context
                        return f"{missing_slots[0]} 정보를 알려주시겠어요?"

            return result["output"]

        except Exception as e:
            return f"죄송해요. 오류가 발생했어요: {str(e)}"


def call_chatbot(messages: List[Dict[str, Any]]) -> str:
    try:
        if not hasattr(call_chatbot, "chatbot_instance"):
            call_chatbot.chatbot_instance = ScheduleChatbot()

        chatbot = call_chatbot.chatbot_instance

        last_message = messages[-1]
        if isinstance(last_message, dict):
            message_content = last_message["content"]
        elif isinstance(last_message, HumanMessage):
            message_content = last_message.content
        else:
            return "죄송해요. 메시지 형식이 올바르지 않아요."

        return chatbot.process_message(message_content)

    except Exception as e:
        return "죄송해요. 문제가 발생했어요. 다시 시도해 주시겠어요?"
