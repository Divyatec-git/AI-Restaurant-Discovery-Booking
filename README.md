# book_restaurant_club_with_AI
type requirements.txt  # For Windows
pip freeze > requirements.txt
pip install -r requirements.txt
uvicorn main_agent:app --host 0.0.0.0 --port 8000 --reload

python -m venv venv
venv\Scripts\activate
source venv/Scripts/activate
source venv/bin/activate
(venv) C:\Users\YourUsername\Projects\MyProject>
python --version
pip install package_name


For Windows:
Download Redis for Windows from here.
Extract it to C:\Redis.
Open Command Prompt and navigate to the folder:
    cd C:\Redis
    redis-server
Verify Redis is Running
    redis-cli ping
    If it returns PONG, Redis is running.


Check Redis Data via CLI
 cd C:\Redis
redis-cli
KEYS *      # List all stored keys
    GET chat:user:123   # Replace with your Redis key
HGETALL chat:user:123
GET your_key


kill uvicron in windows

netstat -ano | findstr :8000
taskkill /PID 12345 /F

redis for ubnatu 

redis-cli
KEYS *
GET user:999:chat_history





pip install redis
redis-server --version
sudo systemctl start redis
sudo systemctl enable redis
redis-cli ping
