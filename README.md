<div align="center">

# consoleChatGPT

The ultimate command line interface for chatting with the ChatGPT! Save time and effort with this simple yet effective
tool.

<h3>

[Homepage](https://github.com/amidabuddha/consoleChatGPT)  | [Examples](/examples)

</h3>


</div>

---

**DISCLAIMER:**
The intention and implementation of this code are entirely unconnected and unrelated to OpenAI. There is no affiliation or relationship with OpenAI in any form.

## Installation and Usage:

1. Clone the repository:
   ```
   git clone https://github.com/amidabuddha/consoleChatGPT.git
   ```
2. Go inside the folder:
   ```shell
   cd consoleChatGPT
   ```
    - Note that if the alias is missing on `Windows` you should use:
      ``` 
      Set-Location "consoleChatGPT"
      ```
3. Install the necessary dependencies:
   ```shell
    python3 -m pip install -r requirements.txt
    ```
4. Export your API key, which you can grab from [HERE](https://platform.openai.com/account/api-keys):

    - On Unix/Linux/macOS:
      ```
      export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
      ```
    - On Windows (Command Prompt):
      ```
      set OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
      ```
    - On Windows (PowerShell):
      ```
      $env:OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
      ```

5. Run the executable:
    ```shell
    python3 chat.py 
    ```
6. Enjoy

## How to submit long text with line breaks
With source code or any other text with multiline content as input use the `whitespace_remover.py` tool to preformat the request and them paste it into the CLI prompt.
