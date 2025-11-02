import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
MODEL = os.getenv("LLM_MODEL", "openai/gpt-3.5-turbo")

# Site-specific selectors and configurations
SITE_CONFIGS = {
    "flipkart": {
        "url": "https://www.flipkart.com",
        "search_input": "input[title*='Search'], input[name='q'], input[placeholder*='Search'], input[type='text']",
        "search_button": "button[type='submit'], svg + button, button._2iLD__",
        "product_card": "[data-id], div[data-id], ._1AtVbE, div._2kHMtA, div[class*='_13oc-S'], div[class*='tUxRFH']",
        "price_selector": "._30jeq3, ._25b18c, div[class*='_30jeq3'], div._1_WHN1",
        "title_selector": "a._2UzuFa, a.s1Q9rs, a[title], ._4rR01T, a._1fQZEK",
        "rating_selector": "._3LWZlK, div[class*='_3LWZlK'], ._2_R_DZ span",
        "link_selector": "a._2UzuFa, a.s1Q9rs, a._1fQZEK, a",
    },
    "amazon": {
        "url": "https://www.amazon.in",
        "search_input": "#twotabsearchtextbox, input[name='field-keywords']",
        "search_button": "#nav-search-submit-button, input[type='submit'][value='Go']",
        "product_card": "[data-index], .s-result-item",
        "price_selector": ".a-price-whole, .a-price .a-offscreen",
        "title_selector": "h2 a span, .a-text-normal",
        "rating_selector": ".a-icon-alt, .a-icon-star-small",
        "link_selector": "h2 a",
    },
    "zomato": {
        "url": "https://www.zomato.com",
        "search_input": "input[placeholder*='Search'], input[name='q'], input[type='text']",
        "search_button": "button[type='submit'], .sc-fzqARJ, button",
        "restaurant_card": "[data-testid*='restaurant'], [class*='jumbo-tracker'], [class*='sc-1mo3ldo'], [class*='restaurant-card']",
        "name_selector": "h4, a[href*='/r/'], [class*='restaurant-name']",
        "rating_selector": "[class*='rating'], [class*='sc-1q7bklc'], .rating",
        "price_selector": "[class*='cost'], [class*='sc-1hez2tp'], [class*='price-range']",
        "link_selector": "a[href*='/r/'], a",
    }
}


