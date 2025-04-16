import google.generativeai as genai
import os
import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Configure your Gemini API key
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Define restaurant list and their timings
restaurant_data = {
    "The Grand Thakar": {"cuisine": "Gujarati Thali", "lunch": "11:00-15:30", "dinner": "19:00-23:00"},
    "Kabir Restaurant": {"cuisine": "Indian, Mughlai", "lunch": "11:00-15:30", "dinner": "18:30-23:00"},
    "Upper Crust Bakery": {"cuisine": "Bakery, Cafe", "brunch": "09:30-14:00", "dinner": "18:00-22:30"},
    "Jassi De Parathe": {"cuisine": "North Indian", "lunch": "11:00-16:00", "dinner": "18:00-23:00"},
    "Real Paprika": {"cuisine": "Italian, Mexican", "lunch": "11:00-15:00", "dinner": "18:30-22:45"},
}

def create_restaurant_agent():
    """Creates an AI restaurant booking assistant using Gemini."""
    
    restaurant_list = "\n".join([f"- {name}: ({data['cuisine']}), Timings: {', '.join([f'{k}: {v}' for k, v in data.items() if k != 'cuisine'])}" for name, data in restaurant_data.items()])
    
    system_prompt = {
        "role": "system",
        "content": f"""
        You are an AI-powered restaurant booking assistant. Your tasks include:
        - Listing restaurants based on the user's specified area and meal type (brunch, lunch, dinner).
        - Checking the availability of a restaurant based on its operational hours.
        - Automatically processing bookings by collecting the user's date, time, and restaurant choice.
        - Ensuring the selected restaurant is open during the requested time before confirming the booking.

        Available Restaurants:
        {restaurant_list}
        """
    }

    model = genai.GenerativeModel("gemini-pro")
    chat = model.start_chat(history=[system_prompt])

    def agent(user_input):
        messages = chat.history + [{"role": "user", "parts": [user_input]}]
        response = chat.send_message(user_input)
        return response.text

    return agent

app = FastAPI()
booking_agent = create_restaurant_agent()

class BookingRequest(BaseModel):
    prompt: str

@app.post("/book")
async def book_restaurant(request: BookingRequest):
    """API endpoint to book a restaurant."""
    try:
        response = booking_agent(request.prompt)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)