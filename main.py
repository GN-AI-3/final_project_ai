from test import graph
from dotenv import load_dotenv

def main():
    # 환경 변수 로드
    load_dotenv()
    
    # NOTE: we're specifying `user_id` to save memories for a given user
    config = {"configurable": {"user_id": "1", "thread_id": "1"}}

    while True:
        user_input = input("사용자 입력: ")  # 사용자로부터 입력 받기
        if user_input.lower() in ["exit", "quit"]:  # 종료 조건
            print("대화를 종료합니다.")
            break

        for chunk in graph.stream({"messages": [("user", user_input)]}, config=config):
            for node, updates in chunk.items():
                print(f"# {node}")
                if "messages" in updates:
                    updates["messages"][-1].pretty_print()
                else:
                    print(updates)

                print("\n")

if __name__ == "__main__":
    main()
