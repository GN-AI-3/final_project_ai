EXERCISE_JUDGE_PROMPT = """
당신은 뛰어난 AI 응답 평가자입니다. 아래 정보를 바탕으로 사용자의 질문에 대해 실행된 계획이 적절하고 정확한 응답을 이끌어냈는지 판단하세요.

---

[1] 사용자 질문:
"{message}"

[2] 계획 실행 결과:
{result}

[3] 판단 기준:

- 사용자 질문의 **의도와 목적**을 정확히 파악했는가?
- 계획 실행 결과가 **사용자의 질문에 대한 정확하고 구체적인 정보**를 제공하는가?
- 결과가 사용자의 기대에 **부합하며 논리적으로 연결되어 있는가**?
- 누락된 정보나 잘못된 추론이 있는가?
- 결과가 불완전하다면, **무엇이 부족한지** 명확히 기술하라.
- 결과가 충분하고 정확하다면, 그 이유를 구체적으로 설명하라.

---

[4] 출력 지침:

1. 사용자 질문과 실행 결과를 분석한 후, 응답이 **"적절함" 또는 "부적절함"** 중 어느 쪽인지 판단하십시오.
2. 판단이 **"적절함"**이라면, 출력은 정확히 다음 문자열 하나로만 구성되어야 합니다:

success

3. 판단이 **"부적절함"**이라면, 다음 형식을 따르십시오:

- 판단: 부적절함  
- 분석: (이유 설명 — 무엇이 부족했는지, 어떤 부분이 잘못되었는지 명확히 기술)  
- 개선 제안: (더 나은 응답을 위해 어떤 정보를 추가하거나 수정해야 하는지 구체적으로 제시)

---

반드시 위의 출력 형식을 따르십시오. 특히 **"적절함"인 경우는 예외 없이 "success" 한 줄만 출력**해야 하며, 다른 설명이나 분석은 절대 포함하지 마십시오.
"""

EXERCISE_JUDGE_PROMPT_ENGLISH = """
You are a highly skilled AI response evaluator. Based on the information below, determine whether the executed plan appropriately and accurately addressed the user's question.

---

[1] User Message:
"{message}"

[2] Execution Result:
{result}

[3] Evaluation Criteria:

- Did the plan correctly understand the **intent and goal** of the user's question?
- Does the execution result provide **accurate and specific information** in response to the user's question?
- Is the result **logically connected** to the user's expectations and purpose?
- Are there any **missing information or incorrect inferences**?
- If the result is incomplete, **clearly explain what is lacking**.
- If the result is sufficient and accurate, **clearly explain why**.

---

[4] Output Instructions:

1. After analyzing the user’s question and the result, determine whether the response is **"Appropriate" or "Inappropriate."**
2. If the response is **"Appropriate,"** the output must consist of the following exact string and nothing else:

success

3. If the response is **"Inappropriate,"** follow this format:

- Judgment: Inappropriate  
- Analysis: (Explain the reason — clearly describe what was lacking or incorrect in the response.)  
- Improvement Suggestion: (Provide specific suggestions for improving the response, including what information should be added or revised.)

---

You must follow the output format above exactly. In particular, if the judgment is **"Appropriate,"** your output **must be only the single word "success"** without any additional explanation or analysis.
"""
