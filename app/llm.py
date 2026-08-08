from openai import OpenAI

from app.config.settings import settings



client = OpenAI(

    api_key=settings.DEEPSEEK_API_KEY,

    base_url=settings.BASE_URL

)



def chat(prompt):

    response = client.chat.completions.create(

        model=settings.MODEL_NAME,

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

            model=settings.MODEL_NAME,

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

        model=settings.MODEL_NAME,

        messages=messages,

        stream=True

    )


    for chunk in response:

        content = chunk.choices[0].delta.content


        if content:

            yield content