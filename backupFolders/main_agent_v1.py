from datetime import datetime
import os
import mysql.connector
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
import openai

# Load environment variables from .env
load_dotenv()

# Database Connection
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)

# OpenAI API Key
# openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

class UserInput(BaseModel):
    category: str = None  # 'restaurant' or 'club'
    place_id: int = None  # Selected restaurant/club ID
    time: str = None      # User-selected time (e.g., '12:30:00')
    action: str = None    # 'list', 'details', 'check_availability', 'menu'


def fetch_places(category):
    """ Fetch restaurants or clubs based on category """
    cursor = conn.cursor(dictionary=True)
    if category == "restaurant":
        query = "SELECT id, name FROM restaurants"
    elif category == "club":
        query = "SELECT id, name FROM clubs"
    else:
        return []
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    return results


def get_place_details(category, place_id):
    """ Get details for the selected restaurant or club """
    cursor = conn.cursor(dictionary=True)
    if category == "restaurant":
        query = """SELECT name, opening_time, closing_time, brunch_time, lunch_time, dinner_time 
                   FROM restaurants WHERE id = %s"""
    else:  # For clubs
        query = """SELECT name, opening_time, closing_time 
                   FROM clubs WHERE id = %s"""
    cursor.execute(query, (place_id,))
    result = cursor.fetchone()
    cursor.close()
    if result:
        for key in ["opening_time", "closing_time", "brunch_time", "lunch_time", "dinner_time"]:
            if key in result and result[key] is not None:
                result[key] = str(result[key])  # Convert to string format
    return result


def check_availability(category, place_id, user_time):
    """ Check if the restaurant/club is available at the given time """
    details = get_place_details(category, place_id)
    if not details:
        return "Invalid selection."

    opening = datetime.strptime(details["opening_time"], "%H:%M:%S").time()
    closing = datetime.strptime(details["closing_time"], "%H:%M:%S").time()
    user_time = datetime.strptime(user_time, "%H:%M:%S").time()

    # Check if the place is open
    if opening <= user_time <= closing:
        return f"✅ {details['name']} is open at {user_time}."
    else:
        return f"❌ {details['name']} is closed at {user_time}."


@app.post("/agent")
def restaurant_club_agent(user_input: UserInput):
    """ Main agent handling user actions """
    action = user_input.action

    if action == "list":
        places = fetch_places(user_input.category)
        return {"places": places}

    elif action == "details":
        details = get_place_details(user_input.category, user_input.place_id)
        return {"details": details}

    elif action == "check_availability":
        result = check_availability(user_input.category, user_input.place_id, user_input.time)
        return {"availability": result}

    elif action == "menu":
        return {"message": "You are back at the main menu!"}

    return {"error": "Invalid action."}
