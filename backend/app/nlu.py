import requests
import json
import os
from dotenv import load_dotenv
import re

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
MODEL = os.getenv("LLM_MODEL", "openai/gpt-3.5-turbo")

def parse_user_intent(text: str) -> dict:
    """
    Parse user intent from natural language text.
    Supports multiple intents: product_search, form_fill, comparison, local_discovery, navigation
    """
    if not OPENROUTER_API_KEY:
        # Fallback to rule-based parsing if API key is not available
        return _rule_based_intent_parsing(text)
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Enhanced prompt for extracting multiple intents
    prompt = f"""Extract the intent and parameters from this user command: "{text}"

Return a JSON object with these fields:
- "intent": one of [product_search, form_fill, comparison, local_discovery, navigation, unknown]
- "site" (optional): target website (e.g., "flipkart", "amazon", "zomato")
- "query" (optional): search query text
- "product_name" (optional): product/item name
- "location" (optional): location/area name (for local_discovery)
- "category" (optional): category type (e.g., "pizza", "restaurants")
- "filters" (object): filters with keys like:
  - max_price, min_price (numbers)
  - rating_min (number, e.g., 4.0)
  - count (number, e.g., 3 for "top 3")
  - sort_by (string)
- "form_data" (object, for form_fill): field_name -> value mappings
- "url" (optional): URL to navigate to
- "comparison_fields" (array, for comparison): fields to compare (e.g., ["price", "rating"])

Examples:
- "Find MacBook Air under ₹100000" → {{"intent": "product_search", "product_name": "MacBook Air", "filters": {{"max_price": 100000}}}}
- "Fill signup form with temp email" → {{"intent": "form_fill", "form_data": {{"email": "generate_temp"}}}}
- "Top 3 pizza places near Indiranagar with 4+ rating" → {{"intent": "local_discovery", "category": "pizza", "location": "Indiranagar", "filters": {{"rating_min": 4, "count": 3}}}}

Return ONLY valid JSON, no markdown or extra text."""

    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0.1
    }

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        response_json = response.json()
        content = response_json["choices"][0]["message"]["content"].strip()
        
        # Clean JSON from markdown code blocks if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        
        intent_data = json.loads(content)
        
        # Validate and set defaults
        if "intent" not in intent_data:
            intent_data["intent"] = "unknown"
        if "filters" not in intent_data:
            intent_data["filters"] = {}
            
        return intent_data
    
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}, content: {content[:200]}")
        return _rule_based_intent_parsing(text)
    except requests.exceptions.RequestException as e:
        print(f"API request error: {e}")
        return _rule_based_intent_parsing(text)
    except Exception as e:
        print(f"Unexpected error in NLU: {e}")
        return _rule_based_intent_parsing(text)


def _rule_based_intent_parsing(text: str) -> dict:
    """Fallback rule-based intent parsing"""
    text_lower = text.lower()
    intent_data = {"intent": "unknown", "filters": {}}
    
    # Extract price filters
    price_match = re.search(r'[₹$]?\s*(\d+(?:,\d+)*)', text)
    if price_match:
        price = int(price_match.group(1).replace(",", ""))
        if "under" in text_lower or "below" in text_lower or "max" in text_lower:
            intent_data["filters"]["max_price"] = price
        elif "above" in text_lower or "min" in text_lower:
            intent_data["filters"]["min_price"] = price
    
    # Extract count (top N)
    count_match = re.search(r'(?:top|first)\s*(\d+)', text_lower)
    if count_match:
        intent_data["filters"]["count"] = int(count_match.group(1))
    
    # Extract rating
    rating_match = re.search(r'(\d+(?:\.\d+)?)\s*★|rating[:\s]+(\d+)', text_lower)
    if rating_match:
        rating = float(rating_match.group(1) or rating_match.group(2))
        intent_data["filters"]["rating_min"] = rating
    
    # Detect intent type
    if any(word in text_lower for word in ["find", "search", "show", "get", "book"]):
        intent_data["intent"] = "product_search"
        # Extract product name (simple heuristic)
        words = text.split()
        product_words = []
        skip_next = False
        for i, word in enumerate(words):
            if skip_next:
                skip_next = False
                continue
            if word.lower() in ["find", "search", "show", "get", "book", "for", "a", "an", "the"]:
                continue
            if word.lower() in ["under", "below", "above", "near", "with", "rating"]:
                break
            product_words.append(word)
        intent_data["product_name"] = " ".join(product_words[:5])  # Limit to 5 words
    
    elif any(word in text_lower for word in ["fill", "submit", "register", "signup", "form"]):
        intent_data["intent"] = "form_fill"
        intent_data["form_data"] = {}
    
    elif any(word in text_lower for word in ["compare", "comparison"]):
        intent_data["intent"] = "comparison"
    
    elif any(word in text_lower for word in ["near", "places", "restaurants", "pizza", "delivery"]):
        intent_data["intent"] = "local_discovery"
        location_match = re.search(r'near\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text)
        if location_match:
            intent_data["location"] = location_match.group(1)
    
    return intent_data
