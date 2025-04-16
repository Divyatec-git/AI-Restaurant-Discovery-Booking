from datetime import datetime, time  # Ensure 'time' is imported
import os,re,random
import mysql.connector
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
# import time
import google.generativeai as genai 
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from chat_history import get_chat_history, move_all_chats_to_mysql, store_chat_in_redis
from utils import convert_to_ampm,fetch_places,get_place_details_by_name,check_availability,extract_place_name,find_place_in_db,extract_place_name_gemini,extract_time_from_prompt,gemini_generate_general_response,book_place
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
    "book_place": ["I want to book a table", "make a reservation", "reserve a spot", "I want to book a table at XYZ", "book my table at XYZ", "book table"],
    "get_details": ["tell me about this place", "give me more info on XYZ", "give me details about xyz", "what about this place xyz", "tell me about", "what is", "give me details on", "Provide a detail", "provide details"]
}

# Intent Priority Order (Higher Index = Higher Priority)
INTENT_PRIORITY = ["greeting", "list_places", "check_availability", "get_details", "book_place"]

# Keywords for early detection
INTENT_KEYWORDS = {
    "greeting": ["hello", "hi", "hey", "morning"],
    "list_places": ["show", "list", "find", "places", "restaurants", "clubs", "dining","place"],
    "check_availability": ["open", "available", "timings", "hours", "closed", "accepting customers",'between'],
    "book_place": ["book", "reservation", "reserve", "schedule",'to'],
    "get_details": ["tell", "details", "info", "what is", "more info", "about", "provide"]
}


def clean_text(text):
    return re.sub(r'[^\w\s]', '', text.lower())

def detect_intent(user_prompt):
    """ Identify the most relevant single intent """
    user_prompt_clean = clean_text(user_prompt)
    detected_intents = set()

    # Step 1: Keyword Matching
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in user_prompt_clean:
                detected_intents.add(intent)

    # Step 2: Fuzzy Matching if No Keywords Found
    if not detected_intents:
        for intent, examples in INTENT_EXAMPLES.items():
            match, score = process.extractOne(user_prompt_clean, examples)
            if score > 70:  # Lowered threshold to detect similar phrases
                detected_intents.add(intent)

    if not detected_intents:
        return None  # No intent found

    # Step 3: Return the highest-priority intent
    return sorted(detected_intents, key=lambda i: INTENT_PRIORITY.index(i))[-1]

class UserInput(BaseModel):
    prompt: str  # User's natural language input
    placeName: Optional[str] = None  # This will be None if not provided
    userTime: Optional[str] = None  # Optional userTime
    userId:Optional[str]  = 99
