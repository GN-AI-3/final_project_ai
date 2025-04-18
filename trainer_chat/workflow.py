import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage
from langgraph.graph import MessagesState, StateGraph, START, END

from langgraph.prebuilt import create_react_agent
from trainer_chat.supervisor_node import supervisor_node
from trainer_chat.tools import tavily_tool
from langgraph.types import Command
from langchain_openai import ChatOpenAI
from typing import Literal
from dotenv import load_dotenv

load_dotenv()

class State(MessagesState):
    next: str

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.56)
    
research_agent = create_react_agent(
    llm, tools=[tavily_tool], prompt="You are a researcher. DO NOT do any math."
)


def research_node(state: State) -> Command[Literal["supervisor"]]:
    result = research_agent.invoke(state)
    return Command(
        update={
            "messages": [
                HumanMessage(content=result["messages"][-1].content, name="researcher")
            ]
        },
        goto="supervisor",
    )


# NOTE: THIS PERFORMS ARBITRARY CODE EXECUTION, WHICH CAN BE UNSAFE WHEN NOT SANDBOXED
# code_agent = create_react_agent(llm, tools=[python_repl_tool])


# def code_node(state: State) -> Command[Literal["supervisor"]]:
#     result = code_agent.invoke(state)
#     return Command(
#         update={
#             "messages": [
#                 HumanMessage(content=result["messages"][-1].content, name="coder")
#             ]
#         },
#         goto="supervisor",
#     )

def create_trainer_chat_workflow(): 
    builder = StateGraph(State)
    builder.add_edge(START, "supervisor")
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("researcher", research_node)
    # builder.add_node("coder", code_node)
    graph = builder.compile()

    return graph

if __name__ == "__main__":
    workflow = create_trainer_chat_workflow()
    print("안녕하세요! 저는 AI 트레이너입니다. 무엇이든 물어보세요. (종료하려면 'exit' 또는 'quit'를 입력하세요)")
    
    while True:
        user_input = input("\n당신: ")
        
        if user_input.lower() in ['exit', 'quit']:
            print("대화를 종료합니다. 감사합니다!")
            break
            
        if user_input.strip():
            result = workflow.invoke({"messages": [HumanMessage(content=user_input)]})
            print("\nAI:", result["messages"][-1].content)
