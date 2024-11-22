import sys

from lib.models import MODELS_LIST
from lib.unified_chat_api import get_chat_completion, set_api_key


def validate_inputs(api_key: str, model_name: str, temperature: str) -> None:
    if not api_key:
        raise ValueError("API key cannot be empty")
    if not any(model_name in models_list for models_list in MODELS_LIST.values()):
        raise ValueError(f"Unsupported model: {model_name}")
    try:
        if not 0 <= float(temperature) <= 2:
            raise ValueError("Temperature must be between 0 and 2")
    except ValueError:
        raise ValueError("Temperature must be a numeric value between 0 and 2")


def main():
    # Prompt the user for necessary inputs
    api_key = input("Enter your API key: ").strip()
    model_name = input("Enter the model name (e.g., 'gpt-4o-mini'): ").strip()
    temperature = input("Enter the temperature (e.g., 0.7) or leave blank for default (1): ").strip()
    if not temperature:
        temperature = "1"

    try:
        validate_inputs(api_key, model_name, temperature)
    except Exception as e:
        print(e)
        print("Please try again with correct values!")
        sys.exit()

    # Set the API key after validation
    set_api_key(api_key)

    # Set the system role or instructions if needed
    role = input("Enter system instructions or leave blank for default:").strip()
    if not role:
        role = "You are a helpful assistant."
    # Initialize the conversation with the system role if provided
    conversation = []
    conversation.append({"role": "system", "content": role})

    while True:
        # Prompt the user for a message
        user_message = input("\nYou: ").strip()
        if not user_message:
            continue
        if user_message.lower() in {"exit", "quit"}:
            print("Exiting the chat.")
            sys.exit()

        # Add the user's message to the conversation
        conversation.append({"role": "user", "content": user_message})

        try:
            # Call the get_chat_completion function
            assistant_response = get_chat_completion(
                model_name=model_name,
                messages=conversation,
                temperature=float(temperature),
            )

            # Add the assistant's response to the conversation
            conversation.append({"role": "assistant", "content": assistant_response})

            # Display the assistant's response
            print(f"\nAssistant: {assistant_response}")

        except Exception as e:
            print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
