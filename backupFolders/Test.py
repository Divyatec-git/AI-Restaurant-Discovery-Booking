# from transformers import pipeline

# # Text generation pipeline
# generator = pipeline("text-generation", model="gpt2")
# result = generator("Tell the jungle story", max_length=50, num_return_sequences=1)

# print(result[0]["generated_text"])

# not working below code for stable diffusion
# from diffusers import StableDiffusionPipeline
# import torch

# model_id = "runwayml/stable-diffusion-v1-5"
# pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=torch.float16)
# pipe = pipe.to("cuda")

# # Generate image from text prompt
# image = pipe("A futuristic city at sunset").images[0]
# image.save("output.png")

# from faker import Faker

# fake = Faker()

# # # Generate random data
# # print(fake.name())           # Random name
# # print(fake.address())        # Random address
# # print(fake.text())           # Random paragraph

# # Generate topic-specific data
# for _ in range(5):
#     print(fake.job())        # Random job title
#     print(fake.company())    # Random company name


# import spacy

# # Load a medium-sized model for better accuracy
# nlp = spacy.load("en_core_web_md")  

# # Define sample intent categories with example phrases
# INTENT_EXAMPLES = {
#     "greeting": ["hello", "hi there", "hey", "good morning"],
#     "list_places": ["show me restaurants", "list clubs", "find dining places"],
#     "check_availability": ["is this place open?", "check if XYZ is available", "what are the timings?"],
#     "book_place": ["I want to book a table", "make a reservation", "reserve a spot"],
#     "get_details": ["tell me about this place", "give me more info on XYZ"]
# }

# def classify_intent_with_similarity(user_prompt):
#     """
#     Uses spaCy's vector similarity to classify user input into the closest intent category.
#     """
#     user_doc = nlp(user_prompt.lower())

#     best_intent = "fallback"  # Default intent if no match found
#     best_score = 0.0

#     for intent, examples in INTENT_EXAMPLES.items():
#         for example in examples:
#             similarity = user_doc.similarity(nlp(example))
#             if similarity > best_score:  # Find the closest matching intent
#                 best_intent = intent
#                 best_score = similarity

#     return best_intent if best_score > 0.6 else "fallback"  # Confidence threshold

# # Example Usage
# user_prompts = [
#     "Hey, how are you?",                  # Should detect "greeting"
#     "Can I book a spot for tomorrow?",    # Should detect "book_place"
#     "Tell me more about this restaurant", # Should detect "get_details"
#     "Is this restaurant open now?",       # Should detect "check_availability"
#     "List some good cafes nearby"         # Should detect "list_places"
# ]

# for prompt in user_prompts:
#     detected_intent = classify_intent_with_similarity(prompt)
#     print(f"User Input: {prompt}")
#     print(f"Detected Intent: {detected_intent}\n")


from fuzzywuzzy import process
import re

INTENT_EXAMPLES = {
    "greeting": ["hello", "hi there", "hey", "good morning"],
    "list_places": ["show me restaurants", "list clubs", "find dining places"],
    "check_availability": ["is this place open?", "check if XYZ is available", "what are the timings?"],
    "book_place": ["I want to book a table", "make a reservation", "reserve a spot", "I want to book a table at XYZ", "book my table at XYZ", "book table"],
    "get_details": ["tell me about this place", "give me more info on XYZ", "give me details about xyz", "what about this place xyz", "tell me about", "what is", "give me details on", "Provide a detail", "provide details"]
}

# Intent Priority Order (Higher Index = Higher Priority)
INTENT_PRIORITY = ["greeting", "list_places", "check_availability", "get_details", "book_place"]

# Keywords for early detection
INTENT_KEYWORDS = {
    "greeting": ["hello", "hi", "hey", "morning"],
    "list_places": ["show", "list", "find", "places", "restaurants", "clubs", "dining"],
    "check_availability": ["open", "available", "timings", "hours", "closed", "accepting customers"],
    "book_place": ["book", "reservation", "reserve", "schedule"],
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

# Example usage
# user_inputs = [
#     "Can you check if this restaurant is available?",  # check_availability
#     "Could you verify if this place is accepting customers?",  # check_availability (via fuzzy match)
#     "I need to schedule a dinner for two",  # book_place
#     "Give me information about this spot",  # get_details
#     "could you book table for this clubs"  # greeting
# ]
# user_input  = input(" ")

# print(f"User Input: {user_input}")
# print(f"Detected Intent: {detect_intent(user_input)}")
# for user_input in user_inputs:
#     print(f"User Input: {user_input}")
#     print(f"Detected Intent: {detect_intent(user_input)}")
#     print("-" * 40)


import requests

GOOGLE_API_KEY = 'AIzaSyCWtfmsWky-D7dDEZXiZNgGqQ6Ph77tbzI'

def get_restaurants_in_maninagar():
    """Fetch all restaurants in Maninagar, Ahmedabad using Google Places API"""
    base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    
    params = {
        "query": "restaurants in Maninagar, Ahmedabad",
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
            # Add token and wait a bit before next call (Google requires a small delay)
            import time
            time.sleep(2)  # Google recommends 2-second delay before using next_page_token
            params["pagetoken"] = next_page_token
        else:
            break

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



restaurants = get_restaurants_in_maninagar()

for r in restaurants:
    print(r['name'], '-', r['address'] + '\n')