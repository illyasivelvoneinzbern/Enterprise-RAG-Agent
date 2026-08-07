class ToolExecutor:


    def __init__(
        self,
        registry
    ):

        self.registry=registry



    def execute(
        self,
        name,
        arguments
    ):

        tool=self.registry.get(
            name
        )


        if tool is None:

            raise Exception(
                "Tool不存在"
            )


        return tool.run(
            **arguments
        )