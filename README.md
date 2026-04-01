
# Simple Chat Agent - Project1

OpenAI-compatible tool-calling AI Agent powered by Groq + Llama 3.1

## 🎯 Features
- Automatic tool calling (calculator)
- Safe mathematical expression evaluation
- Natural language responses
- Production-ready project structure

## 🚀 Quick Start
```bash
git clone git@github.com:Fiona-0525/simple-chat-agent.git
cd simple-chat-agent
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API key
python agent.py

User: "Calculate 123 + 456 * 2"
AI: "456 * 2 = 912, then +123 = 1035"

🏗️ Tech Stack
Python 3.10+

Groq API (llama-3.1-8b-instant)

Tool Calling (OpenAI-compatible)

dotenv for environment management

📁 Project Structure
├── agent.py     
├── requirements.txt  
├── .env.example     
├── .gitignore        
└── README.md        

🎓 Learning Outcomes (Week 1)
LLM tool calling workflow

Safe code execution (restricted eval)

Professional Python project setup

GitHub repository best practices

🔮 Next Steps (Week 2)
Add weather API tool

Multi-tool selection logic

Conversation memory

FastAPI deployment


# Simple Chat Agent - Project2

## 🚀 Features

| Tool | Description | Example |
|------|-------------|---------|
| **Calculator** | Math expressions (`+ - * / **`) | `123 + 456 * 2 = 1035` |
| **Weather** | Real-time weather worldwide | `Beijing: 23°C, 68% humidity` |

**Dual Interface**:
- `python agent.py` → Command line
- `streamlit run app.py` → **Web UI** (`localhost:8501`)

## 🎯 Quick Start

```bash
# Clone & Install
git clone git@github.com:Fiona-0525/simple-chat-agent.git
cd simple-chat-agent

# Setup
pip install -r requirements.txt
cp .env.example .env
# Edit .env → Add your GROQ_API_KEY & WEATHER_API_KEY

# Run Command Line
python agent.py

# Run Web UI (Recommended)
streamlit run app.py
🛠️ Tech Stack
text
🤖 AI Engine: Groq + Llama 3.1 8B Instant
🌐 Web UI: Streamlit
🔧 Tools: Calculator + OpenWeatherMap API
🧪 Testing: GitHub Actions CI/CD
📦 Python: 3.10+ | OpenAI SDK v2.30+
📱 Web Demo
text
[Professional Chat Interface]
> "What's Berlin weather?"
"Berlin: 18°C, humidity 72%, partly cloudy"

> "Calculate (15 + 25) * 3"
"(15 + 25) * 3 = 120"
🏗️ Project Structure
text
simple-chat-agent/
├── agent.py          
├── app.py            
├── tests/            
│   ├── __init__.py
│   └── test_agent.py
├── requirements.txt  
├── .env.example     
├── .gitignore      
🔧 Environment Setup
.env file (create from .env.example):

text
GROQ_API_KEY=gsk-your-groq-key-here
WEATHER_API_KEY=your-openweathermap-key
Free API Keys:

Groq → Fast & Free Llama inference

OpenWeatherMap → Free weather API