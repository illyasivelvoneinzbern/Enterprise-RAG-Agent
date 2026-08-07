class ConversationMemory:


    def __init__(
        self,
        max_messages=10
    ):

        self.messages=[]

        self.max_messages=max_messages



    def add_user_message(
        self,
        message
    ):

        self.messages.append(
            {
                "role":"user",
                "content":message
            }
        )


        self._trim()



    def add_ai_message(
        self,
        message
    ):

        self.messages.append(
            {
                "role":"assistant",
                "content":message
            }
        )


        self._trim()



    def _trim(self):

        while len(self.messages)>self.max_messages:

            self.messages.pop(0)



    def get_history(self):

        return self.messages