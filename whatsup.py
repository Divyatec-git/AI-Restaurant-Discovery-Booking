import os
import requests
import logging
from dotenv import load_dotenv
load_dotenv()
from faker import Faker

fake = Faker()


def send_whatsapp_notification(request, booking_type):
    try:
        payload = {
            "messaging_product": "whatsapp",
            "preview_url": False,
            "recipient_type": "individual",
            "to": f"{request['country_code']}{request['table_booking_recipient']}",
            "type": "template",
            "template": {
                "name": "puravida_restaurant_table_booking",
                "language": {
                    "code": "en_US"
                },
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": request['restaurant_name']},
                            {"type": "text", "text": request['venue_manager_name']},
                            {"type": "text", "text": request['booking_date']},
                            {"type": "text", "text": request['user_name']},
                            {"type": "text", "text": request['user_phone']},
                            {"type": "text", "text": request['total_person']},
                            {"type": "text", "text": booking_type},
                            {"type": "text", "text": request['user_email']}
                        ]
                    },
                    {
                        "type": "button",
                        "sub_type": "quick_reply",
                        "index": 0,
                        "parameters": [
                            {"type": "payload", "payload": "approve"}
                        ]
                    },
                    {
                        "type": "button",
                        "sub_type": "quick_reply",
                        "index": 1,
                        "parameters": [
                            {"type": "payload", "payload": "reject"}
                        ]
                    },
                    {
                        "type": "button",
                        "sub_type": "quick_reply",
                        "index": 2,
                        "parameters": [
                            {"type": "payload", "payload": "fully_booked"}
                        ]
                    }
                ]
            }
        }

        headers = {
            "Authorization": f"Bearer {os.getenv('WHATSAPP_ACCESS_TOKEN')}",
            "Content-Type": "application/json"
        }

        phone_id = os.getenv('WHATSAPP_PHONE_ID')
        url = f"https://graph.facebook.com/v22.0/{phone_id}/messages"

        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()

        return response.json()

    except requests.RequestException as e:
        logging.error(f"Exception caught while sending notification: {str(e)}")
        return {"error": "Failed to send notification. Please try again later."}, 500


# send_whatsapp_notification(requestdata,'Restaurant')