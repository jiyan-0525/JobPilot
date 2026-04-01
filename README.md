
# Simple Chat Agent

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
