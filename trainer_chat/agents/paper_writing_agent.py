from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from .paper_writing_tools import write_document, edit_document, read_document, create_outline
from typing import Literal
from ..utils import make_supervisor_node

class State(MessagesState):
    next: str

def create_paper_writing_graph():
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.56)

    doc_writer_agent = create_react_agent(
        llm,
        tools=[write_document, edit_document, read_document],
        prompt=(
            "You can read, write and edit documents based on note-taker's outlines. "
            "Don't ask follow-up questions."
        ),
    )

    def doc_writing_node(state: State) -> Command[Literal["supervisor"]]:
        result = doc_writer_agent.invoke(state)
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result["messages"][-1].content, name="doc_writer")
                ]
            },
            # We want our workers to ALWAYS "report back" to the supervisor when done
            goto="supervisor",
        )


    note_taking_agent = create_react_agent(
        llm,
        tools=[create_outline, read_document],
        prompt=(
            "You can read documents and create outlines for the document writer. "
            "Don't ask follow-up questions."
        ),
    )


    def note_taking_node(state: State) -> Command[Literal["supervisor"]]:
        result = note_taking_agent.invoke(state)
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result["messages"][-1].content, name="note_taker")
                ]
            },
            # We want our workers to ALWAYS "report back" to the supervisor when done
            goto="supervisor",
        )


    chart_generating_agent = create_react_agent(
        llm, tools=[read_document]
    )


    def chart_generating_node(state: State) -> Command[Literal["supervisor"]]:
        result = chart_generating_agent.invoke(state)
        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=result["messages"][-1].content, name="chart_generator"
                    )
                ]
            },
            # We want our workers to ALWAYS "report back" to the supervisor when done
            goto="supervisor",
        )


    doc_writing_supervisor_node = make_supervisor_node(
        llm, ["doc_writer", "note_taker", "chart_generator"]
    )

    # Create the graph here
    paper_writing_builder = StateGraph(State)
    paper_writing_builder.add_node("supervisor", doc_writing_supervisor_node)
    paper_writing_builder.add_node("doc_writer", doc_writing_node)
    paper_writing_builder.add_node("note_taker", note_taking_node)
    paper_writing_builder.add_node("chart_generator", chart_generating_node)

    paper_writing_builder.add_edge(START, "supervisor")
    
    return paper_writing_builder.compile()