import dateparser
from datetime import datetime, time,timedelta  # Ensure 'time' is imported
import os,re,requests
import mysql.connector
from dotenv import load_dotenv
import google.generativeai as genai
from whatsup import send_whatsapp_notification 
from faker import Faker
import json

fake = Faker()

load_dotenv()
from collections import defaultdict
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
# Function to convert 24-hour format to 12-hour format
def convert_to_ampm(time_str):
    try:
        if isinstance(time_str, time):
            time_str = time_str.strftime("%H:%M:%S")
        else:
            time_str = time_str  # Assume it's already a string
        # Check if the time is already in AM/PM format
        if "AM" in time_str or "PM" in time_str:
            return time_str  # Already converted
        
        # Convert from 24-hour format to 12-hour AM/PM format
        return datetime.strptime(time_str, "%H:%M:%S").strftime("%I:%M %p")
    
    except ValueError as e:
        print(f"Error: {e}")
        return None  # Return None if conversion fails

def fetch_places(place = None):
    """ Fetch both restaurants and clubs in the database """
    cursor = conn.cursor(dictionary=True)
    if place is not None:
        query = f"""
            SELECT id, name, '{place}' AS category FROM {place}s 
        """
        
    else:
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
    query = """SELECT *, 'restaurant' AS category 
               FROM restaurants WHERE name LIKE %s 
               UNION 
               SELECT *, 'club' AS category 
               FROM clubs WHERE name LIKE %s"""
   
    cursor.execute(query, (f"%{place_name}%", f"%{place_name}%"))
    result = cursor.fetchone()
    cursor.close()

    # Convert time fields to strings
    if result:
        result["opening_time"] = str(result["opening_time"])
        result["closing_time"] = str(result["closing_time"])
        result["brunch_open_time"] = str(result["brunch_open_time"])
        result["lunch_open_time"] = str(result["lunch_open_time"])
        result["dinner_open_time"] = str(result["dinner_open_time"])
        result["brunch_close_time"] = str(result["brunch_close_time"])
        result["lunch_close_time"] = str(result["lunch_close_time"])
        result["dinner_close_time"] = str(result["dinner_close_time"])

    return result

def check_availability(place_name, user_time,userId):
    """Check if a place is open at a given time, including midnight cases."""
    details = get_place_details_by_name(place_name)
    if not details:
        return  {"response":f"Sorry, I couldn't find details for {place_name}.","placeName":place_name,"bookTime":user_time,'userId':userId}

   
    opening = datetime.strptime(details["opening_time"], "%H:%M:%S").time()
    closing = datetime.strptime(details["closing_time"], "%H:%M:%S").time()
    user_time = datetime.strptime(user_time, "%H:%M:%S").time()
    
    

    # Handle normal opening-closing case (same day)
    if opening <= closing:
        if opening <= user_time <= closing:
            return {"response":f"✅ {details['name']} is open at {convert_to_ampm(user_time)}. The Brunch time is {convert_to_ampm(details['brunch_open_time'])}, lunch time is {convert_to_ampm(details['lunch_open_time'])}  and Dinner will be {convert_to_ampm(details['dinner_open_time'])}","placeName":place_name,"bookTime":user_time,'userId':userId}
        else:
            return  {"response":f"❌ {details['name']} is closed at {user_time}.","placeName":place_name,"bookTime":user_time,'userId':userId}

    # Handle midnight case (e.g., opening at 9 PM and closing at 5 AM)
    else:
        if user_time >= opening or user_time < closing:  # Fixed condition
            return {"response":f"✅ {details['name']} is open at {convert_to_ampm(user_time)}. The Brunch time is {convert_to_ampm(details['brunch_open_time'])}, lunch time is {convert_to_ampm(details['lunch_open_time'])}  and Dinner will be {convert_to_ampm(details['dinner_open_time'])}","placeName":place_name,"bookTime":user_time,'userId':userId}
        else:
            return {"response":f"❌ {details['name']} is closed at {user_time}.","placeName":place_name,"bookTime":user_time,'userId':userId}

