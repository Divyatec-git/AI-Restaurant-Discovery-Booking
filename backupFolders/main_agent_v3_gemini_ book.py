from datetime import datetime
import os,re
import mysql.connector
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
import time
import spacy # type: ignore
import google.generativeai as genai 
from fastapi.middleware.cors import CORSMiddleware

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
# Allow CORS for all origins (Replace "*" with React frontend URL in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to ["http://localhost:3000"] for security
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

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
    query = """SELECT name, opening_time, closing_time,brunch_time,lunch_time,dinner_time, 'restaurant' AS category 
               FROM restaurants WHERE name LIKE %s 
               UNION 
               SELECT name, opening_time, closing_time,brunch_time,lunch_time,dinner_time, 'club' AS category 
               FROM clubs WHERE name LIKE %s"""
   
    cursor.execute(query, (f"%{place_name}%", f"%{place_name}%"))
    result = cursor.fetchone()
    cursor.close()

    # Convert time fields to strings
    if result:
        result["opening_time"] = str(result["opening_time"])
        result["closing_time"] = str(result["closing_time"])
        result["brunch_time"] = str(result["brunch_time"])
        result["lunch_time"] = str(result["lunch_time"])
        result["dinner_time"] = str(result["dinner_time"])

    
    return result

def check_availability(place_name, user_time):
    """Check if a place is open at a given time, including midnight cases."""
    details = get_place_details_by_name(place_name)
    if not details:
        return f"Sorry, I couldn't find details for {place_name}."

    opening = datetime.strptime(details["opening_time"], "%H:%M:%S").time()
    closing = datetime.strptime(details["closing_time"], "%H:%M:%S").time()
    user_time = datetime.strptime(user_time, "%H:%M:%S").time()

    

    # Handle normal opening-closing case (same day)
    if opening <= closing:
        if opening <= user_time <= closing:
            return {"response":f"✅ {details['name']} is open at {user_time}. The Bruch time is {details['brunch_time']}, lunch time is {details['lunch_time']}  and Dinner will be {details['dinner_time']}"}
        else:
            return  {"response":f"❌ {details['name']} is closed at {user_time}."}

    # Handle midnight case (e.g., opening at 9 PM and closing at 5 AM)
    else:
        if user_time >= opening or user_time <= closing:
            return {"response":f"✅ {details['name']} is open at {user_time}. The Bruch time is {details['brunch_time']}, lunch time is {details['lunch_time']}  and Dinner will be {details['dinner_time']}"}
        else:
            return {"response":f"❌ {details['name']} is closed at {user_time}."}

def fetch_place_info(place_name):
    """Fetch restaurant or club details by name"""
    cursor = conn.cursor(dictionary=True)
    
    query = """SELECT name, opening_time, closing_time,brunch_time,lunch_time,dinner_time, 'restaurant' AS type FROM restaurants WHERE name LIKE %s 
               UNION 
               SELECT name, opening_time, closing_time,bruch_time,lunch_time,dinner_time, 'club' AS type FROM clubs WHERE name LIKE %s"""
    
    cursor.execute(query, (f"%{place_name}%", f"%{place_name}%"))
    result = cursor.fetchone()
    cursor.close()

    if result:
        return f"{result['name']} is a {result['type']}. It is open from {result['opening_time']} to {result['closing_time']}. Also the bruch time is {result['brunch_time']}, lunch time is {result['lunch_time']}  and Dinner will be {result['dinner_time']}."
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

def gemini_chat_fallback(prompt):
    """Friendly Gemini chat fallback when no availability check is needed"""
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Adding a friendly response starter
    full_prompt = f"""
    You are a helpful assistant. If the user asks for **availability of a restaurant or club**, extract details and return "None".
    Otherwise, reply in a friendly, engaging way.

    Examples:
    - User: "Check availability at The Food Lounge at 4 PM?" → Response: "None"
    - User: "Tell me something interesting about AI!" → Response: "Sure! AI is transforming..."
    - User: "Who is the president of the USA?" → Response: "As of today, the president is..."
    - User: "Hello" → Response: "Hello! How can I assist you today?"

    User: "{prompt}"
    """

    response = model.generate_content(full_prompt)
    return response.text.strip()

