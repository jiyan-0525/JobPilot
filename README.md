
# Simple Chat Agent

OpenAI-compatible tool-calling AI Agent powered by Groq + Llama 3.1

## 🎯 Features

| Tool | Description | Example |
|------|-------------|---------|
| **Calculator** | Math expressions (`+ - * / **`) | `123 + 456 * 2 = 1035` |
| **Weather** | Real-time weather worldwide | `Beijing: 23°C, 68% humidity` |

**Dual Interface**:
- `python agent.py` → Command line
- `streamlit run app.py` → **Web UI** (`localhost:8501`)

## 🚀 Quick Start

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
```

## 🛠️ Tech Stack
- 🤖 AI Engine: Groq + Llama 3.1 8B Instant
- 🌐 Web UI: Streamlit
- 🔧 Tools: Calculator + OpenWeatherMap API
- 🧪 Testing: GitHub Actions CI/CD
- 📦 Python: 3.10+ | OpenAI SDK v2.30+

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