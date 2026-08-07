from app.rag_agent import RAGAgent
from app.memory.memory import ConversationMemory


class MockRetriever:


    def retrieve(
        self,
        query,
        top_k=3
    ):

        return [
            {
                "text":"员工入职一年后享受年假",
                "metadata":{
                    "source":"test.txt",
                    "page":1
                }
            }
        ]



memory = ConversationMemory()


agent = RAGAgent(
    MockRetriever(),
    memory
)


print(
    memory.get_history()
)

