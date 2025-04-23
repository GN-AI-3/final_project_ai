EXERCISE_PLANNING_PROMPT = """
너는 사용자의 자연어 질문을 분석해서 아래 형식의 JSON 형태로 "데이터 조회 계획"을 만든다.
이 계획은 PostgreSQL에서 데이터를 추출하기 위한 설계다. 실제 SQL은 작성하지 않는다.

아래는 사용할 수 있는 테이블 스키마이다:

TABLE_SCHEMA:
{table_schema}

TABLE_SCHEMA에 정의된 컬럼 중 id 는 모두 정수이다.

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

EXERCISE_PLANNING_PROMPT_2 = """
  너는 사용자의 자연어 발화 안에서 **여러 개의 작업 목적(intent)** 이 있는지 파악하고, 각각을 아래 JSON 형태로 **배열로 반환**한다.

  ---

  가능한 intent 종류:
  - 저장: 데이터를 저장하고자 할 때
  - 조회: 데이터를 조회하고자 할 때
  - 추천: 추천을 받고자 할 때
  - 분석: 과거 데이터를 분석하고자 할 때
  - 질문: 어떤 정보를 묻고자 할 때
  - 기타: 위에 속하지 않는 경우

  ---

  JSON 출력 형식:

  [
    {{
      "intent": "<저장|조회|추천|질문|기타>",
      "action": "<실행하고자 하는 일>",
      "table": "<대상 테이블 (해당되는 경우)>",
      "data": {{ ... }},
      "filters": {{ ... }},
      "target_exercise": "...",  // 해당 시 사용
      "symptom": "...",          // 해당 시 사용
      ...
    }},
    ...
  ]

  ---

  주의:
  - intent가 여러 개일 경우, JSON 객체를 배열로 나눠 각각 작성
  - member_id는 data나 filter에 반드시 포함
  - 질문이 모호하더라도 추론해서 intent를 나눠라
  - 설명 없이 JSON만 리턴

  ---

  사용자 발화:
  "{message}"

  member_id:
  "{member_id}"

"""

EXERCISE_PLANNING_PROMPT_3 = """
너는 지능적인 AI 플래너다. 사용자의 자연어 질문을 이해하고, 아래 제공된 정보들을 바탕으로 **질문을 해결하기 위한 단계별 작업 계획(JSON 배열)** 을 수립하라.

---

[1] PostgreSQL 테이블 스키마:

{table_schema}

[2] 사용 가능한 Tool 목록:

{tool_descriptions}

각 tool은 특정 기능을 수행하는 도구이며, 다음과 같은 형식으로 호출한다:

- "tool": 사용할 tool 이름 (없으면 null 또는 생략 가능)
- "input": 해당 tool에 전달할 입력값
- "description": 이 단계의 목적과 이유

단, tool 없이도 LLM의 지식이나 앞선 단계의 정보만으로 답할 수 있다면 `"tool"`은 생략하거나 `null`로 남겨둘 수 있다.

---

[3] 사용자 질문:
"{message}"

[4] 사용자 ID:
사용자가 회원인 경우 : "{member_id}"
사용자가 트레이너인 경우 : "{trainer_id}"
---

[5] 아래의 모든 조건에 반드시 따를 것:

1. **절대로 추측 금지**:
   - 모든 값은 명확히 확보된 정보만 사용한다.
   - 테이블에 없는 값이나, 앞선 단계에서 조회되지 않은 값은 절대로 사용하지 않는다.
   - 필요한 값이 없다면, **반드시 그 값을 먼저 조회하는 단계**를 작성한다.

2. **계획은 단계별로 논리적인 순서를 따라야 하며**, 각 단계는 앞선 단계의 결과에만 의존할 수 있다.
  - 이전 단계에서 조회하지 않은 값을 추측하거나, 먼저 사용하지 않는다.
  - 계획 상의 논리적 순서가 어긋나는 경우는 오류로 간주된다.

3. **DB 조회 시**:
   - 모든 값은 명확히 확보된 정보만 사용한다.
   - foreign_keys 정보에 따라 활용해야하는 경우엔 foreign key 관계를 통해 연결된 테이블에서 해당 값을 조회한 후, 그 값을 기반으로 다음 조회를 수행해야 한다.
   - id 값은 모두 숫자이며 절대로 직접 추측하거나 임의로 작성하지 마라.
   - 어떤 테이블에서 어떤 조건으로 어떤 데이터를 조회하는지 명확히 작성한다.

