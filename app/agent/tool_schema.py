def get_tool_schema():

    return [
        {
            "type":"function",
            "function":{
                "name":"knowledge_search",
                "description":
                "查询企业知识库",
                "parameters":{
                    "type":"object",
                    "properties":{
                        "query":{
                            "type":"string"
                        }
                    },
                    "required":[
                        "query"
                    ]
                }
            }
        }
    ]