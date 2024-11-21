import sys

from lib.unified_chat_api import get_chat_completion


def main():
    print("Welcome to the Unified Chat API Tester!")

    # Prompt the user for necessary inputs
    api_key = input("Enter your API key: ").strip()
    model_name = input("Enter the model name (e.g., 'gpt-3.5-turbo'): ").strip()
    temperature = input("Enter the temperature (e.g., 0.7) or leave blank for default (1): ").strip()
    if not temperature:
        temperature = "1"
    model_max_tokens = input("Enter the maximum tokens (e.g., 512) or leave blank for default (4096): ").strip()
    if not model_max_tokens:
        model_max_tokens = "4096"
    # Set the system role or instructions if needed
    role = input("Enter system instructions or leave blank for default:").strip()
    if not role:
        role = "You are a helpful assistant."
    # Initialize the conversation with the system role if provided
    conversation = []
    if role:
        conversation.append({"role": "system", "content": role})

    while True:
        # Prompt the user for a message
        user_message = input("\nYou: ").strip()
        if user_message.lower() in {"exit", "quit"}:
            print("Exiting the chat.")
            sys.exit()

        # Add the user's message to the conversation
        conversation.append({"role": "user", "content": user_message})

        try:
            # Call the get_chat_completion function
            assistant_response = get_chat_completion(
                api_key=api_key,
                model_name=model_name,
                conversation=conversation,
                temperature=float(temperature),
                model_max_tokens=int(model_max_tokens),
                use_beta=False,  # Set to True if testing beta features
                cached=True,  # Adjust as needed
            )

            # Add the assistant's response to the conversation
            conversation.append({"role": "assistant", "content": assistant_response})

            # Display the assistant's response
            print(f"\nAssistant: {assistant_response}")

        except Exception as e:
            print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