def extract_place_name(prompt):
    """Extracts the place name from a natural language prompt."""
    # Remove common words that aren't part of the place name
    stopwords = {"give", "me", "details", "for", "about", "information", "on", "a","is", "in",'i','want','go','to','the','need','of'}
    words = [word for word in prompt.split() if word not in stopwords]

    # Join remaining words (assume it's the place name)
    place_name = " ".join(words).title()  # Capitalize words to match DB
    
    return place_name if place_name else None

def find_place_in_db(place_name):
    """Check if the extracted place name exists in restaurants or clubs table."""
    cursor = conn.cursor(dictionary=True)
    
    query = """
        SELECT id, name, 'restaurant' AS category FROM restaurants WHERE name = %s
        UNION 
        SELECT id, name, 'club' AS category FROM clubs WHERE name = %s
    """
    
    cursor.execute(query, (place_name, place_name))
    results = cursor.fetchall()
    cursor.close()
    
    return results  # List of matched places
def capitalize_first_letters(text):
  """Capitalizes the first letter of each word in a string."""
  words = text.split()
  capitalized_words = [word.capitalize() for word in words]
  return " ".join(capitalized_words)

def extract_place_name_gemini(prompt,max_retries=3, wait_time=60):
    """Use Google Gemini API to extract a potential place name"""
    model = genai.GenerativeModel("gemini-2.0-flash")
    
    for attempt in range(max_retries):
        try:
            # improved_prompt = f"""
            #     From the following text, identify the name of a restaurant or club. If a name is present, return it.'
            #     If a name is present, return only the name. 
            #     If no name is present, return only 'None' with no extra text.

            #     Text: {prompt}

            #     Examples:
            #     Text: 'Visit The Blue Moon Cafe for dinner.'
            #     Name: The Blue Moon Cafe

            #     Text: 'Let's go to Club Zenith tonight.'
            #     Name: Club Zenith

            #     Text: 'I need details about Night Owls.'
            #     Name:Night Owls

            #     Text: 'give me details about Night Owls'
            #     Name: Night Owls
            #     """
            improved_prompt = f"""
                You are an expert at identifying restaurant and club names from messy or informal text.
                and restaurant and club most of the belongs to dubai coutry so you can identify places from dubai

                Extract only the name of the restaurant or club mentioned in the text. If a name is present, return only the name — no quotes, no extra text. If none is found, return exactly: None

                Here are some examples:

                Text: 'Visit The Blue Moon Cafe for dinner.'
                Name: The Blue Moon Cafe

                Text: 'Let's go to Club Zenith tonight.'
                Name: Club Zenith

                Text: 'I need details about Night Owls.'
                Name: Night Owls

                Text: 'give me details about Night Owls'
                Name: Night Owls

                Text: 'Dinner at The Restaurant at Address in Dubai'
                Name: The Restaurant at Address

                Text: 'We had food in Dubai'
                Name: None

                Now analyze this:
                Text: {prompt}
                Name:"""

            
            response = model.generate_content(improved_prompt)
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
        Extract the time from the following text in 24-hour format (HH:MM:SS):

        Convert AM/PM times to 24-hour format correctly.
        If the time is in 24-hour format, return it without any modifications.
        If no time is found, return only "None".
        Ensure that standalone times like "11 PM" or "3 AM" are correctly converted.
        The output should only contain the extracted time, not multiple times exist. No extra text or symbols.
        
        Example Inputs & Expected Outputs:
        "Check availability at 6:30 PM" → "18:30:00"
        "I want to visit at noon" → "12:00:00"
        "Is it open at 5 AM?" → "05:00:00"
        "Can I visit at midnight?" → "00:00:00"
        "Let's go now" → "None"
        
        "What about 11 PM?" → "23:00:00"

        "if it is 10 PM then it should be 22:00:00 and if it is 10 AM then it should be 10:00:00" → "22:00:00, 10:00:00"
        Now extract the time from:
        "{prompt}"
    """

   
    response = model.generate_content(prompt_text)
    extracted_time = response.text.strip().replace('"', '')  # Remove extra quotes
    # print("Extracted time:",extracted_time)
    if extracted_time == "none":
        return None  # No valid time found

    # Try multiple time formats
    for fmt in ["%H:%M:%S", "%H:%M", "%I %p", "%I:%M %p"]:  # Covers 24-hour and 12-hour formats
        try:
            time_obj = datetime.strptime(extracted_time, fmt).time()
            
            return time_obj.strftime("%H:%M:%S")  # Standardize format
        except ValueError:
            continue  # Try next format

    
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

def gemini_generate_general_response(user_prompt):
    model = genai.GenerativeModel("gemini-2.0-flash")
    
    response = model.generate_content(f"""
     You are a helpful restaurant and club booking assistant. 
    - If a user asks for "details" but doesn't specify, ask them whether they need restaurant or club details.
    - If they mention a restaurant or club name, guide them on how to find its details without giving direct answers. 
    - If they ask about something unrelated (flights, hotels, etc.), politely tell them you specialize in restaurants, clubs, and availability.
    -if there is any restaurant or club name in the prompt thne say i dont have inforamtion for this etc.
    -it is only for restaurant and clubs not any other services
    
    - If the user does not provide a valid place name or leaves it blank, thne return a friendly message guiding them to find details.
    - If the user provides a restaurant or club name, return a friendly message guiding them to find details.
    

    User: {user_prompt}
    """)
    
    return response.text
def extract_meal_type(prompt):
    meal_keywords = ['brunch', 'lunch', 'dinner']
    
    # Use regex to find the first occurrence of a meal type in the prompt
    match = re.search(r'\b(brunch|lunch|dinner)\b', prompt, re.IGNORECASE)
    
    if match:
        return match.group(1).lower()  # Return the matched meal type in lowercase
    else:
        return None  # Return None if no meal type is found
   # In-memory dictionary to store user bookings

def book_place(place_name, user_time,userId,prompt):
    
    """Insert fake data into restaurants and clubs tables"""
    cursor = conn.cursor(dictionary=True)
    """Check if a place is open at a given time, including midnight cases."""
    details = get_place_details_by_name(place_name)
    if not details:
        return {"response":f"Sorry, I couldn't find details for {place_name}.","placeName":place_name,"bookTime":user_time,'userId':userId}

    
    opening = datetime.strptime(details["opening_time"], "%H:%M:%S").time()
    closing = datetime.strptime(details["closing_time"], "%H:%M:%S").time()
    user_time = datetime.strptime(user_time, "%H:%M:%S").time()
    category =  details["category"]
    
    query = ""
    mealType = None
    # Handle normal opening-closing case (same day)
    if opening <= closing:
        if opening <= user_time <= closing:
            
            
            return {"response":"What Want to book Brunch , lunch or dinner ?","options":["brunch","lunch","dinner"],"placeName":place_name,"bookTime":user_time,'userId':userId,"category":category}
        else:
           
            return {"response":f"Sorry, {place_name} is closed at {convert_to_ampm(closing)}. 😔 But don't worry, we'll make sure to book your table for another time. 📅 Just let us know when you're free! 😊"}
   
    # Handle midnight case (e.g., opening at 9 PM and closing at 5 AM)
    else:
        
        if user_time >= opening or user_time < closing:  # Fixed condition
            return {"response":"What Want to book Brunch , lunch or dinner ?","options":["brunch","lunch","dinner"],"placeName":place_name,"bookTime":user_time,'userId':userId,"category":category} 
        else:
           
            return {"response":f"Sorry, {place_name} is closed at {convert_to_ampm(closing)}. 😔 But don't worry, we'll make sure to book your table for another time. 📅 Just let us know when you're free! 😊"}






# -------------------------------- Below code for data find from google place api -----------------------------------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Function to get place ID from database
def get_place_id_from_db(restaurant_name, location="Dubai"):
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        cursor = conn.cursor(dictionary=True)
        
        query = "SELECT place_id FROM google_restaurants WHERE name LIKE %s"
        search_term = f"%{restaurant_name}%"  # wrap with % for partial match
        cursor.execute(query, (search_term,))
        result = cursor.fetchone()
       
        return result['place_id'] if result else None
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None
    finally:
        try:
            cursor.close()
        except:
            pass
        try:
            conn.close()
        except:
            pass

# Function to save place ID to database
def save_place_id_to_db(name, place_id, location):
   
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        cursor = conn.cursor(dictionary=True)
       
       # Check if the place_id already exists
        check_query = "SELECT id FROM google_restaurants WHERE place_id = %s"
        cursor.execute(check_query, (place_id,))
        existing = cursor.fetchone()

        if not existing:
            insert_query = "INSERT INTO google_restaurants (name, place_id, location) VALUES (%s, %s, %s)"
            cursor.execute(insert_query, (name, place_id, location))
            conn.commit()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        try:
            cursor.close()
        except:
            pass
        try:
            conn.close()
        except:
            pass


# extract cuision type / name from prompt  
def extract_cuisine_type(prompt):
    known_cuisines = [
        # Common Global Cuisines
        "italian", "chinese", "indian", "thai", "mexican", "japanese", "french", "greek", "lebanese", "korean",
        "american", "spanish", "turkish", "vietnamese", "indonesian", "malaysian", "german", "ethiopian", "persian",
        "brazilian", "argentinian", "portuguese", "moroccan", "russian", "afghan", "nepalese", "sri lankan", "pakistani",
        "caribbean", "jamaican", "cuban", "hawaiian", "tibetan", "egyptian", "syrian", "iraqi", "israeli", "palestinian",
        "filipino", "singaporean", "taiwanese", "scandinavian", "swedish", "norwegian", "danish", "finnish",
        "australian", "new zealand", "hungarian", "czech", "polish", "romanian", "bulgarian", "ukrainian",
        "georgian", "armenian", "bosnian", "serbian", "croatian", "slovak", "slovenian", "albanian",

        # Regional Indian Cuisines (🇮🇳)
        "punjabi", "south indian", "gujarati", "bengali", "rajasthani", "maharashtrian", "kashmiri", "goan",
        "kerala", "tamil", "telugu", "andhra", "malabari", "udupi", "mangalorean", "oriya", "assamese", "naga", "northeast indian",

        # Others / Styles
        "mediterranean", "european", "asian", "middle eastern", "continental", "fusion", "halal", "vegetarian",
        "vegan", "gluten-free", "healthy", "organic", "bbq", "grill", "seafood", "sushi", "ramen", "noodle", "tapas",
        "bistro", "brunch", "fast food", "street food", "fine dining", "buffet", "cafe", "steakhouse", "deli",
        "dessert", "bakery", "pizzeria", "burger", "sandwich", "fried chicken", "shawarma", "kebab", "dumpling",
        "hot pot", "curry house"
    ]

    
    prompt_lower = prompt.lower()
    
    for cuisine in known_cuisines:
        if cuisine in prompt_lower:
            return cuisine.capitalize()  # Optional formatting
    
    return None

# Function to fetch restaurants from Google Places API
def get_restaurants(place_name,cuisine=None):
    
    print(cuisine,'cuision',place_name)
    """Fetch all restaurants for the given place name using Google Places API"""
    base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    
    location = 'Dubai' if place_name == 'None' or 'None' in place_name else place_name
    
    # Build query based on whether cuisine_type is provided
    if cuisine:
        query = f"{cuisine} restaurants in {location}"
    else:
        query = f"restaurants in {location}"
    
    params = {
        "query": query,
        "key": GOOGLE_API_KEY
    }
    

    all_results = []
    while True:
        response = requests.get(base_url, params=params)
        data = response.json()

        if data.get("results"):
            all_results.extend(data["results"])
        
        # Check if there's another page of results
        next_page_token = data.get("next_page_token")
        if next_page_token:
            import time
            time.sleep(2)  # Google requires delay before next page call
            params["pagetoken"] = next_page_token
        else:
            break
    for place in all_results:
        save_place_id_to_db(place.get("name"),place.get("place_id"),place_name)
    
   

    return [
        {
            "name": place.get("name"),
            "address": place.get("formatted_address"),
            "rating": place.get("rating"),
            "location": place.get("geometry", {}).get("location"),
            "types": place.get("types")
        }
        for place in all_results
    ]

# Function to format places for chat
def format_places_for_chat(places):
    grouped = defaultdict(list)

    for place in places:
        name = place.get("name")
        address = place.get("address")
        rating = place.get("rating", "N/A")
        types = place.get("types", [])

        # Categorize by type (basic logic)
        if "restaurant" in types:
            category = "🍽️ Restaurant"
        elif "cafe" in types:
            category = "☕ Cafe"
        elif "bar" in types or "night_club" in types:
            category = "🍸 Club"
        else:
            category = "📍 Other"

        grouped[category].append(f"• **{name}**\n  📍 {address}\n  ⭐ Rating: {rating}")

    # Final formatted message
    message = ""
    for category, items in grouped.items():
        message += f"__{category}__\n"
        message += "\n\n".join(items[:15])  # Show only top 5 from each category
        message += "\n\n"

    return message

# Function to fetch detailed information for a specific restaurant
def get_restaurant_details(restaurant_name, location="Dubai"):
   
    """Fetch detailed information for a specific restaurant using Google Places API"""
    location = 'Dubai' if location == 'None' or 'None' in location else location
    place_id = get_place_id_from_db(restaurant_name, location)
    # print(place_id,'*-'*10,restaurant_name,location)
  
    # Step 2: Call Google API if not found in DB
    if not place_id or place_id == "None":
        
        # Step 1: Search the restaurant by name (Text Search)
        search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        search_params = {
            "query": f"{restaurant_name}, {location}",
            "key": GOOGLE_API_KEY
        }

        search_response = requests.get(search_url, params=search_params)
        search_data = search_response.json()

        if not search_data.get("results"):
            return {"error": "Restaurant not found."}

        # Get the place_id of the first result
        place_id = search_data["results"][0]["place_id"]
        save_place_id_to_db(search_data["results"][0]["name"], place_id, location)
        print("again call function api",restaurant_name)
        if not place_id:
            return {"error": "Failed to fetch place_id."}
        
   
    # Step 2: Use Place Details API to fetch full details
    details_url = "https://maps.googleapis.com/maps/api/place/details/json"
    details_params = {
        "place_id": place_id,
        "fields": "name,formatted_address,formatted_phone_number,rating,opening_hours,geometry,types,website,photos,reviews",
        "key": GOOGLE_API_KEY
    }

    details_response = requests.get(details_url, params=details_params)
    details_data = details_response.json()

    if details_data.get("status") != "OK":
        return {"error": "Failed to fetch restaurant details."}

    result = details_data.get("result", {})
    return {
        "name": result.get("name"),
        "address": result.get("formatted_address"),
        "phone": result.get("formatted_phone_number"),
        "rating": result.get("rating"),
        "location": result.get("geometry", {}).get("location"),
        "types": result.get("types"),
        "website": result.get("website"),
        "opening_hours": result.get("opening_hours", {}).get("weekday_text"),
        "reviews": result.get("reviews"),
    }

# Function to format the chat response for details data
def format_restaurant_chat_response(details: dict) -> str:
    if "error" in details:
        return f"❌ {details['error']}"
  
    if 'none' in details.get('name',"N/A").lower():
        return "😔 Sorry, I couldn't find any details for this restaurant. Please try searching again or providing more information."
       
    lines = [
        f"🍽️ **{details.get('name', 'N/A')}**",
        f"📍 Address: {details.get('address', 'N/A')}",
        f"📞 Phone: {details.get('phone', 'N/A')}",
        f"🌐 Website: {details.get('website', 'N/A')}",
        f"⭐ Rating: {details.get('rating', 'N/A')}",
        f"📌 Location: {details.get('location', {})}",
    ]

    # Add opening hours
    if details.get("opening_hours"):
        lines.append("⏰ Opening Hours:")
        for day in details["opening_hours"]:
            lines.append(f"   - {day}")

    # Add top review if available
    if details.get("reviews"):
        review = details["reviews"][0]
        author = review.get("author_name", "Someone")
        rating = review.get("rating", "N/A")
        text = review.get("text", "")
        lines.append("\n💬 Top Review:")
        lines.append(f"   - **{author}** rated it {rating}/5")
        lines.append(f"   - \"{text}\"")
    
    lines.append('\n\n\n Would you like to proceed with booking a table?')

    return "\n".join(lines)

# Function to extract city and area from a text using Google Gemini
def extract_city_area_gemini(prompt, max_retries=3, wait_time=60):
    """Use Google Gemini API to extract city and area from a text"""
    model = genai.GenerativeModel("gemini-2.0-flash")

    for attempt in range(max_retries):
        try:
            improved_prompt = f"""
                From the following user text, extract the location (city and/or area name only). Return in this exact format:

                City: <city_name or None>
                Area: <area_name or None>

                Do not include any extra text.

                Text: {prompt}
            """

            response = model.generate_content(improved_prompt)
            result_text = response.text.strip()

            # Parse the result into a dict
            lines = result_text.splitlines()
            city = area = None

            for line in lines:
                if line.lower().startswith("city:"):
                    city = line.split(":", 1)[1].strip()
                elif line.lower().startswith("area:"):
                    area = line.split(":", 1)[1].strip()

            return {"city": city, "area": area}

        except Exception as e:
            if "RateLimitError" in str(e):
                print(f"Rate limit reached. Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"Error: {e}")
                break

    return {"city": None, "area": None}

# Function to extract datetime from a text using Google Gemini
def extract_datetime_from_prompt(prompt):
    model = genai.GenerativeModel("gemini-2.0-flash")
    today = datetime.now().strftime("%Y-%m-%d")
    prompt_text = f"""
    From the following user input, extract the date and time (if available).

    - Output format: "YYYY-MM-DD HH:MM:SS" (if both available)
    - If only time is mentioned, return as: "HH:MM:SS"
    - If only date is mentioned, return as: "YYYY-MM-DD"
    - If neither found, return "None" and if only time not found then return text "time is None"
    - Handle fuzzy words like today, tomorrow, yesterday
    - Output only the extracted value, no explanation.
    - if this type of prompt  - book table for me in the market dubai at 6 PM 11 April then extact date and time and time not avaiable then consider return time none
    - if date available but time not avaiavle then return time is none
    - if the prompt refers to vague or general days like "this Saturday", "this Sunday", "any day", then always return the upcoming Saturday as the date, regardless of what's mentioned and it time not prensent then return text "time is None".
    - but note : when you return upcomming date date is not more then 2 month from today {today} Example: If user ask this sunday thne retune this upcooming sunday but not more then 2 month from today,2nd exaple if user want specific date from more then 2 month from today then return "DateTooFar"
    Example : book table in social house for this friday at 5 PM then  always return the upcoming friday or any mentioned day as the date,and if time is avaiable then return time also
    - xuz is open at 6 PM , 6 AM etc then give time and if date not mentioned then rturn current {today} date
    - Can you book Zuma for lunch at 1 PM? or Can you book Zuma for  today lunch at 1 PM?  then this type prompt alway work with {today} date

    Today is {today}.
    Now extract from:
    "{prompt}"
    """
    response = model.generate_content(prompt_text)
    result = response.text.strip().replace('"', '')
    return result if result.lower() != "none" else None

# Function to check if a user's time fits into a restaurant's daily schedule using Google Gemini
def check_if_user_time_in_schedule(schedule_list, user_datetime):
    
    model = genai.GenerativeModel("gemini-2.0-flash")
    today = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")

    # Format user datetime
    date_str = user_datetime.strftime("%Y-%m-%d")
    time_str = user_datetime.strftime("%H:%M:%S")
    day_name = user_datetime.strftime("%A")

    # Prepare schedule list string
    schedule_str = "\n".join(schedule_list)
   
    prompt_text = f"""
    You are a smart assistant checking if a user's time fits into a restaurant's daily schedule.

    Input:
    - Day: {day_name}
    - Date: {date_str}
    - Time: {time_str}
    - Schedule list:
    {schedule_str}

    Rules:
    - Compare the provided time with the timings on the matching day.
    - If the Day, Date, and Time are  previous date compared to the current date ({today}) and current time ({current_time}), return "pastTime" with no extra text.
    - The schedules may have different formats:
    - One slot: e.g., "Monday: 10:00 AM – 11:00 PM"
    - Two slots: e.g., "Monday: 11:30 AM – 3:00 PM, 6:00 PM – 1:00 AM"
    - 24-hour format: e.g., "10:00 – 23:00"
    - "24 hours" or "Open 24 hours"
    - If the user's provided time fits into the schedule for the specified day, return the date and time in 24-hour format.
    - If the time does not fit into the schedule, return "None" with no extra text.

    Output:
    - If the user's time fits, return the matching day and time in this format: {{"date": "{date_str}", "time": "{time_str}"}}
    - If the time does not fit, return "None" not in json.
    - If the time is from a previous date and time, return "pastTime".

    Example inputs:
    - Day: Monday
    - Date: 2025-04-14
    - Time: 13:00:00
    - Schedule list: ["Monday: 11:30 AM – 3:00 PM, 6:00 PM – 1:00 AM"]

    Now answer:
    """
    response = model.generate_content(prompt_text)
    result = response.text.strip()
    
    return result

# Function to check availability and booking proces using Google Gemini
def check_availability_google(restaurant_name, user_prompt, place_name="Dubai",book=False):
    datetime_string = extract_datetime_from_prompt(user_prompt)
    print(datetime_string,'datetime_string')
    if book == True:
        intent = "book_place"
    else:
        intent = "check_availability"

    if datetime_string is None:
        return {"response":  "📅 Please provide the date and time you're interested in? For example: *'Tomorrow at 7 PM'* so I can assist you better!","placeName":restaurant_name,'intent':intent}
    if 'time is None' in datetime_string:
        return {"response":  "🕒 Please provide the time you're interested in? For example: *'Tomorrow at 7 PM'* so I can assist you better!","placeName":restaurant_name,'intent':intent}
    if 'DateTooFar' in datetime_string:
        return {"response":  "📅 That date is a bit too far in the future — I can only help with bookings within the next **2 months** from today.\n\n","placeName":restaurant_name,'intent':intent}

    if not datetime_string:
        return {"response":  "😢 Couldn't extract a valid date or time from your input.\n\n"
        "📅 Could you please provide the date and time you’re interested in? For example: *'Tomorrow at 7 PM'*.","placeName":restaurant_name,'intent':intent}

    parsed_dt = dateparser.parse(datetime_string)
    if not parsed_dt:
        return {"response":  "😢 Failed to understand the date and time from your input.\n\n"
        "🕒 Could you please rephrase it? Try something like *'Friday at 7 PM'* or *'tomorrow evening'* so I can assist you better!","placeName":restaurant_name,'intent':intent}

    now = datetime.now()
    if parsed_dt < now:
        if not any(str(y) in user_prompt for y in range(2010, 2100)):
            parsed_dt = parsed_dt.replace(year=now.year)
            if parsed_dt < now:
                parsed_dt = parsed_dt.replace(year=now.year + 1)
        if parsed_dt < now:
            return {"response": f"⚠️ Oops! You asked for a time that's already gone.📅 Want to check availability for a future date or time instead? Let me know when you'd like to book!","placeName":restaurant_name,'intent':intent}

    # weekday = parsed_dt.strftime("%A")
    query_time = parsed_dt.time()
   
    weekday = parsed_dt.strftime("%A")
    weekday_for_hours = weekday  # Assume same day

    # If it's early morning (e.g., 1 AM), check previous day's hours instead
    if query_time < datetime.strptime("05:00 AM", "%I:%M %p").time():
         weekday_for_hours = (parsed_dt - timedelta(days=1)).strftime("%A")

    restaurant = get_restaurant_details(restaurant_name, place_name)

    if "error" in restaurant:
        return {"response":  f"❌ {restaurant['error']}\n\n"
        "😕 Something didn’t go as expected. If you're trying to book or check availability, feel free to try again or ask for help!","placeName":place_name,'intent':intent}

    hours = restaurant.get("opening_hours", [])
    if not hours:
        return {"response": f"❌ Couldn't fetch opening hours for **{restaurant['name'] if restaurant['name'].lower() != "none" else ""}**.\n\n"
        "This restaurant hasn't provided its opening and closing time with us, but we can assist you with any other details. — we can still help you make a booking or find more info. Just let us know!","placeName":place_name,'intent':intent}

    # matched_day = next((line for line in hours if line.lower().startswith(weekday.lower())), None)
    matched_day = next((line for line in hours if line.lower().startswith(weekday_for_hours.lower())), None)
    # print(hours,datetime_string,'-matched_day')

    if not matched_day:
        return {"response":  f"ℹ️ No opening hours found for **{weekday}**.\n\n"
        "🤔 It looks like we don’t have schedule info for that day. Want to try a different date or go ahead with a booking anyway?","placeName":restaurant['name'],'intent':intent}

    try:
        
        # Convert to datetime
        user_time = datetime.strptime(datetime_string, "%Y-%m-%d %H:%M:%S")
        check_timing_str = check_if_user_time_in_schedule(hours,user_time)
      

        if check_timing_str == 'None' or not check_timing_str:
            restaurant_details = get_restaurant_details(restaurant_name,place_name)
            placeDetails = format_restaurant_chat_response(restaurant_details)
        
            
                
            return {
                "response": (
                    f"❌ No, **{restaurant['name']}** is closed at **{query_time.strftime('%I:%M %p')}** on "
                    f"**{parsed_dt.strftime('%A, %d %B %Y')}**.\n\n Restaurants Deatils for finding best times \n {placeDetails}.\n\n"
                    "📅 But don't worry — we can help you find the next available time and book it for you. Just let us know when you'd like to go! 😊"
                ),
                "placeName": restaurant['name'],
                "intent": intent
            }
            
        if check_timing_str == 'pastTime':
            return {
                "response": f"⚠️ Oops! You asked for a time that's already gone.📅 Want to check availability for a future date or time instead? Let me know when you'd like to book!","placeName":restaurant_name,'intent':intent
            }
        
        
        # Clean string in case it contains formatting like ```json ... ```
        clean_str = check_timing_str.strip().replace("```json", "").replace("```", "").strip()

        # Convert string to dictionary
        check_timing = json.loads(clean_str)
        print(check_timing, 'check_timing')

        # Now it's safe to access keys
        date_str = check_timing["date"]
        time_str = check_timing["time"]

        # Combine into datetime
        datetime_str = f"{date_str} {time_str}"
        given_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")

        # Compare with current datetime
        if given_datetime < datetime.now():
            return {"response": f"⚠️ Oops! You asked for a time that's already gone.📅 Want to check availability for a future date or time instead? Let me know when you'd like to book!","placeName":restaurant_name,'intent':intent}
        else:
            if book == True:
                requestdata = {
                        "country_code":91,
                        "table_booking_recipient":7283947790,
                        "restaurant_name":"Puravida",
                        "venue_manager_name":fake.first_name(),
                        "booking_date":"2023-08-15",
                        "user_name":fake.first_name(),
                        "user_phone":"+91 7283947790",
                        "total_person":"2",
                        "user_email":"YVY8o@example.com"
                }
                conn = mysql.connector.connect(
                    host=os.getenv("DB_HOST"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    database=os.getenv("DB_NAME")
                )
                cursor = conn.cursor(dictionary=True)
                cursor = conn.cursor(dictionary=True)
                query = f"""
                    INSERT INTO book_from_google (place_name, booking_time, user_id, recipient_number)
                    VALUES (%s, %s, %s, %s)
                    """
                # Execute the booking query
                cursor.execute(query, (restaurant_name, given_datetime, 999,7283947790))
                conn.commit()
                cursor.close()
                send_whatsapp_notification(requestdata,'Restaurant')
                
                return {
                        "response": f"✅ 📨 Booking details sent! Our agent will contact you shortly to confirm everything and assist you further. Thanks for choosing us!"
                }
            else:
                return {
                     "response": 
                            f"✅ Yes, **{restaurant['name']}** is open at **{query_time.strftime('%I:%M %p')}** on "
                            f"**{parsed_dt.strftime('%A, %d %B %Y')}**.\n\n"
                            "🍽️ Would you like to make a reservation? We're all set to assist you with a quick and easy booking! 🚀","placeName":restaurant['name'],'intent':intent
                        
                    }

    except Exception as e:
        print(e)
        return {"response": f"⚠️ Oops! There was an error while checking the hours: {str(e)}\n\n"
                "😓 Something went wrong on our side. Please try again in a moment, or let us know if you'd like help with your booking!",'intent':intent}

# -------------------------------- Finish code for data find from google place api -----------------------------------------