@app.post("/agent")
def restaurant_club_agent(user_input: UserInput):
    """ Handle user input and respond with GPT or API logic """
    prompt = user_input.prompt.lower()
    placeName = user_input.placeName
    userTime = user_input.userTime
    userId = user_input.userId
    

    intent = detect_intent(prompt)
    
    if 'date' in prompt or "fix" in prompt:
        return {"response":"🤣🤖 Bhai, restaurant ki booking karva sakti hoon... Teri shadi nahi! 🍽️😂💔 "}
    
    if intent == "greeting":
        return {"response": "Hello! Welcome to our restaurant booking service. How can I assist you today? 🍽️😊"}

    # If the user asks for restaurants and clubs
    if intent == "list_places":
        restaurants_keywords = {"restaurants", "restaurant", "food", "dine", "lunch", "dinner"}
        clubs_keywords = {"clubs", "club", "nightlife", "night", "bar"}

        has_restaurant = any(k in prompt for k in restaurants_keywords)
        has_club = any(k in prompt for k in clubs_keywords)

        places = fetch_places() if has_restaurant and has_club else fetch_places("club" if has_club else "restaurant" if has_restaurant else None)

            
        if not places:
            store_chat_in_redis(userId, prompt, "Sorry, no restaurants or clubs found in our database.")
            return {"response": "Sorry, no restaurants or clubs found in our database."}

        
        # Group places by category
        restaurants = [p['name'] for p in places if p['category'].lower() == "restaurant"]
        clubs = [p['name'] for p in places if p['category'].lower() == "club"]

        response_text = "✨ **Here are some great places for you:**\n\n"

        if restaurants:
            response_text += "🍽️ **Restaurants:**\n" + "\n".join([f"- {r}" for r in restaurants]) + "\n\n"
        if clubs:
            response_text += "🎶 **Clubs:**\n" + "\n".join([f"- {c}" for c in clubs]) + "\n\n"

        response_text += "Let me know if you'd like details or a booking! 😊"
        store_chat_in_redis(userId, prompt, "Sorry, no restaurants or clubs found in our database.")
        return {"response": response_text}

    if intent == "check_availability":
        place_name = extract_place_name_gemini(prompt)
        print(place_name,'-----')
        if place_name == None or place_name == "None":
            place_name = placeName
        
        if place_name:
            details = get_place_details_by_name(place_name)
            print(place_name,'-----')
            if not details:
                store_chat_in_redis(userId, prompt, "Please provide a valid time,placeName:{place_name}")
                return {"response":f"Sorry, I couldn't find details. Please provide a valid place name.","placeName":place_name,'userId':userId}
            
            user_time = extract_time_from_prompt(prompt)
            if user_time == None or user_time == "None":
                user_time = userTime
            if user_time:
                checkAvailability =  check_availability(place_name, user_time,userId)
                store_chat_in_redis(userId, prompt, checkAvailability['response'])
                return checkAvailability
            else:
                store_chat_in_redis(userId, prompt, "Please provide a valid time.")
                return {"response": "Please provide a valid time."}
        else:
            data = gemini_generate_general_response(prompt)
            store_chat_in_redis(userId, prompt, data)  
            return {"response": data}
            store_chat_in_redis(userId, prompt, "Please provide a valid place name.")
            return {"response": "Please provide a valid place name."}
    
    if intent == "book_place":
        
        place_name = extract_place_name_gemini(prompt)
        print(place_name,'-----new')
        if place_name == None or place_name == "None":
            place_name = placeName
        if place_name:
            print(place_name,'-----')
            details = get_place_details_by_name(place_name)
            if not details:
                store_chat_in_redis(userId, prompt, f"Sorry, I couldn't find details for {place_name}.")
                return {"response":f"Sorry, I couldn't find details. Please provide a valid place name.","placeName":place_name,'userId':userId}

            user_time = extract_time_from_prompt(prompt)
            
            if user_time == None or user_time == "None":
                user_time = userTime
            
            if user_time:
                print(user_time,'-----time')
                return book_place(place_name,user_time,userId,prompt)
            else:
                store_chat_in_redis(userId, prompt, "Please provide a valid time,placeName:{place_name}")
                return {"response": "Please provide a valid time.","placeName":place_name}
        else:
            data = gemini_generate_general_response(prompt)
            store_chat_in_redis(userId, prompt, data)  
            return {"response": data}
            store_chat_in_redis(userId, prompt, "Please provide a valid place name.")
            return {"response": "Please provide a valid place name."}

    greeting = random.choice(greetings)
    booking_suggestion = random.choice(booking_prompts) 
    # If the user asks for details
    possible_place_name = extract_place_name_gemini(prompt)
    if intent == "get_details":
        details = get_place_details_by_name(possible_place_name)
        
        if details:
            place_name = details["name"]
            category = details.get("category", details.get("type", "Unknown"))
            opening_time = convert_to_ampm(details["opening_time"])
            closing_time = convert_to_ampm(details["closing_time"])
            
            store_chat_in_redis(userId, prompt,f"{greeting} {place_name} ({category}) is open from {opening_time} to {closing_time}. Brunch is served from {convert_to_ampm(details['brunch_open_time'])} to {convert_to_ampm(details['brunch_close_time'])}, Lunch from {convert_to_ampm(details['lunch_open_time'])} to {convert_to_ampm(details['lunch_close_time'])}, and Dinner from {convert_to_ampm(details['dinner_open_time'])} to {convert_to_ampm(details['dinner_close_time'])}. \n {booking_suggestion}")
            return {
                "response": f"{greeting} {place_name} ({category}) is open from {opening_time} to {closing_time}. Brunch is served from {convert_to_ampm(details['brunch_open_time'])} to {convert_to_ampm(details['brunch_close_time'])}, Lunch from {convert_to_ampm(details['lunch_open_time'])} to {convert_to_ampm(details['lunch_close_time'])}, and Dinner from {convert_to_ampm(details['dinner_open_time'])} to {convert_to_ampm(details['dinner_close_time'])}. \n {booking_suggestion}","placeName":place_name
            }
        else:
            if all(word in prompt for word in ["details", "want", "go", "let", "know"]):
                store_chat_in_redis(userId, prompt, "I'd love to help! Could you tell me what you're looking for—restaurants, clubs, or both? \n And do you have a specific location in mind?")
                return {"response": "I'd love to help! Could you tell me what you're looking for—restaurants, clubs, or both? \n And do you have a specific location in mind?"}
                

    place_name = extract_place_name(prompt)
    if place_name:
        results = find_place_in_db(place_name)
        
        if results:
            for place in results:
                place_name = place["name"]
                details = get_place_details_by_name(place_name)
               
                if details:
                    place_name = details["name"]
                    category = details.get("category", details.get("type", "Unknown"))
                    opening_time = convert_to_ampm(details["opening_time"])
                    closing_time = convert_to_ampm(details["closing_time"])
                    
                    store_chat_in_redis(userId, prompt,  f"{greeting}{place_name} ({category}) is open from {opening_time} to {closing_time}. Brunch is served from {convert_to_ampm(details['brunch_open_time'])} to {convert_to_ampm(details['brunch_close_time'])}, Lunch from {convert_to_ampm(details['lunch_open_time'])} to {convert_to_ampm(details['lunch_close_time'])}, and Dinner from {convert_to_ampm(details['dinner_open_time'])} to {convert_to_ampm(details['dinner_close_time'])}. \n {booking_suggestion}")
                    return {
                        "response": f"{greeting} {place_name} ({category}) is open from {opening_time} to {closing_time}. Brunch is served from {convert_to_ampm(details['brunch_open_time'])} to {convert_to_ampm(details['brunch_close_time'])}, Lunch from {convert_to_ampm(details['lunch_open_time'])} to {convert_to_ampm(details['lunch_close_time'])}, and Dinner from {convert_to_ampm(details['dinner_open_time'])} to {convert_to_ampm(details['dinner_close_time'])}. \n {booking_suggestion}","placeName":place_name
                    }
                else:
                    if all(word in prompt for word in ["details", "want", "go", "let", "know"]):
                        store_chat_in_redis(userId, prompt, "I couldn't find this information. I’d love to help! I focus on finding restaurants, clubs, and availability. What would you like to book?")
                        return {"response": "I couldn't find this information.\n I’d love to help! I focus on finding restaurants, clubs, and availability. What would you like to book?"}
        else:
            data = gemini_generate_general_response(prompt)
            store_chat_in_redis(userId, prompt, data)  
            return {"response": data}
            # return {"response": "I couldn't understand your request. Let's try a different one. Remember,\n I'm a helpful assistant that focuses on finding restaurants, clubs, and availability. What would you like to book?"}
    else:
        data = gemini_generate_general_response(prompt)
        store_chat_in_redis(userId, prompt, data)
        return {"response": data}
        # return {"response": " I'm a helpful assistant that focuses on finding restaurants, clubs, and availability. What would you like to book?"}
    
    # Default to GPT response if no conditions are met
    # return {"response": gemini_chat_fallback(prompt)}

