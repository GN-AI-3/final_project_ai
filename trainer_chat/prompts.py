from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from .tools import db_query_tool
from pydantic import BaseModel, Field

query_check_system = """You are a SQL expert with a strong attention to detail.
Double check the PostgreSQL query for common mistakes, including:
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins

If there are any of the above mistakes, rewrite the query. If there are no mistakes, just reproduce the original query.

You will call the appropriate tool to execute the query after running this check."""

query_check_prompt = ChatPromptTemplate.from_messages([
    ("system", query_check_system), ("placeholder", "{messages}")
])
query_check = query_check_prompt | ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(
    [db_query_tool], tool_choice="required"
)

query_gen_system = """You are a SQL expert with a strong attention to detail.

Given an input question, output a syntactically correct PostgreSQL query to run, then look at the results of the query and return the answer.

When generating the query:
Output the SQL query that answers the input question without a tool call.

You can order the results by a relevant column to return the most interesting examples in the database.
Never query for all the columns from a specific table, only ask for the relevant columns given the question.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database."""

query_gen_prompt = ChatPromptTemplate.from_messages([
    ("system", query_gen_system), ("placeholder", "{messages}")
])

class SubmitFinalAnswer(BaseModel):
    """Submit the final answer to the user based on the query results."""
    final_answer: str = Field(..., description="The final answer to the user")

query_gen = query_gen_prompt | ChatOpenAI(model="gpt-4o-mini", temperature=0)