import os
import openai

def chat():
    openai.api_key = os.getenv("OPENAI_API_KEY")
    default_system_role = "You are a helpful assistant."
    custom_system_role = input("Define assistant bahavior or press 1 for the default setting: ")

    if custom_system_role == "1":
        system_role = default_system_role
    else:
        system_role = custom_system_role

    conversation = [{"role": "system", "content": system_role}]

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
