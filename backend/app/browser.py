from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
import json
import os
import re
import sys
import platform
from typing import Dict, List, Optional, Callable, Any
import random
import string

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0

# Event loop policy fix for Windows (set in start_server.py)
if platform.system() == 'Windows' and sys.version_info >= (3, 8):
    try:
        if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except:
        pass


async def run_action_plan(plan: list, send_event: Callable) -> list:
    """
    Execute browser actions based on plan with robust error handling and retries.
    send_event is an async callback to send live events (to websocket).
    Returns extracted results from the page (if any).
    """
    results = []
    page = None
    browser = None
    
    try:
        async with async_playwright() as p:
            # Use environment variable or default to headless mode
            headless = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
            
            try:
                browser = await p.chromium.launch(
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled"] if not headless else []
                )
            except Exception as e:
                await send_event({
                    "type": "error",
                    "message": f"Failed to launch browser: {str(e)}. Install browsers: playwright install chromium"
                })
                return []
            
            # Create a new context with realistic viewport
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            await send_event({"type": "status", "message": "Browser initialized", "status": "ready"})
            
            # Execute each step in the plan
            for step_idx, step in enumerate(plan):
                action = step.get("action")
                await send_event({
                    "type": "action_start",
                    "action": action,
                    "step": step_idx + 1,
                    "total_steps": len(plan)
                })
                
                try:
                    if action == "navigate":
                        await _handle_navigate(page, step, send_event)
                    elif action == "wait_for":
                        await _handle_wait_for(page, step, send_event)
                    elif action == "type":
                        await _handle_type(page, step, send_event)
                    elif action == "click":
                        await _handle_click(page, step, send_event)
                    elif action == "filter_price":
                        await _handle_filter_price(page, step, send_event)
                    elif action == "filter_rating":
                        await _handle_filter_rating(page, step, send_event)
                    elif action == "extract_products":
                        extracted = await _handle_extract_products(page, step, send_event)
                        results.extend(extracted)
                    elif action == "fill_form_field":
                        await _handle_fill_form_field(page, step, send_event)
                    elif action == "submit_form":
                        await _handle_submit_form(page, step, send_event)
                    elif action == "unsupported":
                        await send_event({"type": "error", "message": step.get("reason", "Unsupported action")})
                        break
                    else:
                        await send_event({"type": "error", "message": f"Unknown action: {action}"})
                    
                except Exception as e:
                    await send_event({"type": "error", "message": f"Error in {action}: {str(e)}"})
                    continue
                
                await send_event({"type": "action_complete", "action": action})
            
            await send_event({"type": "status", "message": "Task completed", "status": "completed"})
            
    except NotImplementedError as e:
        msg = f"Playwright subprocess error. Use 'python start_server.py' (not uvicorn directly)."
        await send_event({"type": "error", "message": msg, "status": "failed"})
    except Exception as e:
        msg = f"Browser error: {str(e)}"
        if "subprocess" in str(e).lower():
            msg += " Try: python start_server.py"
        await send_event({"type": "error", "message": msg, "status": "failed"})
    finally:
        if page:
            await asyncio.sleep(1)
        if browser:
            await browser.close()

    return results


async def _find_selector_with_retry(page, selectors: str, timeout: int = 10000) -> Optional[Any]:
    """Try multiple selectors with retries"""
    for selector in [s.strip() for s in selectors.split(",")]:
        for attempt in range(MAX_RETRIES):
            try:
                return await page.wait_for_selector(selector, timeout=timeout, state="visible")
            except:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
    return None


async def _handle_navigate(page, step: dict, send_event: Callable):
    """Handle navigation action"""
    url = step.get("url")
    await send_event({"type": "action", "action": "navigate", "target": url, "message": f"Navigating to {url}"})
    try:
        await page.goto(url, wait_until=step.get("wait_until", "networkidle"), timeout=30000)
        title = await page.title()
        await send_event({"type": "action", "action": "navigate", "message": f"✓ Loaded: {title[:50]}"})
    except PlaywrightTimeoutError:
        await send_event({"type": "warning", "message": f"Navigation timeout, continuing..."})


