import json
import get_models

models_list, models_max_token = get_models()
print("MODELS_LIST = ", json.dumps(models_list, indent=4))
print("MODELS_MAX_TOKEN = ", json.dumps(models_max_token, indent=4))
