import json
import get_models

models_list, models_max_token = get_models()
print("export const MODELS_LIST = ", json.dumps(models_list, indent=4))
print("export const MODELS_MAX_TOKEN: Record<string, number> = ", json.dumps(models_max_token, indent=4))
