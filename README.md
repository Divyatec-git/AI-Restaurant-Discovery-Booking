# 📘 Book Restaurant Club with AI

This project is an **AI-powered restaurant discovery and booking assistant** built with FastAPI and Redis.

---

## 🚀 Getting Started

### ✅ Create Virtual Environment


python -m venv venv 

### Activate Virtual Environment

venv\Scripts\activate

### pip install -r requirements.txt
### pip freeze > requirements.txt

### uvicorn main_agent:app --host 0.0.0.0 --port 8000 --reload
 ### python --version
 ### pip install package_name

## Redis Setup

``
Download Redis for Windows:
Microsoft Archive Redis Build

cd C:\Redis
redis-server
redis-cli ping
# Should return: PONG

cd C:\Redis
redis-cli

KEYS *                # List all keys
GET chat:user:123     # Get string key
HGETALL chat:user:123 # Get hash key
```
