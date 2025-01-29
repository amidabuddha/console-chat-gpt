import subprocess
import time

import requests

from console_gpt.custom_stdout import custom_print


def is_ollama_running():
    """Check if Ollama is running by attempting to connect to http://localhost:11434."""
    try:
        response = requests.get("http://localhost:11434")
        return response.status_code == 200
    except requests.ConnectionError:
        return False


def start_ollama():
    """Start Ollama in the background using 'ollama serve'."""
    try:
        # Start Ollama in the background
        subprocess.Popen(["ollama", "serve"])

        # Wait for Ollama to be fully up and running
        while not is_ollama_running():
            time.sleep(1)  # Check every second
        custom_print("info", "Ollama started successfully.")
    except Exception as e:
        custom_print("error", f"Failed to start Ollama: {e}")


def list_ollama_models():
    """List all available Ollama models using 'ollama list' and return them as a list."""
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if result.returncode == 0:
            # Parse the output to extract model names
            lines = result.stdout.strip().split("\n")
            models = []
            for line in lines[1:]:  # Skip the header line
                columns = line.split()
                model_name = columns[0]  # The first column is the model name
                models.append(model_name)
            return models
        else:
            custom_print("error", f"Error listing models: {result.stderr}")
            return []
    except Exception as e:
        custom_print("error", f"Failed to list Ollama models: {e}")
        return []


def get_ollama():
    # Check if Ollama is running, start it if not, and return the list of available models.
    if not is_ollama_running():
        custom_print("info", "Ollama is not running. Starting it now...")
        start_ollama()

    # List all available models
    models = list_ollama_models()

    return models
