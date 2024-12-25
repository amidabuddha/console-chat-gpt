On MacOS run the following bash script in the Terminal to collect the entire app source code in one text file:

```bash
for file in $(find * -type f | grep -Ev ".idea|.json|.txt|config.toml|pycache|chats|test|\.log|assistants|app-data|venv|example"); do
    echo  -e "\`\`\`\n\n>>> $file:\n\`\`\`" && cat $file;
done > source_code_for_llm.txt

for file in config.toml.sample mcp_config.json.sample requirements.txt; do
    echo  -e "\n\`\`\`\n\n>>> $file:\n\`\`\`" && cat $file;
done >> source_code_for_llm.txt

echo "\n\`\`\`" >> source_code_for_llm.txt

sed -i '' '1,2d' source_code_for_llm.txt
```
