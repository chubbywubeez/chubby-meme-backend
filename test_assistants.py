import os
from dotenv import load_dotenv
import openai
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_assistants():
    try:
        load_dotenv()
        api_key = os.getenv('OPENAI_API_KEY')
        client = openai.OpenAI(api_key=api_key)
        
        # Test assistant access
        PERSONA_ASSISTANT_ID = "asst_mdB3xM0OczHqAKOB3EBrcp72"
        
        try:
            # Try to retrieve the assistant
            assistant = client.beta.assistants.retrieve(PERSONA_ASSISTANT_ID)
            print(f"Successfully retrieved assistant: {assistant.name}")
        except Exception as e:
            print(f"Error accessing assistant: {str(e)}")
            
        # Test basic API functionality
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Say hello!"}]
            )
            print("\nBasic API test successful!")
            print(f"Response: {response.choices[0].message.content}")
        except Exception as e:
            print(f"Error with basic API call: {str(e)}")
            
    except Exception as e:
        print(f"Setup error: {str(e)}")

if __name__ == "__main__":
    test_assistants() 