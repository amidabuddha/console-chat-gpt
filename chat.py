import os
import openai

def chat():
    openai.api_key = os.getenv("OPENAI_API_KEY")
    conversation = [{"role": "system", "content": "You are a helpful assistant."}]

    while True:
        user_prompt = input("User: ")
        if user_prompt.lower() not in ["exit", "quit", "bye"]:
            user_message = {"role": "user", "content": user_prompt}
            conversation.append(user_message)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo", messages=conversation
            )
            assistant_message = response.choices[0].message
            assistant_response = {
                "role": "assistant",
                "content": assistant_message["content"],
            }
            conversation.append(assistant_response)
            print("\nAssistant: " + assistant_message["content"] + "\n\n")
        else:
            break

chat()
