<div align="center">

<h1>

console-chat-gpt

</h1>

The ultimate command line interface for chatting with the ChatGPT! Save time and effort with this simple yet effective
tool.

<h3>

[Homepage](https://github.com/amidabuddha/consoleChatGPT) | [Examples](/examples)

</h3>

 <h4 align="center">
  <a href="https://github.com/amidabuddha/consoleChatGPT/blob/main/LICENSE.md">
  <img src="https://img.shields.io/github/license/amidabuddha/consoleChatGPT" alt="Released under the Apache license." />
  </a>
  <img src="https://img.shields.io/badge/Python-3.10+-blue" alt="Working on Python 3.10+" />
  <img src="https://img.shields.io/github/stars/amidabuddha/consoleChatGPT"/>
  <img src="http://hits.dwyl.com/amidabuddha/consoleChatGPT.svg"/>
  <img src="https://img.shields.io/github/issues/amidabuddha/consoleChatGPT"/>
  <img src="https://img.shields.io/github/forks/amidabuddha/consoleChatGPT"/>
  <img src="https://img.shields.io/badge/platform-Linux%20%7C%20macOS-blue"/>
</h4>

</div>

---
### Table of content
- [Installation and Usage](#installation-and-usage)
- [How to submit long text with line breaks](#how-to-submit-long-text-with-line-breaks)

---

<font color="pink">**DISCLAIMER:**</font>

The intention and implementation of this code are entirely unconnected and unrelated to OpenAI. There is no affiliation
or relationship with OpenAI in any form.

---
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
