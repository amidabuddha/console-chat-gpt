import time

import openai
import requests

from console_gpt.custom_stdout import custom_print
from console_gpt.general_utils import capitalize
from console_gpt.menus.assistant_menu import _delete_file, _upload_files
from console_gpt.menus.command_handler import command_handler
from console_gpt.prompts.assistant_prompt import assistance_reply
from console_gpt.prompts.user_prompt import assistant_user_prompt

TIMEOUT = 300


def assistant(console, data) -> None:
    client = openai.OpenAI(api_key=data.model["api_key"])
    # Step 3: Add a Message to a Thread
    message_files = []
    while True:
        user_input = assistant_user_prompt()
        # Command Handler
        if not user_input or user_input.lower() in ("exit", "quit", "bye"):  # Used to catch SIGINT
            custom_print("exit", "Goodbye, see you soon!", 130)
        elif user_input.lower() == "save":
            custom_print("info", "Assistant conversations are not saved locally.")
            continue
        elif user_input.lower() in ["flush", "new"]:
            break
        elif user_input.lower() == "file":
            message_files = _upload_files(data.model)
            if message_files:
                custom_print("info", "The upoaded infromation will be added to your next message.")
            continue
        # TODO implement dedicated command handler for assistants
        handled_user_input = command_handler(data.model["model_title"], data.model["model_name"], user_input, "")
        match handled_user_input:
            case "continue" | None:
                continue
            case "break":
                break
            case _:
                user_input = handled_user_input
        try:
            message = client.beta.threads.messages.create(
                thread_id=data.thread_id, role="user", content=user_input, file_ids=message_files
            )
        except openai.NotFoundError as e:
            custom_print(
                "error",
                "The thread specified in the local assistant file does not exist. Please edit the assistant and try again.",
            )
            break
        conversation = message.id
        # Start the loading bar until API response is returned
        with console.status("[bold green]Generating a response...", spinner="aesthetic"):
            # Step 4: Run the Assistant
            run_thread(client, data.assistant_id, data.thread_id)
        # Step 6: Display the Assistant's Response
        conversation, new_replies = update_conversation(data.model["api_key"], conversation, data.thread_id)
        for reply in new_replies:
            assistance_reply(reply["content"], capitalize(data.assistant_name))
        for file in message_files:
            _delete_file(data.model, file)
        message_files = []


def run_thread(client, assistant_id, thread_id):
    try:
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
        )
        # Step 5: Check the Run status
        start_time = time.time()
        while run.status != "completed":
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            match run.status:
                case "expired":
                    custom_print("error", "Maximum wait time exceeded, please try again")
                    break
                case "cancelled":
                    custom_print("error", "Request interrupted, please submit a new one")
                    break
                case "failed":
                    custom_print("error", run.last_error)
                    break
            time.sleep(2)
            current_time = time.time()
            if (current_time - start_time) > TIMEOUT:
                custom_print("error", "Maximum wait time exceeded")
                run = client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run.id)
                break  # Exit the loop if more than 5 minutes have passed
            continue
    except KeyboardInterrupt:
        run = client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run.id)
        # Notifying the user about the interrupt but continues normally.
        custom_print("info", "Interrupted the request. Continue normally.")
    except openai.BadRequestError as e:
        print(e)


def update_conversation(apikey, conversation, thread_id):
    messages = requests.get(
        "https://api.openai.com/v1/threads/{thread_id}/messages".format(thread_id=thread_id),
        headers={"OpenAI-Beta": "assistants=v1", "Authorization": f"Bearer {apikey}"},
    ).json()
    # Parse the JSON object to extract the required information
    messages_list = [
        {"id": message["id"], "content": content["text"]["value"]}
        for message in messages["data"]
        for content in message["content"]
        if content["type"] == "text"
    ]
    messages_list.reverse()
    # Find the index of the dictionary with the specified id
    index = next((i for i, message in enumerate(messages_list) if message["id"] == conversation), None)
    # Slice the list from the next index to the end if the index was found
    new_messages = messages_list[index + 1 :] if index is not None else []
    # Get the 'id' of the last item in the filtered list if it's not empty
    conversation = messages_list[-1]["id"] if new_messages else None
    # Reverse the list
    return (conversation, new_messages)
