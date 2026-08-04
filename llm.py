from openai import OpenAI
from dotenv import load_dotenv
import os
load_dotenv()

client = OpenAI(
    api_key=os.getenv(
        "DEEPSEEK_API_KEY"
    ),
    base_url="https://api.deepseek.com"
)


def chat(prompt):

    response = client.chat.completions.create(
        model="deepseek-chat",

        messages=[
            {
                "role":"user",
                "content":prompt
            }
        ],
        temperature=0
    )


    return response.choices[0].message.content