def generate_action_plan(intent_data: dict) -> list:
    """Generate browser action plan from intent"""
    intent = intent_data.get("intent", "unknown")
    site = intent_data.get("site", "flipkart").lower()
    filters = intent_data.get("filters", {})
    count = filters.get("count", 3)
    
    if OPENROUTER_API_KEY and (plan := _ai_plan(intent_data)):
        return plan
    
    plan = []
    
    if intent == "product_search":
        site_config = SITE_CONFIGS.get(site, SITE_CONFIGS["flipkart"])
        query = intent_data.get("query") or intent_data.get("product_name", "")
        
        plan.append({
            "action": "navigate",
            "url": site_config["url"],
            "wait_until": "networkidle"
        })
        plan.append({
            "action": "wait_for",
            "selector": site_config["search_input"],
            "timeout": 10000
        })
        plan.append({
            "action": "type",
            "selector": site_config["search_input"],
            "value": query,
            "clear_first": True
        })
        plan.append({
            "action": "click",
            "selector": site_config["search_button"],
            "wait_after": "networkidle"
        })
        
        # Apply price filter if specified
        if "max_price" in filters:
            plan.append({
                "action": "filter_price",
                "max_price": filters["max_price"],
                "min_price": filters.get("min_price")
            })
        
        # Extract results
        plan.append({
            "action": "extract_products",
            "product_selector": site_config["product_card"],
            "fields": {
                "name": site_config["title_selector"],
                "price": site_config["price_selector"],
                "rating": site_config["rating_selector"],
                "url": site_config["link_selector"]
            },
            "count": count,
            "site": site
        })
        
    elif intent == "local_discovery":
        location = intent_data.get("location", "")
        category = intent_data.get("category", "restaurants")
        site_config = SITE_CONFIGS.get("zomato", SITE_CONFIGS["flipkart"])
        
        query = f"{category} near {location}"
        plan.append({
            "action": "navigate",
            "url": site_config["url"],
            "wait_until": "networkidle"
        })
        plan.append({
            "action": "type",
            "selector": site_config["search_input"],
            "value": query
        })
        plan.append({
            "action": "click",
            "selector": site_config["search_button"],
            "wait_after": "networkidle"
        })
        
        if "rating_min" in filters:
            plan.append({
                "action": "filter_rating",
                "min_rating": filters["rating_min"]
            })
        
        plan.append({
            "action": "extract_products",
            "product_selector": site_config.get("restaurant_card", site_config.get("product_card", "")),
            "fields": {
                "name": site_config.get("name_selector", site_config.get("title_selector", "")),
                "rating": site_config["rating_selector"],
                "price": site_config.get("price_selector", ""),
                "url": site_config["link_selector"]
            },
            "count": count,
            "site": "zomato",
            "min_rating": filters.get("rating_min")  # Pass rating filter to extraction
        })
        
    elif intent == "form_fill":
        url = intent_data.get("url", "")
        form_data = intent_data.get("form_data", {})
        
        if url:
            plan.append({
                "action": "navigate",
                "url": url,
                "wait_until": "networkidle"
            })
        
        # Fill form fields
        for field_name, value in form_data.items():
            plan.append({
                "action": "fill_form_field",
                "field_name": field_name,
                "value": value,
                "generate_if_needed": True
            })
        
        plan.append({
            "action": "submit_form",
            "wait_after": "networkidle"
        })
        
    elif intent == "comparison":
        # Multi-site comparison workflow
        product_name = intent_data.get("product_name", "")
        sites = intent_data.get("sites", ["flipkart", "amazon"])
        
        for site in sites:
            site_config = SITE_CONFIGS.get(site, SITE_CONFIGS["flipkart"])
            plan.append({
                "action": "navigate",
                "url": site_config["url"]
            })
        plan.append({
            "action": "type",
                "selector": site_config["search_input"],
            "value": product_name
        })
        plan.append({
            "action": "click",
                "selector": site_config["search_button"]
        })
        plan.append({
                "action": "extract_products",
                "product_selector": site_config["product_card"],
                "fields": {
                    "name": site_config["title_selector"],
                    "price": site_config["price_selector"],
                    "rating": site_config["rating_selector"],
                    "url": site_config["link_selector"]
                },
                "count": 1,
                "site": site
            })
    
    elif intent == "navigation":
        url = intent_data.get("url", "")
        if url:
            plan.append({
                "action": "navigate",
                "url": url,
                "wait_until": "networkidle"
            })
    
    else:
        plan.append({
            "action": "unsupported",
            "reason": f"Intent '{intent}' not handled yet. Please try: product_search, local_discovery, form_fill, or comparison."
        })

    return plan


def _ai_plan(intent_data: dict) -> list:
    """AI-powered planning using LLM"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""Given this intent data: {json.dumps(intent_data, indent=2)}
For local discovery intents, ALWAYS generate a plan that navigates and interacts with the Zomato website (https://www.zomato.com), never Google Maps or other sites.
For product search intents, use Flipkart or Amazon as specified.
Generate a step-by-step action plan as a JSON array. Each action is an object with:
- "action": action type (navigate, type, click, wait_for, extract_products, filter_price, fill_form_field, submit_form)
- Other fields specific to each action

Available actions:
1. navigate: {{"action": "navigate", "url": "...", "wait_until": "networkidle"}}
2. type: {{"action": "type", "selector": "...", "value": "...", "clear_first": true}}
3. click: {{"action": "click", "selector": "...", "wait_after": "networkidle"}}
4. wait_for: {{"action": "wait_for", "selector": "...", "timeout": 10000}}
5. extract_products: {{"action": "extract_products", "product_selector": "...", "fields": {{"name": "...", "price": "...", "rating": "...", "url": "..."}}, "count": 3, "site": "flipkart"}}
6. filter_price: {{"action": "filter_price", "max_price": 100000}}
7. fill_form_field: {{"action": "fill_form_field", "field_name": "email", "value": "..."}}
8. submit_form: {{"action": "submit_form"}}

Return ONLY a JSON array of actions, no markdown."""

    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 800,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        
        # Clean JSON
        if content.startswith("```"):
            import re
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        
        plan = json.loads(content)
        if isinstance(plan, list):
            return plan
    except Exception as e:
        print(f"AI planning failed: {e}")
    
    return None