async def _handle_wait_for(page, step: dict, send_event: Callable):
    """Handle wait_for action"""
    selector = step.get("selector")
    element = await _find_selector_with_retry(page, selector, step.get("timeout", 10000))
    if not element:
        await send_event({"type": "warning", "message": f"Element not found: {selector[:50]}"})


async def _handle_type(page, step: dict, send_event: Callable):
    """Handle type action"""
    selector = step.get("selector", "").split(",")[0].strip()
    value = step.get("value", "")
    if not await _find_selector_with_retry(page, selector):
        raise Exception(f"Input not found: {selector}")
    if step.get("clear_first"):
        await page.fill(selector, "")
    try:
        await page.click(selector, timeout=2000)
    except:
        pass
    await page.type(selector, value, delay=50)
    await send_event({"type": "action", "action": "type", "message": f"Typed: '{value[:30]}...'"})


async def _handle_click(page, step: dict, send_event: Callable):
    """Handle click action"""
    selector = step.get("selector", "")
    selectors = [s.strip() for s in selector.split(",")]
    clicked = False
    for sel in selectors:
        try:
            await page.click(sel, timeout=5000)
            clicked = True
            break
        except:
            continue
    if not clicked:
        await page.keyboard.press("Enter")
        await send_event({"type": "action", "action": "click", "message": "Pressed Enter"})
    else:
        await send_event({"type": "action", "action": "click", "message": "Clicked"})
    if step.get("wait_after"):
        await page.wait_for_load_state(step["wait_after"], timeout=15000)
        await asyncio.sleep(1)


async def _handle_filter_price(page, step: dict, send_event: Callable):
    """Handle price filtering - tries UI first, falls back to post-extraction"""
    max_p, min_p = step.get("max_price"), step.get("min_price")
    await send_event({"type": "action", "action": "filter_price", 
                     "message": f"Filtering: ₹{min_p or 0}-{max_p or '∞'}"})
    try:
        await asyncio.sleep(1)
        # Try UI filter inputs
        for sel in ["input[placeholder*='Max']", "input._2IX2F-:last-of-type"]:
            try:
                if max_p:
                    await page.fill(sel.split(",")[0], str(max_p), timeout=3000)
                    await page.keyboard.press("Enter")
                break
            except:
                continue
        await page.wait_for_load_state("networkidle", timeout=10000)
        await asyncio.sleep(2)
    except:
        pass  # Will filter in post-extraction
    # Store for post-extraction filtering
    step["max_price"], step["min_price"] = max_p, min_p


async def _handle_filter_rating(page, step: dict, send_event: Callable):
    """Handle rating filter"""
    rating = step.get("min_rating")
    await send_event({"type": "action", "action": "filter_rating", "message": f"Rating: {rating}+"})
    for sel in [f"[aria-label*='{rating} star']", f".rating-filter[data-rating='{rating}']"]:
        try:
            await page.click(sel, timeout=3000)
            await page.wait_for_load_state("networkidle", timeout=10000)
            return
        except:
            continue


