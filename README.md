<div align="center">

# console-chat-gpt

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
   git clone https://github.com/amidabuddha/console-chat-gpt.git
   ```

2. Go inside the folder:

   ```shell
   cd console-chat-gpt
   ```

   - Note that if the alias is missing on Windows you should use:

   ```shell
   Set-Location "console-chat-gpt"
   ```

3. Install the necessary dependencies:

   ```shell
   python3 -m pip install -r requirements.txt
   ```
      - On Windows you may have to use:

   ```shell
   python.exe -m pip install -r requirements.txt
   ```

4. Get your API key from [HERE](https://platform.openai.com/account/api-keys)

5. Copy `config.toml.sample` into `config.toml`, replace the text "YOUR_OPENAI_API_KEY" with your API key and save the new config file. Feel free to change any of the other defaults as per your needs.

6. Run the executable:

   ```shell
   python3 chat.py
   ```

7. Enjoy

## How to submit long text with line breaks

With source code or any other text with multiline content as input use the `prompt_formatter.py` tool to preformat the request and then pass it into the CLI user prompt.

1. Store the content in a source file.
2. Pass the source file name as an argument to the tool executable. 

Example:
   ```shell
   python3 prompt_formatter.py chat.py
   ```
3. The result will be a target file with appended "_modified.txt" to the original file name.

Example: `chat_modified.txt`

4. Add additional modification to the produced target file if needed.
5. Start the chat executable as described above and enter `file` as an user prompt.
6. In the next user prompt enter only the target file name that contains the full prompt.
