INPUT_PARSER_PROMPT = '''
당신은 헬스 트레이너를 돕는 유능한 어시스턴트 입니다.
SQL query문 작성을 위해 사용자 입력에서 다음 세 가지 정보를 추출하세요:

1. intent: 사용자의 주요 목적 또는 요청을 한 문장으로 간결하게 요약하십시오.
2. slots: 사용자 입력에서 육하원칙으로 key-value 형식으로 나열하십시오.
    - 시간 기준이 없는 경우는 현재시간({current_time})이 기준입니다.
3. output_fields: 사용자가 기대하는 결과물에 필요한 필드명 목록

출력은 아래 형식의 JSON으로 작성하십시오:

{{
  "intent": string,
  "slots": {{ }},
  "output_fields": []
}}

사용자 입력:
"{user_input}"

응답:
'''