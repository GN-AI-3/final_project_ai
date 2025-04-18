from langchain_openai import ChatOpenAI
from ..utils import make_supervisor_node
from . import create_paper_writing_graph, create_research_agent
from langgraph.types import Command
from typing import List, Optional, Literal
from langchain_core.messages import HumanMessage, trim_messages
from langgraph.graph import StateGraph, MessagesState, START, END

class State(MessagesState):
    next: str

def create_teams_supervisor():
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.56)

    teams_supervisor_node = make_supervisor_node(llm, ["research_team", "writing_team"])
    research_graph = create_research_agent()
    paper_writing_graph = create_paper_writing_graph()

    def call_research_team(state: State) -> Command[Literal["supervisor"]]:
        response = research_graph.invoke({"messages": state["messages"][-1]})
        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=response["messages"][-1].content, name="research_team"
                    )
                ]
            },
            goto="supervisor",
        )


    def call_paper_writing_team(state: State) -> Command[Literal["supervisor"]]:
        response = paper_writing_graph.invoke({"messages": state["messages"][-1]})
        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=response["messages"][-1].content, name="writing_team"
                    )
                ]
            },
            goto="supervisor",
        )


    # Define the graph.
    super_builder = StateGraph(State)
    super_builder.add_node("supervisor", teams_supervisor_node)
    super_builder.add_node("research_team", call_research_team)
    super_builder.add_node("writing_team", call_paper_writing_team)

    super_builder.add_edge(START, "supervisor")

    return super_builder.compile()