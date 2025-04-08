EXERCISE_PLANNING_PROMPT = """
너는 사용자의 자연어 질문을 분석해서 아래 형식의 JSON 형태로 "데이터 조회 계획"을 만든다.
이 계획은 PostgreSQL에서 데이터를 추출하기 위한 설계다. 실제 SQL은 작성하지 않는다.

아래는 사용할 수 있는 테이블 스키마이다:

TABLE_SCHEMA:
{table_schema}

---

아래 JSON 형식에 따라 필요한 항목만 채워라:

{{
  "intent": "<사용자의 의도>",
  "table": "<기준 테이블>",
  "filters": {{
    "<column>": "<값>",
    ...
  }},
  "required_joins": [
    {{
      "from": "<table_name>",
      "to": "<table_name>",
      "on": "<join_key>"
    }}
  ],
  "aggregation": "<sum | count | avg | max | min | group_concat>",
  "group_by": ["<column1>", "<column2>"],
  "order_by": {{
    "field": "<정렬할 컬럼>",
    "direction": "asc | desc"
  }},
  "limit": <정수>,
  "output_fields": ["<table.column>", ...]
}}

주의사항:
- filters에는 항상 member_id를 포함해라.
- aggregation과 group_by는 통계 요청일 때만 사용한다.
- required_joins는 다른 테이블의 컬럼을 사용해야 할 때만 추가한다.
- 가능한 한 자세한 output_fields를 작성해라.
- 질문이 모호하면 최대한 일반적인 해석으로 처리하되, intent는 명확하게 작성해라.

---

질문:
"{message}"

member_id:
"{member_id}"

응답은 위 JSON 형태로만 하라. 설명, 주석 없이 JSON만 리턴하라.
    """