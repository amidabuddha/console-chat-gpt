# consoleChatGPT

Keep your API key outside of the Python source code for security reasons!

We can use environment variables to store sensitive information like the API key. 

Here are examples how to set the environment variable on different operating systems:

   - On Unix/Linux/macOS:
     ```
     export API_KEY="OPENAI_API_KEY"
     ```
   - On Windows (Command Prompt):
     ```
     set API_KEY="OPENAI_API_KEY"
     ```
   - On Windows (PowerShell):
     ```
     $env:API_KEY="OPENAI_API_KEY"
     ```
