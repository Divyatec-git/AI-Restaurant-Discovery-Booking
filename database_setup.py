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
        database=os.getenv("DB_NAME", "puravida_agent")
    )
    return conn

def create_tables():
    """Create restaurants table if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurants (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        opening_time TIME NOT NULL,
        closing_time TIME NOT NULL,
        brunch_open_time TIME DEFAULT NULL,
        lunch_open_time TIME DEFAULT NULL,
        dinner_open_time TIME DEFAULT NULL,
        brunch_close_time TIME DEFAULT NULL,
        lunch_close_time TIME DEFAULT NULL,
        dinner_close_time TIME DEFAULT NULL
    );           
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clubs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        opening_time TIME NOT NULL,
        closing_time TIME NOT NULL,
        brunch_open_time TIME DEFAULT NULL,
        lunch_open_time TIME DEFAULT NULL,
        dinner_open_time TIME DEFAULT NULL,
         
        brunch_close_time TIME DEFAULT NULL,
        lunch_close_time TIME DEFAULT NULL,
        dinner_close_time TIME DEFAULT NULL
    );

    """)

   
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS book_restaurants (
        id INT AUTO_INCREMENT PRIMARY KEY,
        place_name VARCHAR(255) NOT NULL,
        booking_time TIME NOT NULL,
        user_id INT NOT NULL,
        meal_type VARCHAR(100) NOT NULL,
        order_id VARCHAR(255) NOT NULL,
        payment_id VARCHAR(255) NOT NULL,

    );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS book_clubs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        place_name VARCHAR(255) NOT NULL,
        booking_time TIME NOT NULL,
        user_id INT NOT NULL,
        meal_type VARCHAR(100) NOT NULL,
        order_id VARCHAR(255) NOT NULL,
        payment_id VARCHAR(255) NOT NULL,
                   
    );
    """) 
      
    cursor.execute("""
        CREATE TABLE google_restaurants (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        place_id VARCHAR(255) NOT NULL,
        location VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ); 
    """)  
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS book_from_google (
        id INT AUTO_INCREMENT PRIMARY KEY,
        place_name VARCHAR(255) NOT NULL,
        booking_time VARCHAR(255) NOT NULL,
        user_id INT NOT NULL,
        recipient_number VARCHAR(100) NOT NULL          
    );
    """) 
    

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Table created successfully!")

if __name__ == "__main__":
    create_tables()
