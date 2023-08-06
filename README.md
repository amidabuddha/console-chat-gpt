<div align="center">

# consoleChatGPT

The ultimate command line interface for chatting with the ChatGPT! Save time and effort with this simple yet effective tool.

<h3>

[Homepage](https://github.com/amidabuddha/consoleChatGPT) | [Examples](/examples)

</h3>

</div>

- [Installation and Usage](#installation-and-usage)
- [How to submit long text with line breaks](#how-to-submit-long-text-with-line-breaks)
  
---

**DISCLAIMER:**

The intention and implementation of this code are entirely unconnected and unrelated to OpenAI. There is no affiliation or relationship with OpenAI in any form.

## Installation and Usage:

1. Clone the repository:

   ```shell
   git clone https://github.com/amidabuddha/consoleChatGPT.git
   ```

2. Go inside the folder:

   ```shell
   cd consoleChatGPT
   ```

   - Note that if the alias is missing on Windows you should use:

   ```shell
   Set-Location "consoleChatGPT"
   ```

3. Install the necessary dependencies:

   ```shell
   python3 -m pip install -r requirements.txt
   ```

4. Export your API key, which you can grab from [HERE](https://platform.openai.com/account/api-keys):

   - On Unix/Linux/macOS:

   ```shell
   export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
   ```

   - On Windows (Command Prompt):

   ```shell
   set OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
   ```

   - On Windows (PowerShell):

   ```shell
   $env:OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
   ```

5. Run the executable:

   ```shell
   python3 chat.py
   ```

6. Enjoy

## How to submit long text with line breaks

With source code or any other text with multiline content as input use the `prompt_formatter.py` tool to preformat the request and then pass it into the CLI user prompt.

1. Store the content in a source file
2. Pass the source file name as an argument to the tool executable. 

Example:
   ```shell
   python3 prompt_formatter.py chat.py
   ```
3. The result will be a target file with appended "_modified.txt" to the original file name.

Example: `chat_modified.txt`

4. Add additional modification to the produced target file if needed
5. Start the chat executable as described above and enter `file` as an user prompt
6. In the next user prompt enter only the filename that contains the full prompt