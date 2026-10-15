import os
import json
import sys
import requests
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Lazy client initialization
_client = None

def get_client():
    """Get or create the OpenAI client (lazy initialization)"""
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "❌ GROQ_API_KEY not found in environment variables.\n"
                "Please add it to .env file:\n"
                "  GROQ_API_KEY=your_key_from_https://console.groq.com/keys\n"
                "Or set it as an environment variable: export GROQ_API_KEY=your_key"
            )
        _client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
    return _client

def calculator(expression: str) -> str:
    """Safe calculator for mathematical expressions"""
    try:
        # Secure eval with restricted operations only
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except Exception:
        return "Calculation error"

WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


def get_weather(city: str) -> str:
    """Get real-time weather for any city (Open-Meteo, no API key required)"""
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=5,
        ).json()
        if not geo.get("results"):
            return f"City not found: {city}"

        place = geo["results"][0]
        lat, lon = place["latitude"], place["longitude"]

        weather = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code",
            },
            timeout=5,
        ).json()

        cur = weather["current"]
        temp = cur["temperature_2m"]
        humidity = cur["relative_humidity_2m"]
        desc = WEATHER_CODES.get(cur["weather_code"], "unknown")
        return f"{place['name']}: {temp}°C, humidity {humidity}%, {desc}"
    except Exception:
        return f"Network error for {city}"

def chat_with_tools(user_message: str) -> str:
    """Main agent function with multi-tool support"""
    client = get_client()
    
    # Define available tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "Calculate mathematical expressions (+, -, *, /, **)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Math expression like '123 + 456 * 2'"
                        }
                    },
                    "required": ["expression"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather for any city worldwide",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City name (Beijing, Berlin, Shanghai, etc.)"
                        }
                    },
                    "required": ["city"]
                }
            }
        }
    ]
    
    messages = [
        {"role": "system", "content": """You are a helpful AI assistant with access to tools. 
You MUST follow these rules:
1. For ANY question about weather, city temperature, humidity, or climate → ALWAYS call get_weather with the city name
2. For ANY math expression, calculation, or number question → ALWAYS call calculator
3. Do not refuse to use tools - use them proactively and immediately
4. After using a tool, provide a friendly response with the results

Examples:
- User: "What's the weather in Berlin?" → Call get_weather("Berlin")
- User: "Calculate 123 + 456" → Call calculator("123 + 456")
- User: "Berlin temperature?" → Call get_weather("Berlin")
"""},
        {"role": "user", "content": user_message}
    ]
    
    # First call: LLM decides which tool(s) to use
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=0.1
    )
    
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls
    
    # Execute tools if needed
    if tool_calls:
        messages.append(response_message)
        
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            
            # Execute appropriate tool
            if func_name == "calculator":
                tool_result = calculator(args["expression"])
            elif func_name == "get_weather":
                tool_result = get_weather(args["city"])
            else:
                tool_result = "Unknown tool"
            
            # Feed tool result back to LLM
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": func_name,
                "content": tool_result
            })
        
        # Second call: LLM generates final response with tool results
        final_response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages
        )
        return final_response.choices[0].message.content
    else:
        return response_message.content

# Demo and testing
if __name__ == "__main__":
    print("🤖 AI Agent Demo - Calculator + Weather Tools")
    print("=" * 50)
    
    test_cases = [
        "Calculate 123 + 456 * 2",
        "What's the weather in Beijing?",
        "Berlin temperature today?",
        "Just say hello"
    ]
    
    for test in test_cases:
        print(f"\nUser: {test}")
        print(f"AI:   {chat_with_tools(test)}")
        print("-" * 50)