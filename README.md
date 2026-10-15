
# Simple Chat Agent

OpenAI-compatible tool-calling AI Agent powered by Groq + GPT-OSS 120B

## 🎯 Features

| Tool | Description | Example |
|------|-------------|---------|
| **Calculator** | Math expressions (`+ - * / **`) | `123 + 456 * 2 = 1035` |
| **Weather** | Real-time weather worldwide | `Beijing: 23°C, 68% humidity` |

**Dual Interface**:
- `python3 agent.py` → Command line
- `streamlit run app.py` → **Web UI** (`localhost:8501`)

## 🚀 Quick Start

```bash
# Clone & Install
git clone git@github.com:jiyan-0525/simple-chat-agent.git
cd simple-chat-agent

# Setup
pip install -r requirements.txt
cp .env.example .env
# Edit .env → Add your GROQ_API_KEY (weather needs no key)

# Run Command Line
python agent.py

# Run Web UI (Recommended)
streamlit run app.py
```

## 🛠️ Tech Stack
- 🤖 AI Engine: Groq + GPT-OSS 120B (openai/gpt-oss-120b)
- 🌐 Web UI: Streamlit
- 🔧 Tools: Calculator + Open-Meteo API (no key required)
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
Free API Keys:

Groq → Fast & Free OpenAI-compatible inference

Open-Meteo → Free weather API (no key needed)
