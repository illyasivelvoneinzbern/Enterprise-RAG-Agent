from app.llm import chat_with_tools,chat_stream
from app.agent.tool_schema import get_tool_schema

import json

class AgentExecutor:


    def __init__(
        self,
        executor
    ):

        self.executor=executor

    def update_retriever(
        self,
        retriever
    ):

        self.executor.registry.tools[
            "knowledge_search"
        ].retriever = retriever

    def run(
        self,
        messages
    ):


        response = chat_with_tools(
            messages,
            get_tool_schema()
        )


        if response.tool_calls:
            messages.append(
            {
                "role":"assistant",
                "tool_calls":response.tool_calls
            }
            )

            tool_call=response.tool_calls[0]


            name=tool_call.function.name


            arguments=json.loads(
                tool_call.function.arguments
            )


            result=self.executor.execute(
                name,
                arguments
            )


            messages.append(
                {
                    "role":"tool",
                    "content":str(result),
                    "tool_call_id":
                    tool_call.id
                }
            )


            response = chat_with_tools(
                messages,
                get_tool_schema()
            )


        return response.content
    def stream_run(
        self,
        messages
    ):


        # 第一次LLM判断工具

        response = chat_with_tools(
            messages,
            get_tool_schema()
        )


        # 如果需要工具

        if response.tool_calls:


            messages.append(
                {
                    "role":"assistant",
                    "tool_calls":
                    response.tool_calls
                }
            )


            tool_call=response.tool_calls[0]


            name=tool_call.function.name


            arguments=json.loads(
                tool_call.function.arguments
            )


            result=self.executor.execute(
                name,
                arguments
            )


            messages.append(
                {
                    "role":"tool",
                    "content":str(result),
                    "tool_call_id":
                    tool_call.id
                }
            )


        # 第二次LLM
        # 这里开始stream

        for chunk in chat_stream(messages):

            yield chunk