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
The script should work fine in Linux and macOS terminals. There might be some libraries that are currenlty not supported on Windows, the recommneded use is inside [WSL](https://learn.microsoft.com/en-us/windows/wsl/)

1. Clone the repository:

   ```shell
   git clone https://github.com/amidabuddha/console-chat-gpt.git
   ```

2. Go inside the folder:

   ```shell
   cd console-chat-gpt
   ```

3. Install the necessary dependencies:

   ```shell
   python3 -m pip install -r requirements.txt
   ```

4. Get your API key from [HERE](https://platform.openai.com/account/api-keys)

5. Copy `config.toml.sample` into `config.toml`, replace the text "YOUR_OPENAI_API_KEY" with your API key and save the new config file. Feel free to change any of the other defaults as per your needs.

6. Run the executable:

   ```shell
   python3 chat.py
   ```

7. Enjoy

## How to submit long text with line breaks

With source code or any other text with multiline content as input there are the following helper commands available to submit it:

`format` - this command will provide prompt to paste the content into the terminal

`file` - this command may be used if the desired content is too long to be submitted via paste
