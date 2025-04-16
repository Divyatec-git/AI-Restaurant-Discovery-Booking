import google.generativeai as genai
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import mysql.connector
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import time

# ✅ Configure Gemini API Key
genai.configure(api_key=os.getenv("GENAI_API_KEY"))
api_key = os.getenv("GENAI_API_KEY")
class BookingRequest(BaseModel):
    selected_meal: str
    place_name: str
    user_time: str
    userId: int = 0
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)
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

def book_meal(request: BookingRequest):
    # Access the request data as attributes
    selected_meal = request.selected_meal
    place_name = request.place_name
    user_time = request.user_time
    userId = request.userId if request.userId else 0
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
    mealType = selected_meal
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
    # send_email('divyapbagul@gmail.com', 'Booking', f"🎉 Your booking for **{place_name}** at **{user_time.strftime('%I:%M %p')}** has been successfully confirmed! We will make sure to reserve a table for you at that time. Please arrive on time to ensure a smooth experience. If you need to cancel or change your booking, please let us know as soon as possible. Thank you for choosing {place_name}! 🎉")
    return {"response": f"🎉 Your booking for **{place_name}** at **{user_time.strftime('%I:%M %p')}** has been successfully confirmed! We will make sure to reserve a table for you at that time. Please arrive on time to ensure a smooth experience. If you need to cancel or change your booking, please let us know as soon as possible. Thank you for choosing {place_name}! 🎉"}


# ✅ Restaurant Data with Timings
# restaurant_data = {
#     "The Grand Thakar": {"cuisine": "Gujarati Thali", "lunch": "11:00-15:30", "dinner": "19:00-23:00","area":"maninagar"},
#     "Kabir Restaurant": {"cuisine": "Indian, Mughlai", "lunch": "11:00-15:30", "dinner": "18:30-23:00","area":"maninagar"},
#     "Upper Crust Bakery": {"cuisine": "Bakery, Cafe", "brunch": "09:30-14:00", "dinner": "18:00-22:30","area":"prahadnagar"},
#     "Jassi De Parathe": {"cuisine": "North Indian", "lunch": "11:00-16:00", "dinner": "18:00-23:00","area":"ITC"},
#     "Real Paprika": {"cuisine": "Italian, Mexican", "lunch": "11:00-15:00", "dinner": "18:30-22:45","area":"syamal"},
# }

def fetch_restaurants_and_clubs():
    # conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT id, name, 'restaurant' AS category, area, lunch_time, dinner_time, area,brunch_time,opening_time,closing_time FROM restaurants 
        UNION 
        SELECT id, name, 'club' AS category, NULL AS area, NULL AS lunch_time, NULL AS dinner_time,NULL AS brunch_time,NULL AS opening_time,NULL AS closing_time, area FROM clubs
    """
    cursor.execute(query)
    results = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return results
# ✅ Create AI-powered Restaurant Booking Assistant
def create_restaurant_agent():
    # restaurant_list = "\n".join([
    #     f"- {name}: {data['cuisine']} (Timings: {', '.join([f'{k}: {v}' for k, v in data.items() if k != 'cuisine'])})" 
    #     for name, data in restaurant_data.items()
    # ])
    places = fetch_restaurants_and_clubs()
    restaurant_list = "\n".join([
        f"- {place['name']} ({place['category']}, {place.get('area', 'N/A')}, Area: {place['area']}, Timings: {place.get('lunch', 'N/A')} - {place.get('dinner', 'N/A')})"
        for place in places
    ])

    
    system_prompt = f"""
        You are an AI-powered restaurant booking assistant.
        - List restaurants based on user input (area, opening hours,closing hours,brunch,lunch,dinner, meal type).
        - Check if the restaurant is open at the requested time.
        - Collect details like restaurant name, date, and time before confirming a booking.
        - Ensure the booking is only for restaurants that are open at the requested time.
        -also find  restaurant in my list of restaurant outside of my list of restaurant locations give message we are not join that restaurant
        - if user want to book , reservation, kind thing want  then call my funcion  for booking - 
        Available Restaurants:
        -if user want to book, reservation, kind thing want then give them option book brunch, dinner, lunch and options should be in options key like this, but user want to ask time avaiablity  thne no need to add optins
        response:"Yes it is open or any meesage What Want to book Brunch , lunch or dinner ?",
        options:["brunch","lunch","dinner"],
        - and  if first time user add place name so add placeName key and return valuedo we can use for further like if user prompt - The Grand Thakar is available at 9 PM and thne user promts book it thne we need to book or give options for The Grand Thakar.
        - "book_meal" function is for booking table 
        it take arguments selected_meal meand it ill from optiins brunch , lunch , dinners
        place_name it is restaurant name 
        user_time - users time hen he want to book if can not find time  in promt thne ask for  time 
        userId it will be user id which you get other wise set 0

        {restaurant_list}
    """

    model = genai.GenerativeModel("gemini-2.0-flash")

    def agent(user_input):
        # messages = [
        #     {"role": "system", "content": system_prompt},
        #     {"role": "user", "content": user_input}
        # ]
        response = model.generate_content([system_prompt, user_input])  # ✅ Correct format

        # response = model.generate_content(messages)
        return response.text

    return agent

# ✅ Initialize FastAPI App
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to ["http://localhost:3000"] for security
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)
booking_agent = create_restaurant_agent()

# ✅ Define API Request Model
class BookingRequest(BaseModel):
    prompt: str

# ✅ Booking Endpoint
@app.post("/book")
async def book_restaurant(request: BookingRequest):
    """Handles restaurant booking requests via AI."""
    try:
        response = booking_agent(request.prompt)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Run FastAPI Server 
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
 