async def _handle_extract_products(page, step: dict, send_event: Callable) -> List[Dict]:
    """Extract product/item information - supports Flipkart and Zomato"""
    product_selector = step.get("product_selector", "")
    fields = step.get("fields", {})
    count = step.get("count", 3)
    site = step.get("site", "flipkart")
    
    await send_event({"type": "action", "action": "extract_products", "message": f"Extracting top {count} results..."})
    
    try:
        await page.wait_for_selector("div[data-id], [class*='restaurant'], [class*='jumbo-tracker']", timeout=20000)
        await asyncio.sleep(2)
    except:
        pass
    await asyncio.sleep(2)
    
    # Site-specific extraction
    if site == "zomato":
        extraction_script = """
    (() => {
        const products = [];
        // Try multiple selectors for restaurant cards
        const selectors = [
            '[data-testid*="restaurant"]',
            '[class*="jumbo-tracker"]',
            '[class*="sc-1mo3ldo"]',
            '[class*="restaurant-card"]',
            'div[class*="card"]'
        ];
        
        let containers = [];
        for (const sel of selectors) {
            try {
                const els = document.querySelectorAll(sel);
                if (els.length > 0) {
                    containers = Array.from(els).slice(0, 20);
                    break;
                }
            } catch(e) { continue; }
        }
        
        // Fallback: find any div with restaurant-like content
        if (containers.length === 0) {
            const allDivs = Array.from(document.querySelectorAll('div'));
            for (const div of allDivs) {
                const hasRestaurantLink = div.querySelector('a[href*="/r/"]');
                const hasRating = div.textContent.match(/\\d\\.\\d|\\d\\s+★/);
                if (hasRestaurantLink && hasRating) {
                    containers.push(div);
                    if (containers.length >= 20) break;
                }
            }
        }
        
        containers.forEach(container => {
            const item = {};
            
            // Extract name - multiple strategies
            const nameSelectors = ['h4', 'a[href*="/r/"]', '[class*="restaurant-name"]', 'a'];
            for (const sel of nameSelectors) {
                const nameEl = container.querySelector(sel);
                if (nameEl) {
                    item.name = (nameEl.textContent || nameEl.getAttribute('title') || '').trim();
                    if (item.name && item.name.length >= 3) break;
                }
            }
            
            // Extract rating
            const ratingSelectors = ['[class*="rating"]', '[class*="sc-1q7bklc"]', '.rating'];
            for (const sel of ratingSelectors) {
                const ratingEl = container.querySelector(sel);
                if (ratingEl) {
                    const ratingText = ratingEl.textContent || '';
                    const match = ratingText.match(/([\\d.]+)/);
                    if (match && parseFloat(match[1]) >= 1 && parseFloat(match[1]) <= 5) {
                        item.rating = match[1];
                        break;
                    }
                }
            }
            
            // Extract cost for two (optional)
            const costSelectors = ['[class*="cost"]', '[class*="sc-1hez2tp"]', '[class*="price-range"]'];
            for (const sel of costSelectors) {
                const costEl = container.querySelector(sel);
                if (costEl) {
                    const costText = costEl.textContent || '';
                    const costMatch = costText.match(/₹?([\\d,]+)/);
                    if (costMatch) {
                        item.price = costMatch[1].replace(/,/g, '');
                        break;
                    }
                }
            }
            
            // Extract URL
            const link = container.querySelector('a[href*="/r/"]');
            if (link) {
                item.url = link.href || link.getAttribute('href') || '';
                if (item.url && !item.url.startsWith('http')) {
                    item.url = window.location.origin + item.url;
                }
            }
            
            // For restaurants: name is required, rating preferred, price optional
            if (item.name && item.name.length >= 3) {
                item.rating = item.rating || '';
                item.price = item.price || '';
                item.url = item.url || '';
                products.push(item);
            }
        });
        
        return products;
    })()
    """
    else:
        # Flipkart/product extraction
        extraction_script = """
    (() => {
        const products = [];
        
        // Flipkart product containers - multiple strategies
        const containerSelectors = [
            'div[data-id]',
            'div._1AtVbE',
            'div._2kHMtA',
            'div[class*="_13oc-S"]',
            'div[class*="tUxRFH"]',
            '[data-id]'
        ];
        
        let productContainers = [];
        
        for (const sel of containerSelectors) {
            try {
                const elements = document.querySelectorAll(sel);
                if (elements.length > 0) {
                    productContainers = Array.from(elements).slice(0, 20); // Get more for filtering
                    console.log('Found ' + elements.length + ' containers with: ' + sel);
                    break;
                }
            } catch(e) {
                continue;
            }
        }
        
        // If still no containers, try finding any div with product-like structure
        if (productContainers.length === 0) {
            const allDivs = document.querySelectorAll('div');
            for (const div of allDivs) {
                const hasLink = div.querySelector('a[href*="/p/"]');
                const hasPrice = div.textContent.match(/₹[\\d,]+|Rs\\.?[\\d,]+/);
                if (hasLink && hasPrice && !div.querySelector('div[data-id]')) {
                    productContainers.push(div);
                    if (productContainers.length >= 20) break;
                }
            }
        }
        
        productContainers.forEach((container, idx) => {
            const item = {};
            
            // Extract URL - most reliable
            const links = container.querySelectorAll('a[href*="/p/"]');
            if (links.length > 0) {
                const link = links[0];
                item.url = link.href || link.getAttribute('href') || '';
                if (item.url && !item.url.startsWith('http')) {
                    item.url = window.location.origin + item.url;
                }
                // Extract name from link
                item.name = link.getAttribute('title') || link.textContent.trim() || '';
            }
            
            // Try alternative name extraction
            if (!item.name || item.name.length < 3) {
                const nameSelectors = [
                    'a[title]',
                    '._4rR01T',
                    'a._2UzuFa',
                    'a.s1Q9rs',
                    'a._1fQZEK'
                ];
                for (const sel of nameSelectors) {
                    const elem = container.querySelector(sel);
                    if (elem) {
                        item.name = elem.getAttribute('title') || elem.textContent.trim() || '';
                        if (item.name && item.name.length >= 3) break;
                    }
                }
            }
            
            // Extract price - Flipkart specific
            const priceSelectors = [
                '._30jeq3',
                'div._25b18c',
                'div[class*="_30jeq3"]',
                'div._1_WHN1'
            ];
            for (const sel of priceSelectors) {
                const priceEl = container.querySelector(sel);
                if (priceEl) {
                    let priceText = priceEl.textContent || priceEl.innerText || '';
                    priceText = priceText.replace(/[^\\d]/g, '');
                    if (priceText && priceText.length >= 4) {
                        item.price = priceText;
                        break;
                    }
                }
            }
            
            // Alternative price extraction - search all text for price pattern
            if (!item.price) {
                const allText = container.textContent || '';
                const priceMatch = allText.match(/₹\\s*([\\d,]+)|Rs\\.?\\s*([\\d,]+)/);
                if (priceMatch) {
                    item.price = (priceMatch[1] || priceMatch[2] || '').replace(/[,]/g, '');
                }
            }
            
            // Extract rating
            const ratingSelectors = [
                '._3LWZlK',
                'div[class*="_3LWZlK"]',
                '._2_R_DZ span',
                '[class*="rating"]'
            ];
            for (const sel of ratingSelectors) {
                const ratingEl = container.querySelector(sel);
                if (ratingEl) {
                    let ratingText = ratingEl.textContent || ratingEl.innerText || '';
                    const ratingMatch = ratingText.match(/([\\d.]+)/);
                    if (ratingMatch) {
                        item.rating = ratingMatch[1];
                        break;
                    }
                }
            }
            
            // Clean up values
            if (item.name) {
                item.name = item.name.trim();
                // Remove extra whitespace and newlines
                item.name = item.name.replace(/\\s+/g, ' ').substring(0, 150);
            }
            
            if (item.price) {
                item.price = item.price.replace(/[,]/g, '');
                if (!item.price || item.price === '0' || item.price.length < 3) {
                    item.price = null;
                }
            }
            
            // Only add product if it has valid name and price
            if (item.name && item.name.length >= 3 && item.price && item.price.length >= 3) {
                // Set defaults for missing optional fields
                if (!item.url) item.url = 'N/A';
                if (!item.rating) item.rating = 'N/A';
                products.push(item);
            }
        });
        
        return products;
    })()
    """
    
    try:
        products = await page.evaluate(extraction_script)
        
        # Validate and filter products (different rules for restaurants vs products)
        valid_products = []
        for product in (products or []):
            name = product.get("name", "").strip()
            if not name or len(name) < 3:
                continue
            
            price_str = str(product.get("price", "0")).replace(",", "").replace("₹", "")
            try:
                price_val = int(price_str) if price_str else 0
                
                # For restaurants: name required, price optional; For products: both required
                if site == "zomato":
                    product["price"] = str(price_val) if price_val > 0 else ""
                    product["url"] = product.get("url", "") or ""
                    print(product["url"])
                    product["rating"] = product.get("rating", "") or ""
                    valid_products.append(product)
                else:
                    if price_val >= 100:
                        product["price"] = str(price_val)
                        product["url"] = product.get("url", "") or ""
                        product["rating"] = product.get("rating", "") or ""
                        valid_products.append(product)
            except:
                if site == "zomato":
                    product["price"] = ""
                    product["url"] = product.get("url", "") or ""
                    product["rating"] = product.get("rating", "") or ""
                    valid_products.append(product)
                continue
        products = valid_products
        
        # Filter by rating (for restaurants) or price (for products)
        filtered = products
        if step.get("min_rating") and site == "zomato":
            min_rating = float(step.get("min_rating"))
            filtered = [p for p in products 
                       if p.get("rating") and float(p.get("rating", "0")) >= min_rating]
            await send_event({"type": "action", "action": "filter_rating", 
                            "message": f"Filtered: {len(filtered)} restaurants with {min_rating}+ rating"})
        
        if (step.get("max_price") or step.get("min_price")) and site != "zomato":
            max_p, min_p = step.get("max_price"), step.get("min_price")
            filtered = [p for p in filtered 
                       if not p.get("price") or not p["price"] or
                       int(p["price"] or "0") <= (int(max_p) if max_p else 999999999) 
                       and int(p["price"] or "0") >= (int(min_p) if min_p else 0)]
            if max_p or min_p:
                await send_event({"type": "action", "action": "filter_price", 
                                "message": f"Filtered: {len(filtered)} items"})
        
        final_products = filtered[:count] if filtered else []
        
        if len(final_products) == 0:
            await send_event({
                "type": "warning",
                "message": "No valid products found. The page structure might have changed. Try a different search query."
            })
        else:
            await send_event({
                "type": "action",
                "action": "extract_products",
                "message": f"✓ Extracted {len(final_products)} valid results",
                "count": len(final_products),
                "preview": final_products[:2] if final_products else []
            })
        print(final_products)
        return final_products
    
    except Exception as e:
        await send_event({
            "type": "error",
            "message": f"Extraction error: {str(e)}. Page title: {await page.title() if page else 'N/A'}"
        })
        return []


