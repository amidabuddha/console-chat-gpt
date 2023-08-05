import configparser
import openai

def get_api_key():
    config = configparser.ConfigParser()
    config.read('key.ini')
    return config['openai']['api_key']

def chat():
    openai.api_key = get_api_key()
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
            print("Assistant: " + assistant_message["content"])
        else:
            break

chat()
