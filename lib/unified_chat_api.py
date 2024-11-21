import json                                                                    
import anthropic                                                               
import google.generativeai as genai                                            
import openai                                                                  
from mistralai import Mistral

# In case you need to use a custom model, please add it to the relevant list
anthropic_models = ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest", "claude-3-opus-latest"]
mistral_models = ["mistral-small-latest", "mistral-large-latest", ]
openai_models = ["gpt-3.5-turbo", "gpt-4o-mini", "gpt-4o", "o1-mini", "o1-preview"]
grok_models = ["grok-beta"]
gemini_models = ["gemini-1.5-flash", "gemini-1.5-pro"]

def set_defaults(
    api_key,                                                                   
    model_name,                                                                
    conversation,                                                              
    temperature,                                                                                                                                                                                                                                                                                                     
    cached=True,
):
    # Extract the system instructions from the conversation
    if model_name in anthropic_models or gemini_models:
        role = conversation[0]["content"] if conversation[0]["role"] == "system" else ""
    # Initiate API
    if model_name in mistral_models:
        client = Mistral(api_key=api_key)
    elif model_name in anthropic_models:
        client = anthropic.Anthropic(api_key=api_key)
        cached = False
    elif model_name in grok_models:
        client = openai.OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    elif model_name in gemini_models:
        genai.configure(api_key=api_key)
        generation_config = {
            "temperature": float(temperature),
        }
        client = genai.GenerativeModel(
            model_name=model_name, generation_config=generation_config, system_instruction=role, tools="code_execution"
        )
    else:
        client = openai.OpenAI(api_key=api_key)

    # Set defaults
    if model_name in anthropic_models or gemini_models:
        conversation = [message for message in conversation if message["role"] != "system"]

    return client, conversation, role, cached

def get_chat_completion(                                                       
    api_key,                                                                   
    model_name,                                                                
    conversation,                                                              
    temperature,                                                               
    model_max_tokens,                                                                  
    use_beta=False,                                                                                                             
    cached=True,                                                                                                                
):
    client, conversation, role, cached  = set_defaults(
        api_key,                                                                
        model_name,                                                                
        conversation,
        temperature,                                                                                                                                                             
        cached,
    )                                                                    
    try:                                                                       
        if model_name in mistral_models:                                                                  
            response = client.chat.complete(                                   
                model=model_name,                                              
                temperature=float(temperature) / 2,                            
                messages=conversation,                                         
            )                                                                  
            response = response.choices[0].message.content

        elif model_name in anthropic_models:                                              
            if use_beta:                                                       
                response = client.beta.prompt_caching.messages.create(         
                    model=model_name,                                          
                    max_tokens=model_max_tokens,                               
                    temperature=float(temperature) / 2,                        
                    system=[                                                   
                        {"type": "text", "text": role},                        
                        {"type": "text", "text": cached, "cache_control": {"type": "ephemeral"}},                                                        
                    ],                                                         
                    messages=conversation,                                     
                ).model_dump_json()                                            
            else:                                                              
                response = client.messages.create(                             
                    model=model_name,                                          
                    max_tokens=model_max_tokens,                               
                    temperature=float(temperature) / 2,                        
                    system=role,                                               
                    messages=conversation,                                     
                ).model_dump_json()                                            
            response = json.loads(response)                                    
            response_content = response["content"][0]["text"]                  
                                                                            
        elif model_name in gemini_models:                                                                                                  
            output_list = []                                                   
            for item in conversation:                                          
                new_role = "model" if item["role"] == "assistant" else item["role"]                                                                   
                new_item = {"role": new_role, "parts": [item["content"]]}      
                output_list.append(new_item)                                   
            chat_session = client.start_chat(history=output_list[:-1])         
            response = chat_session.send_message(conversation[-1]["content"])  
            response_content = response.text                                   
                                                                            
        elif model_name in grok_models:                                    
            response = client.chat.completions.create(                         
                model=model_name,                                              
                temperature=float(temperature),                                
                messages=conversation,                                         
            )                                                                  
            response_content = response.choices[0].message.content             
                                                                            
        elif model_name in openai_models:                       
            response = client.chat.completions.create(                         
                model=model_name,                                              
                temperature=float(temperature),                                
                messages=conversation,                                         
            )                                                                  
            response_content = response.choices[0].message.content 

        else:
            return f'Model {model_name} is curently not supported'            
                                                                            
        return response_content                                                
                                                                            
    except (openai.APIConnectionError, anthropic.APIConnectionError) as e:     
        raise ConnectionError(f"The server could not be reached: {e}") from e  
    except (openai.RateLimitError, anthropic.RateLimitError) as e:             
        raise RuntimeError(f"Rate limit exceeded: {e}") from e                 
    except (openai.APIStatusError, anthropic.APIStatusError, anthropic.BadRequestError) as e:                                               
        raise RuntimeError(f"API status error: {e.status_code} - {e.message}") from e
    except Exception as e:                                                     
        raise Exception(f"An unexpected error occurred: {e}") from e