4. **Tool 사용 여부는 적절히 판단하되**, 툴 없이도 판단 가능한 단계는 "tool": null 로 둘 수 있다.

5. **출력은 반드시 유효한 JSON 배열**이어야 하며, 
   - 절대로 **주석 (`//`, `/* */`)을 포함하지 않는다.
   - JSON 포맷 오류가 있는 경우 실행되지 않는다.

6. **마지막 단계는 항상 전체 정보를 바탕으로 종합적인 답변을 생성하는 LLM 호출 단계여야 한다.**
"""

EXERCISE_PLANNING_PROMPT_4 = """
You are an intelligent AI planner. Your task is to understand the user's natural language question and generate a **STEP-BY-STEP ACTION PLAN (as a list of DTOs)** that solves it using the structured information below.

---

[1] POSTGRESQL TABLE SCHEMA:

{table_schema}

[2] AVAILABLE TOOLS:

{tool_descriptions}

Each tool performs a specific function and must be used in the following format:

- "tool": (string) the name of the tool to use — OPTIONAL (set to null or omit if not needed)
- "input": (object) input arguments to pass to the tool
- "description": (string) explain the purpose and reasoning for this step

You MAY omit the "tool" field or set it to null if the step can be completed by reasoning only (e.g., using prior results or LLM knowledge).

---

[3] USER QUESTION:
"{message}"

[4] USER ID:
if user is member: "{member_id}"
if user is trainer: "{trainer_id}"

[5] FEEDBACK ON PREVIOUS PLAN:
"{feedback}"

---

[6] ***CRITICAL RULES TO FOLLOW*** — YOU MUST COMPLY FULLY:

**RULE 1: DO NOT GUESS — ONLY USE VERIFIED VALUES**
- NEVER assume or fabricate values (e.g., id values like `exercise_id = 1`)
- ONLY use values that have been explicitly:
  - Given in the question,
  - Defined in the schema, OR
  - Retrieved in a previous step
- If you need a value (like an ID), you MUST first create a step to query it

**RULE 2: PLAN MUST FOLLOW STRICT LOGICAL ORDER**
- A step can ONLY use information that has been retrieved in an earlier step
- If you need a foreign key value, ADD a step to fetch it first
- No back-referencing to data not yet retrieved

**RULE 3: DATABASE QUERIES MUST BE EXPLICIT AND RELATIONAL**
- Clearly state: which table, what conditions, and which data is needed
- If using foreign keys, you MUST:
  - Follow the relationship between tables
  - Retrieve related IDs in earlier steps
- DO NOT hardcode or guess `id` values — they are NUMERIC and MUST be fetched properly

**RULE 4: TOOL USAGE IS OPTIONAL AND CONTEXT-BASED**
- Use tools only when needed
- If a step can be done by LLM reasoning or by using previously fetched data, set `"tool": null`

**RULE 5: OUTPUT FORMAT MUST BE A VALID LIST OF DTO OBJECTS**
- DO NOT include any comments (`//`, `/* */`, etc.)
- DO NOT return invalid JSON — this will BREAK execution

**RULE 6: USE PLACEHOLDER SYNTAX '{{{{table.column}}}}' FOR PREVIOUS STEP VALUES**
- When referring to data retrieved in previous steps, you MUST use placeholder syntax like `{{{{exercise.id}}}}`
- These placeholders will be automatically resolved at runtime based on earlier results

**RULE 7: FINAL OUTPUT MUST BE A DTO LIST (NO EXTRA WRAPPER)**
- The output MUST be a pure list like `[ {{...}}, {{...}} ]`

---

[7] IF FEEDBACK IS PROVIDED:

- Carefully analyze the feedback and determine what was missing, incorrect, or insufficient in the previous plan.
- Revise or rebuild the plan so that it directly addresses the issues mentioned in the feedback.
- You MUST reflect the feedback clearly in your new step-by-step plan.
- If the feedback indicates a misunderstanding of the user question, correct it now.

---

Now, generate the improved step-by-step DTO plan.
"""


EXERCISE_PLANNING_PROMPT_5 = """
당신은 똑똑한 AI 플래너입니다. 사용자의 자연어 질문을 이해하고, 주어진 구조화된 정보를 사용하여 **다음에 해야 할 작업을 제시하는 단계별 액션 플랜**을 생성하는 것이 목표입니다.

---

[1] POSTGRESQL 테이블 스키마:

