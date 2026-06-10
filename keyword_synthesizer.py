import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load variables from your secure local .env shield
load_dotenv()

def run_keyword_synthesizer():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY is missing from your .env file.")
        return

    print("Initializing Google Gen AI Production Client...")
    client = genai.Client()

    dealer_profile = """
    Dealership Domain: www.apexautotexas.com
    Location/Radius: Austin, TX (25-mile radius)
    Inventory Tier: Used Inventory
    Core Vehicle Matrix Segments: ["SUVs", "Trucks", "Sedans"]
    Key Makes Handled: ["Ford", "Chevrolet", "Toyota"]
    """

    system_instruction = (
        "You are an expert Automotive Google Ads strategist. Your task is to process a dealer's inventory profile "
        "and return a cleanly structured keyword map. CRITICAL RULE: You must isolate queries into strictly "
        "separate 'Purchase Intent' matching phrases and 'Service Intent' matching phrases. Do not mix them up."
    )

    user_prompt = f"Analyze the following dealership profile matrix and generate high-intent search keywords based on your instructions:\n{dealer_profile}"

    print("Transmitting semantic payload to Gemini (Requesting JSON Layout)...")
    
    # We pass a strict Pydantic-like Configuration telling Gemini to ONLY speak JSON
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "dealership_domain": {"type": "STRING"},
                    "purchase_intent_keywords": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": "High-intent phrases focused on buying, inventory, and local dealership searches."
                    },
                    "service_intent_keywords": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": "High-intent phrases focused on car repair, maintenance, fixes, and mechanics."
                    }
                },
                "required": ["dealership_domain", "purchase_intent_keywords", "service_intent_keywords"]
            }
        )
    )

    print("\n--- SYNTHESIZED KEYWORD JSON MATRIX ---")
    print(response.text)
    print("---------------------------------------")

    # Let's save this output automatically into your 'output' directory
    try:
        os.makedirs("output", exist_ok=True)
        json_data = json.loads(response.text)
        with open("output/keywords.json", "w") as f:
            json.dump(json_data, f, indent=4)
        print("SUCCESS: Structured payload safely cached inside output/keywords.json!")
    except Exception as e:
        print(f"Failed to cache JSON: {e}")

if __name__ == "__main__":
    run_keyword_synthesizer()