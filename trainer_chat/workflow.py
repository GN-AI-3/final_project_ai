from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.messages import AIMessage, ToolMessage
from typing import Annotated, Literal
from typing_extensions import TypedDict
from .tools import list_tables_tool, get_schema_tool, db_query_tool
from .prompts import query_check, query_gen, SubmitFinalAnswer
from langchain_openai import ChatOpenAI

# State 정의
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

# 에러 핸들링 유틸리티
def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }

from langgraph.prebuilt import ToolNode
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks

def create_tool_node_with_fallback(tools: list) -> RunnableWithFallbacks:
    return ToolNode(tools).with_fallbacks([
        RunnableLambda(handle_tool_error)
    ], exception_key="error")

# 워크플로우 정의
def first_tool_call(state: State) -> dict[str, list[AIMessage]]:
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "sql_db_list_tables",
                        "args": {},
                        "id": "tool_abcd123",
                    }
                ],
            )
        ]
    }

def model_check_query(state: State) -> dict[str, list[AIMessage]]:
    return {"messages": [query_check.invoke({"messages": [state["messages"][-1]]})]}

model_get_schema = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools([
    get_schema_tool
])

def query_gen_node(state: State):
    message = query_gen.invoke(state)
    tool_messages = []
    if message.tool_calls:
        for tc in message.tool_calls:
            if tc["name"] != "SubmitFinalAnswer":
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: The wrong tool was called: {tc['name']}. Please fix your mistakes. Remember to only call SubmitFinalAnswer to submit the final answer. Generated queries should be outputted WITHOUT a tool call.",
                        tool_call_id=tc["id"],
                    )
                )
    else:
        tool_messages = []
    return {"messages": [message] + tool_messages}

def should_continue(state: State) -> Literal[END, "correct_query", "query_gen"]:
    messages = state["messages"]
    last_message = messages[-1]
    if getattr(last_message, "tool_calls", None):
        return END
    if last_message.content.startswith("Error:"):
        return "query_gen"
    else:
        return "correct_query"

workflow = StateGraph(State)
workflow.add_node("first_tool_call", first_tool_call)
workflow.add_node("list_tables_tool", create_tool_node_with_fallback([list_tables_tool]))
workflow.add_node("get_schema_tool", create_tool_node_with_fallback([get_schema_tool]))
workflow.add_node(
    "model_get_schema",
    lambda state: {
        "messages": [model_get_schema.invoke(state["messages"])],
    },
)
workflow.add_node("query_gen", query_gen_node)
workflow.add_node("correct_query", model_check_query)
workflow.add_node("execute_query", create_tool_node_with_fallback([db_query_tool]))
workflow.add_edge(START, "first_tool_call")
workflow.add_edge("first_tool_call", "list_tables_tool")
workflow.add_edge("list_tables_tool", "model_get_schema")
workflow.add_edge("model_get_schema", "get_schema_tool")
workflow.add_edge("get_schema_tool", "query_gen")
workflow.add_conditional_edges(
    "query_gen",
    should_continue,
)
workflow.add_edge("correct_query", "execute_query")
workflow.add_edge("execute_query", "query_gen")

app = workflow.compile()

if __name__ == "__main__":
    messages = app.invoke(
        {"messages": [("user", "다음주 수업 있는 회원 누구야?")]},
        {"recursion_limit": 10}
    )
    json_str = messages["messages"][-1].tool_calls[0]["args"]["final_answer"]
    print(json_str)