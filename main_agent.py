from datetime import datetime, time  # Ensure 'time' is imported
import os,re,random
import dateparser
import mysql.connector
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
# import time
import google.generativeai as genai 
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from chat_history import get_chat_history, move_all_chats_to_mysql, store_chat_in_redis
from utils import check_availability_google, convert_to_ampm, extract_cuisine_type, format_restaurant_chat_response,get_place_details_by_name,check_availability,extract_place_name,find_place_in_db,extract_place_name_gemini,extract_time_from_prompt,gemini_generate_general_response,book_place,get_restaurants,format_places_for_chat,extract_city_area_gemini,get_restaurant_details
from mail import send_email
load_dotenv()
import uvicorn
import spacy
from fuzzywuzzy import process
import razorpay

# Database Connection
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)
# Get API key from environment
api_key = os.getenv("GENAI_API_KEY")

# Configure genai with the API key
genai.configure(api_key=api_key)
app = FastAPI()
# Allow CORS for all origins (Replace "*" with React frontend URL in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to ["http://localhost:3000"] for security
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Load a medium-sized model for better accuracy
nlp = spacy.load("en_core_web_md")  

greetings = [
        "Great choice!", "Awesome pick!", "Fantastic selection!", "You'll love this place!",
        "This place is a must-visit!", "An excellent choice for your meal!"
    ]
booking_prompts = [
        "Would you like to book a table in advance?",
        "Shall I help you reserve a table?",
        "Do you want to secure a spot now?",
        "Want me to check for available reservations?",
        "Planning to dine here? I can help with reservations!"
    ]
 
INTENT_EXAMPLES = {
    "greeting": ["hello", "hi there", "hey", "good morning"],
    "list_places": ["show me restaurants", "list clubs", "find dining places"],
    "check_availability": ["is this place open?", "check if XYZ is available", "what are the timings?","timing"],
    "book_place": ["I want to book a table", "make a reservation", "reserve a spot", "I want to book a table at XYZ", "book my table at XYZ", "book table","book table in XYZ for this saturday or any day","table for 2 at XYZ"],
    "get_details": ["tell me about this place", "give me more info on XYZ", "give me details about xyz", "what about this place xyz", "tell me about", "what is", "give me details on", "Provide a detail", "provide details"]
}

# Intent Priority Order (Higher Index = Higher Priority)
# INTENT_PRIORITY = ["greeting", "list_places", "check_availability", "get_details", "book_place"]
INTENT_PRIORITY = ["list_places", "check_availability", "get_details", "book_place", "greeting"]


# Keywords for early detection
INTENT_KEYWORDS = {
    "greeting": ["hello", "hi", "hey", "morning"],
    "list_places": ["show", "list", "find", "places", "restaurants", "clubs", "dining","place"],
    "check_availability": ["open", "available", "timings", "hours", "closed", "accepting customers",'between','is open'],
    "book_place": ["book", "reservation", "reserve", "schedule",'to','booking'],
    "get_details": ["tell", "details", "info", "what is", "more info", "about", "provide"]
}


def clean_text(text):
    return re.sub(r'[^\w\s]', '', text.lower())

def is_time_only_prompt(prompt: str) -> bool:
    prompt = prompt.lower().strip()
    
    # Check for typical patterns
    time_patterns = [
        r"\b\d{1,2}(:\d{2})?\s*(am|pm)?\b",
        r"\bbetween\s+\d{1,2}(:\d{2})?\s*(am|pm)?\s+and\s+\d{1,2}(:\d{2})?\s*(am|pm)?\b",
        r"\bfrom\s+\d{1,2}(:\d{2})?\s*(am|pm)?\s+to\s+\d{1,2}(:\d{2})?\s*(am|pm)?\b"
    ]
    
    if any(re.search(pattern, prompt) for pattern in time_patterns):
        intent_keywords = [
            "book", "reserve", "open", "available", "details", "show", "list", "find", "info"
        ]
        if not any(word in prompt for word in intent_keywords):
            return True
    return False
def detect_intent(user_prompt,previous_intent=None):
    user_prompt_clean = clean_text(user_prompt)
    intent_scores = {}

    if is_time_only_prompt(user_prompt_clean):
        return previous_intent
    # Step 1: Keyword Matching with count
    for intent, keywords in INTENT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in user_prompt_clean)
        if hits > 0:
            intent_scores[intent] = hits

    # Step 2: Fuzzy Matching if no keyword match
    if not intent_scores:
        for intent, examples in INTENT_EXAMPLES.items():
            match, score = process.extractOne(user_prompt_clean, examples)
            if score > 70:
                intent_scores[intent] = score / 100  # Normalize for later comparison

    # Step 3: Handle no detected intent
    if not intent_scores:
        # If only time is detected and no place name, fallback to previous intent
        if is_time_only_prompt(user_prompt_clean):
            return previous_intent
        else:
            return None
        
    if not intent_scores:
        return None

    print(intent_scores.items(),user_prompt_clean)
    # Step 3: Sort by score desc, then by priority
    sorted_intents = sorted(
        intent_scores.items(),
        key=lambda x: (-x[1], INTENT_PRIORITY.index(x[0]))
    )

    return sorted_intents[0][0]


def parse_user_input(user_input):
    improved_prompt = f"""
        You are a helpful assistant for a restaurant chatbot.

        Extract structured information from the text below and return intent not json formate just return anyone whose match:

        - intent: one of ["list_places", "check_availability", "get_details", "book_place", "greeting","check_availability_with_list_place"]
        - if found this type of prompt  - social house in dubai, xyz in ai safa thn it is intent for get_details beacs the search perticluar place in dubai and underand this type intent also


        Only return intent
        Text: "{user_input}"

        """
   

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(improved_prompt)
        text = response.text.strip()
        return text
    except Exception as e:
        return {"intent": "unknown", "error": str(e)}



