import os
import mysql.connector
from mysql.connector import Error
from utils.logger import get_logger

logger = get_logger(__name__)

def get_db_connection():
    try:
        # Parse Heroku ClearDB URL
        if os.getenv('CLEARDB_DATABASE_URL'):
            url = os.getenv('CLEARDB_DATABASE_URL')
            # mysql://username:password@host/database
            parts = url.replace('mysql://', '').split('@')
            user_pass = parts[0].split(':')
            host_db = parts[1].split('/')
            
            connection = mysql.connector.connect(
                host=host_db[0],
                user=user_pass[0],
                password=user_pass[1],
                database=host_db[1].split('?')[0]
            )
        else:
            # Local development
            connection = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='chubby_memes'
            )
            
        return connection
    except Error as e:
        logger.error(f"Error connecting to MySQL: {e}")
        raise e

def init_db():
    """Initialize database tables"""
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memes (
                id VARCHAR(36) PRIMARY KEY,
                created_at DATETIME,
                type VARCHAR(20),
                persona_prompt VARCHAR(255),
                theme_prompt VARCHAR(255),
                image_url VARCHAR(255)
            )
        """)
        connection.commit()
    except Error as e:
        logger.error(f"Error creating tables: {e}")
        raise e
    finally:
        cursor.close()
        connection.close() 