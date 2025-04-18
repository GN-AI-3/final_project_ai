from langchain_core.messages import HumanMessage
from .agents import create_teams_supervisor

if __name__ == "__main__":
    workflow = create_teams_supervisor()
    print("안녕하세요! 저는 AI 트레이너입니다. 무엇이든 물어보세요. (종료하려면 'exit' 또는 'quit'를 입력하세요)")
    
    while True:
        user_input = input("\n당신: ")
        
        if user_input.lower() in ['exit', 'quit']:
            print("대화를 종료합니다. 감사합니다!")
            break
            
        if user_input.strip():
            result = workflow.invoke({"messages": [HumanMessage(content=user_input)]})
            print("\nAI:", result["messages"][-1].content)