async def _handle_fill_form_field(page, step: dict, send_event: Callable):
    """Handle form field filling"""
    field_name = step.get("field_name")
    value = step.get("value", "")
    if not value or step.get("generate_if_needed"):
        if "email" in field_name.lower():
            value = f"temp_{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}@example.com"
        elif "phone" in field_name.lower():
            value = f"+91{random.randint(7000000000, 9999999999)}"
        else:
            value = f"test_{random.randint(1000, 9999)}"
    selectors = [f"input[name='{field_name}']", f"input[id='{field_name}']", 
                f"input[placeholder*='{field_name}']", f"#{field_name}"]
    if await _find_selector_with_retry(page, ",".join(selectors)):
        await page.fill(selectors[0], value)
        await send_event({"type": "action", "action": "fill_form_field", "message": f"Filled {field_name}"})
    else:
        await send_event({"type": "warning", "message": f"Field not found: {field_name}"})


async def _handle_submit_form(page, step: dict, send_event: Callable):
    """Handle form submission"""
    selectors = "button[type='submit'], input[type='submit'], button:has-text('Submit')"
    if await _find_selector_with_retry(page, selectors):
        await page.click(selectors.split(",")[0])
    else:
        await page.keyboard.press("Enter")
    await send_event({"type": "action", "action": "submit_form", "message": "Form submitted"})
    try:
        await page.wait_for_load_state(step.get("wait_after", "networkidle"), timeout=15000)
    except:
        pass
