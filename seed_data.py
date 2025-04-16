import mysql.connector
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Connect to MySQL Database"""
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "agent")
    )
    return conn

def insert_fake_data():
    """Insert fake data into restaurants and clubs tables"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Insert sample restaurants
    restaurants = [
        ("Spice Junction", "07:00:00", "23:30:00", "10:00:00","11:00:00", "13:30:00","15:30:00", "20:00:00","23:00:00"),
        ("Tandoori Flames", "08:00:00", "22:00:00", "10:30:00","11:30:00", "13:00:00","15:30:00", "19:30:00","22:30:00"),
        ("Curry House", "07:30:00", "23:00:00", "10:00:00","11:30:00", "13:30:00", "14:00:00", "20:30:00","22:30:00"),
        ("Biryani Paradise", "06:30:00", "22:30:00", "09:30:00","10:30:00", "13:00:00", "15:00:00", "19:00:00","22:00:00"),
        ("The Royal Thali", "08:00:00", "22:00:00", "11:00:00","12:00:00", "14:00:00", "15:30:00", "20:00:00","23:00:00"),
        ("Masala Magic", "07:00:00", "22:30:00", "10:30:00","11:30:00",  "13:30:00", "15:00:00", "19:30:00","22:30:00"),
        ("Mughlai Feast", "06:00:00", "23:00:00", "09:00:00","10:30:00", "13:00:00", "15:30:00", "20:00:00","23:30:00"),
        ("South Spice", "06:30:00", "22:00:00", "09:30:00", "10:30:00","12:30:00","15:00:00", "19:30:00","22:30:00"),
        ("Punjabi Dhaba", "05:30:00", "23:30:00", "08:30:00", "10:30:00","12:30:00","15:30:00", "19:00:00","23:00:00"),
    ]

    cursor.executemany("""
        INSERT INTO restaurants (name, opening_time, closing_time, brunch_open_time,brunch_close_time, lunch_open_time,lunch_close_time, dinner_open_time,dinner_close_time)
        VALUES (%s, %s, %s, %s, %s, %s,%s,%s,%s);
    """, restaurants)

    # Insert sample clubs
    clubs = [
       ("Bollywood Nights", "19:30:00", "03:00:00", "10:00:00","11:30:00",  "14:00:00", "16:00:00", "20:30:00","23:00:00"),
        ("Desi Vibes", "20:00:00", "04:30:00", "09:00:00","10:30:00",  "13:30:00", "15:30:00", "19:00:00","22:30:00"),
        ("Mumbai Lights", "21:00:00", "05:00:00", "10:30:00","11:00:00", "14:00:00", "16:30:00", "20:00:00","23:30:00"),
        ("Bangalore Beats",  "07:00:00", "22:30:00", "10:30:00","11:30:00",  "13:30:00", "15:00:00", "19:30:00","22:30:00"),
        ("Delhi Groove", "06:00:00", "23:00:00", "09:00:00","10:30:00", "13:00:00", "15:30:00", "20:00:00","23:30:00"),
        ("Goa Trance", "06:30:00", "22:00:00", "09:30:00", "10:30:00","12:30:00","15:00:00", "19:30:00","22:30:00"),
        ("Pune Pulse",  "05:30:00", "23:30:00", "08:30:00", "10:30:00","12:30:00","15:30:00", "19:00:00","23:00:00"),
        ("Kolkata Rave", "07:30:00", "23:00:00", "10:00:00","11:30:00", "13:30:00", "14:00:00", "20:30:00","22:30:00"),
        ("Jaipur Jazz", "07:00:00", "23:30:00", "10:00:00","11:00:00", "13:30:00","15:30:00", "20:00:00","23:00:00"),
    ]

    cursor.executemany("""
        INSERT INTO clubs (name, opening_time, closing_time,brunch_open_time,brunch_close_time, lunch_open_time,lunch_close_time, dinner_open_time,   dinner_close_time)
        VALUES (%s, %s, %s,%s,%s,%s,%s,%s,%s);
    """, clubs)

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Fake data inserted successfully!")

if __name__ == "__main__":
    insert_fake_data()
