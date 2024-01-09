import openai

threads = ["thread_8UK3kdTZhiA4vhUthc33es84"]
client = openai.OpenAI(api_key="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")

for tread in threads:
    response = client.beta.threads.delete(tread)
    print(response)

