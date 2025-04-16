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

## Redis Installation (Python)
``` pip install redis
redis-server --version
```

## Redis Setup
``` Download Redis for Windows:
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
##  For Ubuntu / Linux:

``` sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis
redis-cli ping
redis-cli

KEYS *
GET user:999:chat_history
```
## Kill Uvicorn (Port 8000) on Windows

```netstat -ano | findstr :8000
taskkill /PID <PID_FROM_ABOVE> /F
```
