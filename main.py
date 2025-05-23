import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from supervisor import Supervisor
import warnings
from langchain._api.deprecation import LangChainDeprecationWarning

# LangChain 경고 무시 설정
warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)

async def main():
    # 환경 변수 로드
    load_dotenv()
    
    # Supervisor 초기화
    model = ChatOpenAI(model="gpt-3.5-turbo")

    # Supervisor 초기화 (model 객체 전달)
    supervisor = Supervisor(model=model)
    
    print("안녕하세요! 운동, 식단, 일정, 일반적인 대화에 대해 도움을 드릴 수 있습니다.")
    print("종료하려면 'quit' 또는 'exit'를 입력하세요.")
    
    while True:
        user_input = input("\n사용자: ").strip()
        
        if user_input.lower() in ['quit', 'exit']:
            print("대화를 종료합니다. 좋은 하루 되세요!")
            break
            
        if not user_input:
            continue
            
        try:
            response = await supervisor.process(user_input)
            print(f"\n{response['type'].upper()} 전문가: {response['response']}")
        except Exception as e:
            print(f"\n오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())