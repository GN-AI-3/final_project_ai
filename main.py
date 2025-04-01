from chatbot import Chatbot

def main():
    chatbot = Chatbot()
    print("안녕하세요! 헬스장 예약 시스템입니다.")
    print("예약이나 일정 조회를 원하시면 말씀해주세요.")
    print("종료하려면 '종료'를 입력하세요.")
    
    while True:
        user_name = input("\n이름을 입력하세요: ")
        if user_name.lower() == '종료':
            break
        
        message = input("메시지를 입력하세요: ")
        if message.lower() == '종료':
            break
        
        response = chatbot.process_message(message, user_name)
        print("\n응답:", response)

if __name__ == "__main__":
    main() 