def extract_meal_type(prompt):
    meal_keywords = ['brunch', 'lunch', 'dinner']
    
    # Use regex to find the first occurrence of a meal type in the prompt
    match = re.search(r'\b(brunch|lunch|dinner)\b', prompt, re.IGNORECASE)
    
    if match:
        return match.group(1).lower()  # Return the matched meal type in lowercase
    else:
        return None  # Return None if no meal type is found
   # In-memory dictionary to store user bookings
user_bookings = {}
 
def book_place(place_name, user_time,userId,prompt):
    
    """Insert fake data into restaurants and clubs tables"""
    cursor = conn.cursor(dictionary=True)
    """Check if a place is open at a given time, including midnight cases."""
    details = get_place_details_by_name(place_name)
    if not details:
        return f"Sorry, I couldn't find details for {place_name}."

    opening = datetime.strptime(details["opening_time"], "%H:%M:%S").time()
    closing = datetime.strptime(details["closing_time"], "%H:%M:%S").time()
    user_time = datetime.strptime(user_time, "%H:%M:%S").time()
    category =  details["category"]
    
    query = ""
    mealType = None
    # Handle normal opening-closing case (same day)
    if opening <= closing:
        if opening <= user_time <= closing:
            if category == "restaurant":
               
                query = f"""
                        INSERT INTO book_{category}s (place_name, booking_time,user_id,meal_type)
                        VALUES (%s, %s, %s,%s)
                        """
        else:
            return {"response":f"Sorry, {place_name} is closed at {closing}. 😔 But don't worry, we'll make sure to book your table for another time. 📅 Just let us know when you're free! 😊"}
   
    # Handle midnight case (e.g., opening at 9 PM and closing at 5 AM)
    else:
        if user_time >= opening or user_time <= closing:
                
                query = f"""
                        INSERT INTO book_{category}s (place_name, booking_time,user_id,meal_type)
                        VALUES (%s, %s, %s,%s)
                        """  
        else:
           return {"response":f"Sorry, {place_name} is closed at {closing}. 😔 But don't worry, we'll make sure to book your table for another time. 📅 Just let us know when you're free! 😊"}
    
    cursor.execute(query, (place_name, user_time,userId,mealType))
   

    conn.commit()
    cursor.close()
 
    return {"response": f"🎉 Your booking for **{place_name}** at **{user_time.strftime('%I:%M %p')}** has been successfully confirmed! We will make sure to reserve a table for you at that time. Please arrive on time to ensure a smooth experience. If you need to cancel or change your booking, please let us know as soon as possible. Thank you for choosing {place_name}! 🎉"}

@app.post("/agent")
def restaurant_club_agent(user_input: UserInput,userId = 0):
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

    
    if "check" in prompt or "availability" in prompt:
        place_name = extract_place_name_gemini(prompt)
        if place_name:
            user_time = extract_time_from_prompt(prompt)
            if user_time:
                return check_availability(place_name, user_time)
            else:
                return {"response": "Please provide a valid time."}
        else:
            return {"response": "Please provide a valid place name."}
    
    if "book" in prompt or "booking" in prompt or "reserve" in prompt or 'brunch' in prompt or 'lunch' in prompt or 'dinner' in prompt:
        print(prompt)
        place_name = extract_place_name_gemini(prompt)
        if place_name:
            user_time = extract_time_from_prompt(prompt)
            if user_time:
                return book_place(place_name,user_time,userId,prompt)
            else:
                return {"response": "Please provide a valid time."}
        else:
            return {"response": "Please provide a valid place name."}

    # If the user asks for details
    possible_place_name = extract_place_name_gemini(user_input)
    if possible_place_name:
        details = get_place_details_by_name(possible_place_name)
       
        if details:
            place_name = details["name"]
            category = details.get("category", details.get("type", "Unknown"))
            opening_time = details["opening_time"]
            closing_time = details["closing_time"]
            

            return {
                "response": f"Great choice! {place_name} ({category}) is open from {opening_time} to {closing_time}.Brunch will be at {details['brunch_time']}, Lunch will be at {details['lunch_time']} and Dinner will be at {details['dinner_time']}."
            }
        else:
            if all(word in prompt for word in ["details", "want", "go", "let", "know"]):
                return {"response": "I couldn't find that place."}

    # Default to GPT response if no conditions are met
    return {"response": gemini_chat_fallback(prompt)}

