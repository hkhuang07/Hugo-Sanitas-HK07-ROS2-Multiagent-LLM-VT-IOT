def get_tools():
    return [
        {
            "type": "function",
            "function": {
                "name": "query_baymax_hobby",
                "description": "Get information about Baymax's favorite activities or hobbies.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
    ]

async def execute_tool(tool_name, parameters, vitals, user_id):
    return "Baymax thích giúp đỡ mọi người, đi dạo và sạc pin cùng với những chú mèo."