class UserInput(BaseModel):
    prompt: str  # User's natural language input
    placeName: Optional[str] = None  # This will be None if not provided
    userTime: Optional[str] = None  # Optional userTime
    userId:Optional[str]  = 99
    previousIntent: Optional[str] = None
@app.post("/agent")
def restaurant_club_agent(user_input: UserInput):
    """ Handle user input and respond with GPT or API logic """
    prompt = user_input.prompt.lower()
    placeName = user_input.placeName
    userTime = user_input.userTime
    userId = user_input.userId
    
    previous_intent = user_input.previousIntent
    parsed = parse_user_input(prompt)
    intent = parsed
    print(intent,'wewwewewe')
    if intent == "greeting":
        return {"response": "Hello! Welcome to our restaurant booking service. How can I assist you today? 🍽️😊",'intent':intent}

    # If the user asks for restaurants and clubs
    if intent == "list_places" or intent == "check_availability_with_list_place":
        
        location_info = extract_city_area_gemini(prompt)
        
        
        if location_info is not None:
            place_parts = [location_info['area'], location_info['city']]
            place_name = ", ".join([part for part in place_parts if part])
        else:
             return {"response": "Sorry, no restaurants found.",'intent':intent}
        
        cuisine = extract_cuisine_type(prompt)
        places = get_restaurants(place_name,cuisine)
        if not places:
            store_chat_in_redis(userId, prompt, "Sorry, no restaurants or clubs found in our database.")
            return {"response": "Sorry, no restaurants or clubs found in our database.",'intent':intent}
        
            

        pretty_chat_message = format_places_for_chat(places)
        
        # Group places by category
       
        response_text = "✨ **Here are some great places for you:**\n\n"

        response_text += pretty_chat_message + "\n\n"
      
        response_text += "Let me know if you'd like details or a booking! 😊"
        store_chat_in_redis(userId, prompt, "Sorry, no restaurants or clubs found in our database.")
        return {"response": response_text,'intent':intent}

    if intent == "check_availability":
        possible_place_name = extract_place_name_gemini(prompt)
       
        if possible_place_name == None or possible_place_name == "None":
            possible_place_name = placeName
        place_name = "Dubai"    

        if possible_place_name != 'None':
            location_info = extract_city_area_gemini(prompt)
            if location_info is not None:
                place_parts = [location_info['area'], location_info['city']]
                place_name = ", ".join([part for part in place_parts if part])
            
            checkAvailability =  check_availability_google(possible_place_name, prompt,place_name)
            store_chat_in_redis(userId, prompt, checkAvailability['response'])
            return checkAvailability
    
        else:
            store_chat_in_redis(userId, prompt, "Please provide a valid Place")
            return {"response":f"Sorry, I couldn't find details. Please provide a valid place name.",'userId':userId,'intent':intent}
            
    if intent == "book_place":
        
        possible_place_name = extract_place_name_gemini(prompt)
       
        if possible_place_name == None or possible_place_name == "None":
            possible_place_name = placeName
        place_name = "Dubai"    

        if possible_place_name != 'None':
            location_info = extract_city_area_gemini(prompt)
            if location_info is not None:
                place_parts = [location_info['area'], location_info['city']]
                place_name = ", ".join([part for part in place_parts if part])
            
           
            checkAvailability =  check_availability_google(possible_place_name, prompt,place_name,True)
            store_chat_in_redis(userId, prompt, checkAvailability['response'])
            return checkAvailability
    
        else:
            store_chat_in_redis(userId, prompt, "Please provide a valid Place")
            return {"response":f"Sorry, I couldn't find details. Please provide a valid place name23232323.",'userId':userId,'intent':intent}

    
    # If the user asks for details
    possible_place_name = extract_place_name_gemini(prompt)
    location_info = extract_city_area_gemini(prompt)
    
    if possible_place_name == None or possible_place_name == "None":
            possible_place_name = placeName
    
    
    place_name = "Dubai"    
    if location_info is not None:
        place_parts = [location_info['area'], location_info['city']]
        place_name = ", ".join([part for part in place_parts if part])
    
    if intent == "get_details":
        if possible_place_name != 'None':
            details = get_restaurant_details(possible_place_name,place_name)
            placeDetails = format_restaurant_chat_response(details)
        
            if placeDetails is not None or  placeDetails != 'None':
                return {"response":placeDetails,'intent':intent}
        else:
            store_chat_in_redis(userId, prompt, "Sorry, I couldn't find details for the specified place.")
            return {"response": "Sorry, I couldn't find details for the specified place. Please provide a valid place name.",'intent':intent}


   
    if possible_place_name != 'None':
        details = get_restaurant_details(possible_place_name,place_name)
        
        placeDetails = format_restaurant_chat_response(details)
        
        
        if placeDetails is not None or placeDetails != 'None':
            return {"response":placeDetails,"placeName":possible_place_name,'intent':intent}
        else:
            
            store_chat_in_redis(userId, prompt, "I couldn't understand your request. Let's try a different one. Remember,\n I'm a helpful assistant that focuses on finding restaurants, clubs, and availability. What would you like to book?") 
            return {"response": "I couldn't understand your request. Let's try a different one. Remember,\n I'm a helpful assistant that focuses on finding restaurants, clubs, and availability. What would you like to book?",'intent':intent}
    else:
       
        store_chat_in_redis(userId, prompt, "I'm a helpful assistant that focuses on finding restaurants, clubs, and availability. What would you like to book?")

        return {"response": " I'm a helpful assistant that focuses on finding restaurants, clubs, and availability. What would you like to book?",'intent':intent}
    
    # Default to GPT response if no conditions are met
    # return {"response": gemini_chat_fallback(prompt)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)