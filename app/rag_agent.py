from app.utils.logger import logger
import time
class RAGAgent:


    def __init__(
        self,
        memory,
        agent_executor
    ):
        
        self.memory = memory

        self.agent_executor = agent_executor



    def answer(
        self,
        query
    ):
        start=time.time()
        logger.info(
            f"user query:{query}"
        )
        self.memory.add_user_message(
            query
        )


        messages = [

            {
                "role":"system",
                "content":
                "你是企业知识库助手。需要时调用工具查询知识库。"
            },

            {
                "role":"user",
                "content":query
            }

        ]


        try:

            response=self.agent_executor.run(
                messages
            )


        except Exception as e:


            logger.error(
                f"agent error:{e}"
            )


            raise e
        cost=time.time()-start


        logger.info(
            f"agent finished cost={cost:.2f}s"
        )

        self.memory.add_ai_message(
            response
        )


        return {

            "answer":response,

            "sources":[]

        }



    def stream_answer(
        self,
        query
    ):


        self.memory.add_user_message(
            query
        )


        messages=[

            {
                "role":"system",
                "content":
                "你是企业知识库助手。需要时调用工具查询知识库。"
            },

            {
                "role":"user",
                "content":query
            }

        ]


        full_answer=""


        for chunk in self.agent_executor.stream_run(
            messages
        ):

            full_answer += chunk

            yield chunk



        self.memory.add_ai_message(
            full_answer
        )



    def update_retriever(
        self,
        retriever
    ):


        self.agent_executor.update_retriever(
            retriever
        )