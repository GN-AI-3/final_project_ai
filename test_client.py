import requests
import json

API_URL = "http://localhost:5000/chat"

def test_emotion_analysis():
    # Simulating a conversation with emotional context
    conversation = [
        {"message": "I'm feeling really excited about my fitness journey!", "response": ""},
        {"message": "But I missed my workout yesterday and now I'm feeling guilty.", "response": ""},
        {"message": "I'm worried I won't be able to stick to my diet plan.", "response": ""},
        {"message": "Despite the challenges, I'm determined to keep going!", "response": ""}
    ]
    
    chat_history = []
    
    for i, item in enumerate(conversation):
        print(f"\n--- Message {i+1}: {item['message']} ---")
        
        # Prepare the request with the current message and chat history
        data = {
            "message": item["message"],
            "email": "test@example.com"
        }
        
        if chat_history:
            data["chat_history"] = chat_history
        
        # Send the request to the API
        response = requests.post(API_URL, json=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {result['response']}")
            print(f"Emotion: {result.get('emotion_type', 'Not available')} (Score: {result.get('emotion_score', 'N/A')})")
            print(f"Context info: {result.get('context_info', 'Not available')}")
            print(f"Categories: {result.get('categories', [])}")
            
            # Update chat history for the next request
            chat_history.append({
                "message": item["message"],
                "response": result["response"]
            })
        else:
            print(f"Error: {response.status_code} - {response.text}")
            break

if __name__ == "__main__":
    print("Testing improved emotion analysis functionality...")
    test_emotion_analysis() 