from app.memory.memory import ConversationMemory



class SessionMemoryManager:


    def __init__(self):

        self.sessions={}



    def get_memory(
        self,
        session_id
    ):


        if session_id not in self.sessions:

            self.sessions[session_id]=(
                ConversationMemory()
            )


        return self.sessions[session_id]