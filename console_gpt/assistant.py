import time

import openai
import requests

from console_gpt.custom_stdout import custom_print
from console_gpt.menus.command_handler import command_handler
from console_gpt.prompts.assistant_prompt import assistance_reply
from console_gpt.prompts.user_prompt import assistant_user_prompt


def assistant(console, data) -> None:            
    # Step 1: Create an Assistant
    client = openai.OpenAI(api_key=data.model["api_key"])
    my_tools = [] if data.tools == None else data.tools
    # TODO upload files for retrieval on assistant level: https://platform.openai.com/docs/assistants/tools/uploading-files-for-retrieval
    assistant = client.beta.assistants.create(
        name=data.role_title,
        instructions=data.instructions,
        tools=my_tools,
        model=data.model["model_name"]
    )
    # Step 2: Create a Thread
    thread = client.beta.threads.create()
    # Step 3: Add a Message to a Thread
    conversation = []
    # 
    while True:
        user_input = assistant_user_prompt()
        if not user_input or user_input == "exit":  # Used to catch SIGINT
            # TODO Ask to save assistant
            client.beta.assistants.delete(assistant.id)
            # TODO Delete the thread only if keeping the assistant
            ## Ask to save thread
            command_handler(data.model["model_title"], data.model["model_name"], "exit", conversation)
        # Command Handler
        handled_user_input = command_handler(data.model["model_title"], data.model["model_name"], user_input, conversation)
        match handled_user_input:
            case "continue" | None:
                continue
            case "break":
                break
            case _:
                user_input = handled_user_input
        conversation.append({"role": "user", "content": user_input})
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input
        )
        # Start the loading bar until API response is returned
        with console.status("[bold green]Generating a response...", spinner="aesthetic"):
            # Step 4: Run the Assistant
            run_thread(client, assistant.id, thread.id)
        # Step 6: Display the Assistant's Response
        conversation, new_replies = update_conversation(data.model["api_key"], conversation, thread.id)
        for reply in new_replies:
            assistance_reply(reply["content"])

def run_thread(client, assistant_id, thread_id):
    try:
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
            )
        # Step 5: Check the Run status
        start_time = time.time() 
        while run.status !="completed":
            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
                )
            match run.status:
                case "expired":
                    custom_print("error","Maximum wait time exceeded, please try again") 
                    break  
                case "cancelled":
                    custom_print("error","Request interrupted, please submit a new one")   
                    break 
                case "failed":
                    custom_print("error", run.last_error)
                    break
            time.sleep(2)
            current_time = time.time()                                                 
            if (current_time - start_time) > 60:                                       
                custom_print("error","Maximum wait time exceeded")                                    
                break  # Exit the loop if more than 60 seconds have passed 
            continue
    except KeyboardInterrupt:
        run = client.beta.threads.runs.cancel(
            thread_id=thread_id,
            run_id=run.id
            )
        # Notifying the user about the interrupt but continues normally.
        custom_print("info", "Interrupted the request. Continue normally.")

def update_conversation(apikey, conversation, thread_id):
    messages = requests.get("https://api.openai.com/v1/threads/{thread_id}/messages".format(thread_id=thread_id), headers={"OpenAI-Beta": "assistants=v1", "Authorization": f"Bearer {apikey}"}).json()
    # Parse the JSON object to extract the required information   
    messages_list = [                                                                
        {'role': message['role'], 'content': content['text']['value']}             
        for message in messages['data']                                            
        for content in message['content']                                          
        if content['type'] == 'text'                                               
    ]
    reverse_list = messages_list.reverse()                                                             
    new_messages = messages_list[len(conversation):]                                                                               
    # Reverse the list                                                                  
    return (messages_list, new_messages)                                  
