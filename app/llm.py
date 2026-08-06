from openai import OpenAI
import os
from dotenv import load_dotenv


load_dotenv()


client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

def chat(prompt):
    response=client.chat.completions.create(
        model=os.getenv("MODEL_NAME"),
        messages=[
            {
                "role":"user",
                "content":prompt
            }
        ]
    )
    return response.choices[0].message.content
def chat_with_tools(messages, tools):

    try:

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools
        )

        return response.choices[0].message


    except Exception as e:

        raise Exception(
            f"LLM调用失败:{e}"
        )

def chat_stream(messages):

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        stream=True
    )


    for chunk in response:

        print("chunk:", chunk)

        content = chunk.choices[0].delta.content

        print("content:", content)

        if content:
            yield content