# Define the request model
class BookingRequest(BaseModel):
    selected_meal: str
    place_name: str
    user_time: str
    userId: str = 99
    payNow: bool = False
    orderId: Optional[str] = None
    paymentId: Optional[str] = None
    userPayNow: Optional[str] = "No"
@app.post("/agent_book")
def book_meal(request: BookingRequest):
    # Access the request data as attributes
    selected_meal = request.selected_meal.lower()  # Convert to lowercase for consistency
    place_name = request.place_name
    user_time = request.user_time
    userId = request.userId if request.userId else 99
    payNow = request.payNow
    userPayNow = request.userPayNow if request.userPayNow else "No"
    order_id = request.orderId if request.orderId  else ""
    payment_id = request.paymentId if request.paymentId else ""
    
    
    # Check if a place is open at a given time, including midnight cases.

    """Retrieve place details"""
    details = get_place_details_by_name(place_name)
    if not details:
        store_chat_in_redis(userId, selected_meal, f"Sorry, I couldn't find details for {place_name}.")
        return {"response": f"Sorry, I couldn't find details for {place_name}."}

    # Convert times from string to datetime.time objects
    opening = datetime.strptime(details["opening_time"], "%H:%M:%S").time()
    closing = datetime.strptime(details["closing_time"], "%H:%M:%S").time()
    user_time = datetime.strptime(user_time, "%H:%M:%S").time()
    category = details["category"]

    # Extract meal-specific timings (if available)
    meal_times = {
        "brunch": {
            "open": datetime.strptime(details["brunch_open_time"], "%H:%M:%S").time() if "brunch_open_time" in details else None,
            "close": datetime.strptime(details["brunch_close_time"], "%H:%M:%S").time() if "brunch_close_time" in details else None,
        },
        "lunch": {
            "open": datetime.strptime(details["lunch_open_time"], "%H:%M:%S").time() if "lunch_open_time" in details else None,
            "close": datetime.strptime(details["lunch_close_time"], "%H:%M:%S").time() if "lunch_close_time" in details else None,
        },
        "dinner": {
            "open": datetime.strptime(details["dinner_open_time"], "%H:%M:%S").time() if "dinner_open_time" in details else None,
            "close": datetime.strptime(details["dinner_close_time"], "%H:%M:%S").time() if "dinner_close_time" in details else None,
        },
    }

    cursor = conn.cursor(dictionary=True)
    query = ""

    # **Check if the selected meal has valid timing and falls within range**
    if selected_meal in meal_times:
        meal_open = meal_times[selected_meal]["open"]
        meal_close = meal_times[selected_meal]["close"]

        if meal_open and meal_close:
            if meal_open <= user_time <= meal_close:
                if(category == "club"):
                
                    if payNow == False:
                        return {"response":f"Awesome choice! For {category} booking, a payment of ₹500 is required to secure your spot. Want to pay now?","options":["Yes","No"],"placeName":place_name,"bookTime":user_time,'userId':userId,"category":category,'notPay':True,'selected_meal':selected_meal}
                    
                    if userPayNow == "No":
                        return {"response": f"Unfortunately, we cannot book your spot without payment. Please complete the payment to secure your reservation.", "options":["Yes","No","Exit"], "placeName": place_name, "bookTime": user_time, 'userId': userId, "category": category}
                    
                    if userPayNow == "Exit":
                        return {"response": f"Thanks for using our service! Have a great day!","placeName":place_name,"bookTime":user_time,'userId':userId,"category":category}
                    
                
                query = f"""
                        INSERT INTO book_{category}s (place_name, booking_time, user_id, meal_type,order_id,payment_id)
                        VALUES (%s, %s, %s, %s,%s,%s)
                        """
            else:
                store_chat_in_redis(userId, selected_meal, f"Sorry, {place_name} serves {selected_meal} between {convert_to_ampm(meal_open)} and {convert_to_ampm(meal_close)}. 🍽️ Please select a different time.")
                return {"response": f"Sorry, {place_name} serves {selected_meal} between {convert_to_ampm(meal_open)} and {convert_to_ampm(meal_close)}. 🍽️ Please select a different time."}

    # **Regular Opening Hours Check (if no specific meal time is found)**
    elif opening <= closing:  # Normal case (same-day opening and closing)
        if opening <= user_time <= closing:
            if(category == "club"):
                if payNow == False:
                    return {"response":f"Awesome choice! For {category} booking, a payment of ₹500 is required to secure your spot. Want to pay now?","options":["Yes","No"],"placeName":place_name,"bookTime":user_time,'userId':userId,"category":category,'notPay':True,'selected_meal':selected_meal}
                
                if userPayNow == "No":
                        return {"response": f"Unfortunately, we cannot book your spot without payment. Please complete the payment to secure your reservation.", "options":["Yes","No","Exit"], "placeName": place_name, "bookTime": user_time, 'userId': userId, "category": category,'selected_meal':selected_meal}
                elif userPayNow == "Exit":
                    return {"response": f"Thanks for using our service! Have a great day!","placeName":place_name,"bookTime":user_time,'userId':userId,"category":category}
                    
                    
            query = f"""
                    INSERT INTO book_{category}s (place_name, booking_time, user_id, meal_type,order_id,payment_id)
                    VALUES (%s, %s, %s, %s,%s, %s)
                    """
        else:
            store_chat_in_redis(userId, selected_meal, f"Sorry, {place_name} is closed at {convert_to_ampm(closing)}. 😔")
            return {"response": f"Sorry, {place_name} is closed at {convert_to_ampm(closing)}. 😔"}

    else:  # Midnight case (e.g., opening at 9 PM and closing at 5 AM)
        if user_time >= opening or user_time < closing:
            if(category == "club"):
                if payNow == False:
                    return {"response":f"Awesome choice! For {category} booking, a payment of ₹500 is required to secure your spot. Want to pay now?","options":["Yes","No"],"placeName":place_name,"bookTime":user_time,'userId':userId,"category":category,'notPay':True,'selected_meal':selected_meal}
                
                if userPayNow == "No":
                        return {"response": f"Unfortunately, we cannot book your spot without payment. Please complete the payment to secure your reservation.", "options":["Yes","No","Exit"], "placeName": place_name, "bookTime": user_time, 'userId': userId, "category": category,'selected_meal':selected_meal}
                elif userPayNow == "Exit":
                    return {"response": f"Thanks for using our service! Have a great day!","placeName":place_name,"bookTime":user_time,'userId':userId,"category":category}
                    
            query = f"""
                    INSERT INTO book_{category}s (place_name, booking_time, user_id, meal_type,order_id,payment_id)
                    VALUES (%s, %s, %s, %s,%s, %s)
                    """
        else:
            store_chat_in_redis(userId, selected_meal, f"Sorry, {place_name} is closed at {convert_to_ampm(closing)}. 😔")
            return {"response": f"Sorry, {place_name} is closed at {convert_to_ampm(closing)}. 😔"}

    # Execute the booking query
    cursor.execute(query, (place_name, user_time, userId, selected_meal,order_id,payment_id))
    conn.commit()
    cursor.close()

    responseText = f"Your booking for **{place_name}** at **{user_time.strftime('%I:%M %p')}** "
    if payment_id:
        responseText += f"with payment id **{payment_id}** "
    responseText += f"has been successfully confirmed! Please arrive on time to ensure a smooth experience.If you need to cancel or change your booking, please let us know. Thank you for choosing {place_name}! 🎉"

    send_email('divyapbagul@gmail.com', 'Booking', responseText)
    store_chat_in_redis(userId, selected_meal, responseText)

    return {"response": responseText,"pyamentStatus":"success"}

class ChatRequest(BaseModel):
    userId: int
@app.get("/get_chat_history")
def get_chat_in_redis(request: ChatRequest):
    chat_history = get_chat_history(request.userId)
    return {"chatHistory": chat_history}

@app.get("/get_chat_history_db")
def get_chat_from_mysql(request: ChatRequest):
    userId = request.userId
    
    """Retrieve chat history from MySQL for a specific user"""
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT prompt, response, timestamp FROM chat_history WHERE user_id = %s ORDER BY timestamp DESC", (userId,))
    rows = cursor.fetchall()
    cursor.close()

    chat_history = [{"timestamp": row["timestamp"], "prompt": row["prompt"], "response": row["response"]} for row in rows]
    return chat_history

@app.get("/add_chat_history_db")
def get_chat_from_mysql(request: ChatRequest):
    userId = request.userId
    return move_all_chats_to_mysql(userId)

client = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY_ID")
                               , os.getenv("RAZORPAY_SECRET")))
@app.post("/create-order")
def create_order():
    order_data = {
        "amount": 10000,  # in paise
        "currency": "INR",
        "payment_capture": 1
    }
    order = client.order.create(data=order_data)
    return {"order_id": order["id"]}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)