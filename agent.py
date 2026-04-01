import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

def calculator(expression: str) -> str:
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except:
        return "Calculation error"

def chat_with_tools(user_message: str):
    tools = [{
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Calculate mathematical expressions",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"]
            }
        }
    }]
    
    messages = [{"role": "user", "content": user_message}]
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )
    
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls
    
    if tool_calls:
        messages.append(response_message)
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            if func_name == "calculator":
                tool_result = calculator(args["expression"])
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })
        
        final_response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages
        )
        return final_response.choices[0].message.content
    return response_message.content

if __name__ == "__main__":
    print(chat_with_tools("Help me calculate 123 + 456 * 2"))

