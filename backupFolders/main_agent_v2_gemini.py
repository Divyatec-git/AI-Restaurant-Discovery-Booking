from datetime import datetime
import os
import mysql.connector
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
import time
import spacy # type: ignore
import google.generativeai as genai 

# Load environment variables
load_dotenv()
nlp = spacy.load("en_core_web_sm")
# Database Connection
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)

# OpenAI API Key

genai.configure(api_key='')

app = FastAPI()

class UserInput(BaseModel):
    prompt: str  # User's natural language input


def fetch_places():
    """ Fetch both restaurants and clubs in the database """
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT id, name, 'restaurant' AS category FROM restaurants 
        UNION 
        SELECT id, name, 'club' AS category FROM clubs
    """
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    return results

def get_place_details_by_name(place_name):
    """Search for a place in both restaurants and clubs"""
    cursor = conn.cursor(dictionary=True)
   
    # Search in both tables
    query = """SELECT name, opening_time, closing_time, 'restaurant' AS category 
               FROM restaurants WHERE name LIKE %s 
               UNION 
               SELECT name, opening_time, closing_time, 'club' AS category 
               FROM clubs WHERE name LIKE %s"""
    
    cursor.execute(query, (f"%{place_name}%", f"%{place_name}%"))
    result = cursor.fetchone()
    cursor.close()

    # Convert time fields to strings
    if result:
        result["opening_time"] = str(result["opening_time"])
        result["closing_time"] = str(result["closing_time"])
    
    return result

def check_availability(place_name, user_time):
    """Check if a place is open at a given time"""
    details = get_place_details_by_name(place_name)
    if not details:
        return f"Sorry, I couldn't find details for {place_name}."

    opening = datetime.strptime(details["opening_time"], "%H:%M:%S").time()
    closing = datetime.strptime(details["closing_time"], "%H:%M:%S").time()
    user_time = datetime.strptime(user_time, "%H:%M:%S").time()

    if opening <= user_time <= closing:
        return f"✅ {details['name']} is open at {user_time}."
    else:
        return f"❌ {details['name']} is closed at {user_time}."

def fetch_place_info(place_name):
    """Fetch restaurant or club details by name"""
    cursor = conn.cursor(dictionary=True)
    
    query = """SELECT name, opening_time, closing_time, 'restaurant' AS type FROM restaurants WHERE name LIKE %s 
               UNION 
               SELECT name, opening_time, closing_time, 'club' AS type FROM clubs WHERE name LIKE %s"""
    
    cursor.execute(query, (f"%{place_name}%", f"%{place_name}%"))
    result = cursor.fetchone()
    cursor.close()

    if result:
        return f"{result['name']} is a {result['type']}. It is open from {result['opening_time']} to {result['closing_time']}."
    return "Sorry, I couldn't find that place."

def extract_place_name(prompt):
    """Extracts the place name from a natural language prompt."""
    # Remove common words that aren't part of the place name
    stopwords = {"give", "me", "details", "for", "about", "information", "on", "a","is", "in",'i','want','go','to','the'}
    words = [word for word in prompt.split() if word not in stopwords]

    # Join remaining words (assume it's the place name)
    place_name = " ".join(words).title()  # Capitalize words to match DB
    
    return place_name if place_name else None

def extract_place_name_gemini(prompt,max_retries=3, wait_time=60):
    """Use Google Gemini API to extract a potential place name"""
    model = genai.GenerativeModel("gemini-2.0-flash")
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                f"Extract the restaurant or club name from this text: '{prompt}'. If there is no place name, return 'None'."
            )
            
            extracted_name = response.text.strip()
            return extracted_name
        
        except Exception as e:
            if "RateLimitError" in str(e):
                print(f"Rate limit reached. Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"Error: {e}")
                break  # Exit loop if it's not a rate limit error

    return None  # Return None if all retries fail

def extract_time_from_prompt(prompt):
    """Extracts time from any user input and converts it to HH:MM:SS format."""
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt_text = f"""
    Extract the time from the following text in a **24-hour format (HH:MM)**.
    If no time is found, return "None".

    Example Inputs:
    - "Check availability at 6:30 PM"  →  "18:30"
    - "I want to visit at noon" → "12:00"
    - "Is it open at 5 AM?" → "05:00"
    - "Can I visit at midnight?" → "00:00"
    - "Let's go now" → "None"
    - "The restaurant is open from 4PM to 11PM" → "16:00"

    Now extract time from:
    "{prompt}"
    """

    response = model.generate_content(prompt_text)
    extracted_time = response.text.strip().replace('"', '')  # Remove extra quotes

    if extracted_time.lower() == "none":
        return None  # No valid time found

    # Try multiple time formats
    for fmt in ["%H:%M", "%I %p", "%I:%M %p"]:  # Covers 24-hour and 12-hour formats
        try:
            time_obj = datetime.strptime(extracted_time, fmt).time()
            return time_obj.strftime("%H:%M:%S")  # Standardize format
        except ValueError:
            continue  # Try next format

    print("❌ Invalid time format:", extracted_time)  # Debugging
    return None  # Return None if all formats fail


@app.post("/agent")
def restaurant_club_agent(user_input: UserInput):
    """ Handle user input and respond with GPT or API logic """
    prompt = user_input.prompt.lower()
    # print(prompt.split())  # Debugging line to check tokenization

    # If the user asks for restaurants and clubs
    if ("restaurant" in prompt or "club" in prompt) and "list" in prompt:
        places = fetch_places()
        if not places:
            return {"response": "Sorry, no restaurants or clubs found in our database."}

        # Generate a friendly response
        place_list = "\n".join([f"- {p['name']} ({p['category']})" for p in places])
        return {"response": f"Here are some places you might like:\n{place_list}"}

    
    if "check" in prompt and "availability" in prompt:
        place_name = extract_place_name_gemini(prompt)
        if place_name:
            user_time = extract_time_from_prompt(prompt)
            if user_time:
                return check_availability(place_name, user_time)
            else:
                return {"response": "Please provide a valid time."}
        else:
            return {"response": "Please provide a valid place name."}

    possible_place_name = extract_place_name_gemini(user_input)
    if possible_place_name:
        details = get_place_details_by_name(possible_place_name)
       
        if details:
            place_name = details["name"]
            category = details.get("category", details.get("type", "Unknown"))
            opening_time = details["opening_time"]
            closing_time = details["closing_time"]

            return {
                "response": f"Great choice! {place_name} ({category}) is open from {opening_time} to {closing_time}."
            }

    # Default to GPT response if no conditions are met
    return {"response": "not found"}

