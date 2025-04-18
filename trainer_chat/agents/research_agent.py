from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from typing import Literal
from .research_tools import tavily_tool, scrape_webpages
from ..utils import make_supervisor_node

class State(MessagesState):
    next: str

def create_research_agent():
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.56)

    search_agent = create_react_agent(llm, tools=[tavily_tool])


    def search_node(state: State) -> Command[Literal["supervisor"]]:
        result = search_agent.invoke(state)
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result["messages"][-1].content, name="search")
                ]
            },
            # We want our workers to ALWAYS "report back" to the supervisor when done
            goto="supervisor",
        )


    web_scraper_agent = create_react_agent(llm, tools=[scrape_webpages])


    def web_scraper_node(state: State) -> Command[Literal["supervisor"]]:
        result = web_scraper_agent.invoke(state)
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result["messages"][-1].content, name="web_scraper")
                ]
            },
            # We want our workers to ALWAYS "report back" to the supervisor when done
            goto="supervisor",
        )


    research_supervisor_node = make_supervisor_node(llm, ["search", "web_scraper"])

    research_builder = StateGraph(State)
    research_builder.add_node("supervisor", research_supervisor_node)
    research_builder.add_node("search", search_node)
    research_builder.add_node("web_scraper", web_scraper_node)

    research_builder.add_edge(START, "supervisor")
    
    return research_builder.compile()
