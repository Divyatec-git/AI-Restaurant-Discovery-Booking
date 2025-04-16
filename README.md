# 📘 Book Restaurant Club with AI

This project is an **AI-powered restaurant discovery and booking assistant** built with FastAPI and Redis.

---

## 🧠 What It Does

- 🔍 **Restaurant Discovery**  
  Easily find restaurants based on location, cuisine, rating, and other preferences using intelligent filtering and search.

- 📅 **Smart Booking System**  
  Handles reservation requests with real-time availability checks and stores booking information securely.

- 💬 **Automated WhatsApp Notifications**  
  Sends confirmation and reminder messages to users via WhatsApp for a seamless communication experience.

- 🗃️ **Booking History and Storage**  
  Uses a fast in-memory Redis database to manage user sessions, bookings, and chat history.

- ⚡ **FastAPI Backend**  
  Provides a high-performance API interface for integrating with chat agents or front-end clients.

---

This makes the platform a perfect assistant for both restaurant-goers and businesses to **automate bookings**, **engage users**, and **improve customer experience**.
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
```
   pip install redis
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

```
Start
  │
  ▼
Receive User Input (prompt, placeName, userTime, userId, previousIntent)
  │
  ▼
Parse Intent from Prompt
  │
  ├── Is Intent = greeting?
  │       └── Yes → Return greeting message
  │
  ├── Is Intent = list_places OR check_availability_with_list_place?
  │       └── Extract city/area
  │             └── If location found
  │                  └── Get restaurants list
  │                       └── If restaurants found → Format and return list
  │                       └── Else → Return "no restaurants found"
  │             └── Else → Return "no restaurants found"
  │
  ├── Is Intent = check_availability?
  │       └── Extract place name
  │       └── Extract location
  │       └── Get availability via Google API
  │       └── Return availability response
  │
  ├── Is Intent = book_place?
  │       └── Extract place name and location
  │       └── Call check availability with booking=True
  │       └── Return booking response
  │
  ├── Is Intent = get_details?
  │       └── Extract place name and location
  │       └── Get details via Google API
  │       └── Format and return restaurant details
  │
  └── Else
          ├── Try to extract details anyway
          └── If found → Return details
          └── Else → Return default fallback message

End
```
