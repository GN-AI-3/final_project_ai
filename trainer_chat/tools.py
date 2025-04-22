from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from .db_utils import db
from langchain.tools import Tool
import re

toolkit = SQLDatabaseToolkit(db=db, llm=ChatOpenAI(model="gpt-4o-mini"))
tools = toolkit.get_tools()

list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")

def get_clean_schema(table_name: str) -> str:
    raw_schema = db.get_table_info_no_throw(table_name.split(", "))
    clean_schema = re.sub(r"/\*.*?\*/", "", raw_schema, flags=re.DOTALL)
    return clean_schema

get_schema_tool = Tool.from_function(
    name="sql_db_schema",
    description="Return the schema for the given table name",
    func=get_clean_schema
)

@tool
def db_query_tool(query: str) -> str:
    """
    Execute a SQL query against the database and get back the result.
    If the query is not correct, an error message will be returned.
    If an error is returned, rewrite the query, check the query, and try again.
    """
    result = db.run_no_throw(query)
    if not result:
        return "Error: Query failed. Please rewrite your query and try again."
    return result 