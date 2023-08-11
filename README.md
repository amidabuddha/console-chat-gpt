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
- [Examples and preview](#examples-and-preview)
- [Features](#features)
- [Installation and Usage](#installation-and-usage)
---

<font color="pink">**DISCLAIMER:**</font>

The intention and implementation of this code are entirely unconnected and unrelated to OpenAI. There is no affiliation
or relationship with OpenAI in any form.

---

# Features:

- Chat saving
  - Upon accidentally hitting ctrl+c (SIGINT).
  - Upon accidentally hitting ctrl+d (EOF).
  - Upon request via the `Save` command.
  - Custom naming of chats.
- Reading a prompt or content from a file via the `file` command.
- Pasting a multiline content inside the chat via the `format` command.
- Code formatting and coloring. 
- Adjustable colors.
- Costs calculator via the `cost` command.
- **A nice team that is active in adding features and fixing bugs.**

---

## Examples and preview
1. Upon executing the script, the first thing you'll be prompted is to continue an old chat:
    <img src="examples/start_chat.png" alt="init" width=auto height=130 />
    > You can use the arrow keys to navigate, or you can use your keyboard. The signs/numbers inside the "[]" (e.g. [x]) are the actual keybinds to access the displayed function
2. Afterward, you will have the ability to select how the AI should behave:
    <img src="examples/roles.png" alt="add" width=auto height=200 />
    > Those are roles set inside your config.toml. You can also add/remove or adjust.
3. The last prompt you'll see is regarding the so-called temperature (randomness):
    <img src="examples/temperature.png" alt="key" width=auto height=auto />
4. The script also contains a help menu with built-in commands which you might find helpful:
    <img src="examples/built-in_commands.png" alt="preview" width=auto height=180 />
5. The script also supports language formatting and coloring:</br>
    <img src="examples/example_python.png" alt="Removal" width=auto height=auto />


---
## Installation and Usage:
The script should work fine in Linux and macOS terminals. There might be some libraries that are currently not supported on Windows, the recommended use is inside WSL
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

7. Use the `help` command within the chat to check the available options.

8. Enjoy
