import os
from dotenv import load_dotenv
import openai
import json

# Get absolute path to .env file
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
print(f"Looking for .env file at: {env_path}")
print(f"File exists: {os.path.exists(env_path)}")

# Try to load it
load_dotenv(env_path)

# Check if it loaded
api_key = os.getenv('OPENAI_API_KEY')
print(f"API Key loaded: {api_key is not None}")
if api_key:
    print(f"First few characters of API key: {api_key[:10]}...")

def test_openai():
    try:
        # Load environment variables
        load_dotenv()
        api_key = os.getenv('OPENAI_API_KEY')
        print(f"API Key found: {api_key[:15]}...")
        
        # Create OpenAI client
        client = openai.OpenAI(api_key=api_key)
        
        # Test a simple completion
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Generate a funny meme idea about programming"}],
                max_tokens=100
            )
            print("\nOpenAI Response:")
            print(response.choices[0].message.content)
            print("\nAPI test successful!")
        except Exception as e:
            print(f"\nError during API call: {str(e)}")
            print(f"Error type: {type(e)}")
            if hasattr(e, 'response'):
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
    except Exception as e:
        print(f"Setup error: {str(e)}")

if __name__ == "__main__":
    test_openai() 