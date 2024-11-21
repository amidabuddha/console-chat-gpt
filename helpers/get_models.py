# Run this file from within the /helpers directory
# make sure the config.toml.cample exists

import toml
import json  

# Sample TOML content                                                          
toml_content = "../config.toml.sample"                                                                            
                                                                            
# Parse the TOML data                                                          
data = toml.load(toml_content)
                                                       
# Initialize the structures                                                    
MODELS_LIST = {                                                                
    "anthropic_models": [],                                                    
    "mistral_models": [],                                                      
    "openai_models": [],                                                       
    "grok_models": [],                                                         
    "gemini_models": [],                                                       
}                                                                              
                                                                            
MODELS_MAX_TOKEN = {}

# Extract the models information                                               
models_data = data['chat']['models']  
                                                                            
# Populate the structures                                                      
for model, model_data in models_data.items():                                     
    model_name = model_data['model_name']                                      
    max_tokens = model_data['model_max_tokens']                                
                                                                            
    # Fill MODELS_MAX_TOKEN                                                    
    MODELS_MAX_TOKEN[model_name] = str(max_tokens)                             
                                                                            
    # Fill MODELS_LIST                                                         
    if "anthropic" in model:                                               
        MODELS_LIST["anthropic_models"].append(model_name)                     
    elif "mistral" in model:                                               
        MODELS_LIST["mistral_models"].append(model_name)                       
    elif "gpt" in model or "o1" in model:                          
        MODELS_LIST["openai_models"].append(model_name)                        
    elif "grok" in model:                                                  
        MODELS_LIST["grok_models"].append(model_name)                          
    elif "gemini" in model:                                                
        MODELS_LIST["gemini_models"].append(model_name)                        
                                                                            
# Print the results                                                            
print("MODELS_LIST = ", json.dumps(MODELS_LIST, indent=4))                                                                                
print("MODELS_MAX_TOKEN = ", json.dumps(MODELS_MAX_TOKEN, indent=4))                                                