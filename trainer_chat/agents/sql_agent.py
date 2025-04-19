from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import Runnable
from langchain_community.utilities import SQLDatabase
from ..utils import PG_URI, summarize_db_schema
from trainer_chat.prompts.sql_prompt import SQL_PROMPT

# 1. 상태 정의
class SQLAgentState(TypedDict):
    user_input: str
    sql_query: str
    sql_result: str
    final_answer: str

# 2. PostgreSQL 연결
db = SQLDatabase.from_uri(PG_URI)

# 3. LLM 준비
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 4. SQLQueryGeneratorNode
sql_prompt = PromptTemplate.from_template(SQL_PROMPT)

def generate_sql(state: SQLAgentState) -> SQLAgentState:
    # TODO: 질문에 따른 테이블
    schema = summarize_db_schema(db._engine, ['pt_schedule', 'pt_contract', 'member'])
    # TODO: trainer_id 바인딩
    prompt = sql_prompt.format(schema=schema, user_question=state['user_input'], trainer_id=1)
    print("[LOG] SQL 프롬프트:", prompt)
    sql = llm.invoke(prompt)
    print("[LOG] 생성된 SQL 쿼리:", sql.content.strip())
    return {**state, "sql_query": sql.content.strip()}

# 5. SQLExecutorNode
def execute_sql(state: SQLAgentState) -> SQLAgentState:
    print("[LOG] 실행할 SQL 쿼리:", state["sql_query"])
    try:
        result = db.run(state["sql_query"])
    except Exception as e:
        result = f"[SQL ERROR] {str(e)}"
    print("[LOG] SQL 실행 결과:", result)
    return {**state, "sql_result": result}

# 6. AnswerFormatterNode
answer_prompt = PromptTemplate.from_template("""
Here is the SQL query result:

{sql_result}

Summarize this result in a friendly and clear sentence for the user.
""")

def generate_answer(state: SQLAgentState) -> SQLAgentState:
    print("[LOG] AnswerFormatter에 전달된 sql_result:", state["sql_result"])
    prompt = answer_prompt.format(sql_result=state["sql_result"])
    print("[LOG] AnswerFormatter 프롬프트:", prompt)
    answer = llm.invoke(prompt)
    print("[LOG] 최종 응답:", answer.content.strip())
    return {**state, "final_answer": answer.content.strip()}

# 7. 그래프 정의
builder = StateGraph(SQLAgentState)

builder.add_node("generate_sql", generate_sql)
builder.add_node("execute_sql", execute_sql)
builder.add_node("generate_answer", generate_answer)

builder.set_entry_point("generate_sql")
# builder.add_edge("generate_sql", "execute_sql")
# builder.add_edge("execute_sql", "generate_answer")
# builder.add_edge("generate_answer", END)

builder.add_edge("generate_sql", END)


def create_sql_agent():
    return builder.compile()

if __name__ == "__main__":
    # 에이전트 생성
    app = create_sql_agent()
    
    # 테스트용 입력 상태
    state = {
        "user_input": "다음주 PT 일정 잡힌 회원 알려줘"
    }
    
    # 에이전트 실행
    final_state = app.invoke(state)