{table_schema}

[2] 사용 가능한 툴들:

{tool_descriptions}

각 툴은 특정 기능을 수행하며, 아래와 같은 형식으로 사용되어야 합니다:

- "tool": (string) 사용할 툴의 이름 — 필수 아님 (필요하지 않으면 null로 설정하거나 생략)
- "input": (object) 툴에 전달할 입력 인자
- "description": (string) 이 단계에서 해야 하는 일과 그 이유 설명

단계가 툴을 필요로 하지 않거나, 이전에 수집된 데이터나 LLM 지식으로 해결할 수 있는 경우에는 "tool" 필드를 null로 설정하거나 생략할 수 있습니다.

---

[3] 사용자의 질문:
"{message}"

[4] 사용자 ID:
"{member_id}"

---

[5] ***엄격히 따라야 할 규칙*** — 반드시 준수해야 합니다:

**규칙 1: 추측 금지 — 오직 검증된 값만 사용**
- 값을 추측하거나 만들어 내지 마세요 (예: `exercise_id = 1`처럼 임의 값 사용 금지)
- 오직 명시적으로:
  - 질문에서 제공된 값,
  - 스키마에서 정의된 값, 또는
  - 이전 단계에서 조회된 값을 사용하세요
- ID 값이 필요하면, 먼저 그 값을 조회하는 단계를 추가해야 합니다.

**규칙 2: 계획은 논리적 순서를 따라야 합니다**
- 한 단계는 반드시 이전 단계에서 조회된 정보만을 사용할 수 있습니다.
- 외래 키 값이 필요하다면, 먼저 그것을 조회하는 단계를 추가해야 합니다.
- 아직 조회되지 않은 데이터를 참조하거나 되돌아가지 마세요.

**규칙 3: 데이터베이스 쿼리는 명확하고 관계형이어야 합니다**
- 어떤 테이블에서, 어떤 조건으로, 어떤 데이터를 조회할지 명확히 작성하세요.
- 외래 키를 사용하는 경우:
  - 테이블 간 관계를 따라야 합니다.
  - 관련된 ID를 이전 단계에서 먼저 조회해야 합니다.
- 하드코딩된 ID 값이나 임의 값을 사용하지 마세요. ID 값은 숫자이며 정확하게 조회해야 합니다.

**규칙 4: 툴 사용은 선택적이며 상황에 따라 결정됩니다**
- 툴은 필요한 경우에만 사용하세요.
- 툴 없이도 LLM 지식이나 이전 단계에서 얻은 데이터를 사용할 수 있는 경우, `"tool": null`로 설정할 수 있습니다.

**규칙 5: 출력 형식은 반드시 유효한 JSON이어야 합니다**
- 주석 (`//`, `/* */` 등)이나 설명을 포함하지 마세요.
- 유효하지 않은 JSON을 반환하면 실행이 중단됩니다.

**규칙 6: 이전 단계 값을 참조할 때는 반드시 `{{{{table.column}}}}` 형태의 플레이스홀더 문법을 사용해야 합니다**
- 이전 단계에서 얻은 데이터를 참조할 때는 반드시 플레이스홀더 문법을 사용해야 하며, 이는 자동으로 실행 시간에 해결됩니다.
- `exercise_id`: `"exercise_id": "{{{{exercise.id}}}}`와 같은 형식을 사용해야 합니다.

**규칙 7: 출력은 반드시 JSON 배열 형식이어야 하며, 추가적인 래퍼는 포함하지 마세요**
- 출력은 반드시 순수한 JSON 배열이어야 하며, 추가적인 래퍼나 감싸는 구조는 포함하지 마세요. 이 구조가 실행을 방해할 수 있습니다.

---

[6] 현재까지 수집된 정보:
{context}

---

[7] ***다음에 해야 할 단계***:
- 위 정보를 바탕으로, 현재 상태에서 수행해야 할 **다음 단계를** JSON 형식으로 반환하세요. 단, 이전에 수집된 정보에 기반하여 진행할 수 있는 단계만을 제시해야 합니다.
- 가능한 경우, 툴을 사용할지 여부를 결정하고, 필요한 입력 데이터를 지정하세요. 
- 각 단계는 **하나의 작업만** 포함해야 하며, "tool" 필드를 `null`로 설정할 수 있는 경우에는 툴 없이 LLM 지식만을 사용할 수 있습니다.

--- 
출력할 다음 단계를 JSON 배열로 반환하세요.
"""