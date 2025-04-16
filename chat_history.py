import redis
import json
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv
load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)
# Connect to Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def store_chat_in_redis(user_id, prompt, response):
    
    """Store chat messages temporarily in Redis for multiple users"""
    history_key = f"user:{user_id}:chat_history"

    # Load existing chat history
    existing_history = redis_client.get(history_key)
    chat_history = json.loads(existing_history) if existing_history else []

    # Append new chat entry
    chat_history.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "prompt": prompt,
        "response": response
    })

    # Save back to Redis with 1-hour expiry
    # Store the updated chat history back in Redis with a 1-hour expiration time
    # 'redis_client.setex' is used to set the value of 'history_key' in Redis
    # with an expiration time (in seconds) specified as the second argument
    # Here, the expiration time is set to 3600 seconds (1 hour)
    # 'json.dumps(chat_history)' converts the chat history list to a JSON string
    redis_client.setex(history_key, 3600, json.dumps(chat_history))

# Example: Store chat for multiple users
# store_chat_in_redis("123", "Hi!", "Hello!")
# store_chat_in_redis("456", "Recommend a club", "Try Electric Beats!")


# Redis is an in-memory, NoSQL data store that allows you to store and
# retrieve data quickly. It can be used as a database, message broker, or
# caching layer. It stores data in a key-value format, making it easy to
# store and retrieve values. Redis is a popular choice for caching data
# because it is fast and can be easily scaled horizontally. It is also
# commonly used for leaderboards, sessions, and other real-time data needs.

def get_chat_history(user_id):
    history_key = f"user:{user_id}:chat_history"
    try:
        # Retrieve the chat history for the given user_id from Redis
        # 'redis_client.get' fetches the value stored at 'history_key'
        # The value is expected to be a JSON string representing the user's chat history
        # If the key does not exist, 'redis_client.get' returns None
        chat_history = redis_client.get(history_key)
        return json.loads(chat_history) if chat_history else []
    except Exception as e:
        print(f"Error getting chat history for user {user_id}: {e}")
        return []


def move_all_chats_to_mysql(userId = None):
    """Move all user chat history from Redis to MySQL"""
    
    # Create table in MySQL if it does not exist
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT NOT NULL,
            

            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cursor.close()
    if userId is not None:
        keys = [f"user:{userId}:chat_history"]
    else:
        keys = redis_client.keys("user:*:chat_history")  # Get all user chat keys
   
    for key in keys:
        cursor = conn.cursor(dictionary=True)
        user_id = key.split(":")[1]  # Extract user_id from key
        chat_data = redis_client.get(key)  # Get chat data from Redis user:495:chat_history

        if chat_data:
            chat_history = json.loads(chat_data)
            
            for chat in chat_history:
               
                cursor.execute(
                    "INSERT INTO chat_history (user_id, prompt, response, timestamp) VALUES (%s, %s, %s, %s)",
                    (user_id, chat["prompt"], chat["response"], chat["timestamp"])
                )
            conn.commit()
        cursor.close()
           
            # redis_client.delete(key)  # Remove user chat from Redis after storing
    return "Data Saved successfully"
# Run function to move all users' chats
# move_all_chats_to_mysql()