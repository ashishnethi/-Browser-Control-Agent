import sys
import platform
import asyncio

if platform.system() == 'Windows':
    if sys.version_info >= (3, 8):
        # Windows ProactorEventLoopPolicy supports subprocess operations required by Playwright
        try:
            # Only set if not already set
            current_policy = asyncio.get_event_loop_policy()
            if not isinstance(current_policy, asyncio.WindowsProactorEventLoopPolicy):
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                print("✓ Set WindowsProactorEventLoopPolicy for Playwright compatibility")
        except Exception as e:
            print(f"Warning: Could not set event loop policy: {e}")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from backend.app.nlu import parse_user_intent
from backend.app.planner import generate_action_plan
from backend.app.browser import run_action_plan
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
def read_root():
    return {"message": "Quash Browser Agent API", "status": "running", "websocket": "/ws/chat"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# @app.websocket("/ws/chat")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         while True:
#             user_text = await websocket.receive_text()
#             intent_data = parse_user_intent(user_text)
#             plan=generate_action_plan(intent_data)
#             await websocket.send_text(json.dumps({"type": "plan", "plan": plan}))
#             results = await run_action_plan(plan, send_event)
#     except WebSocketDisconnect:
#         print("Client disconnected")

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    async def send_event(event_data):
        """Send event to client - accepts dict or string for backward compatibility"""
        if isinstance(event_data, dict):
            await websocket.send_text(json.dumps(event_data))
        else:
            # Backward compatibility: string message
            await websocket.send_text(json.dumps({"type": "message", "content": event_data}))

    try:
        while True:
            user_text = await websocket.receive_text()
            
            await send_event({
                "type": "user_message",
                "content": user_text
            })

            # Parse intent
            await send_event({
                "type": "status",
                "message": "Understanding your request...",
                "status": "processing"
            })
            
            intent_data = parse_user_intent(user_text)
            
            await send_event({
                "type": "intent",
                "data": intent_data
            })

            await send_event({
                "type": "status",
                "message": "Planning actions...",
                "status": "planning"
            })
            
            plan = generate_action_plan(intent_data)
            
            await send_event({
                "type": "plan",
                "plan": plan,
                "step_count": len(plan)
            })

            # Execute plan
            await send_event({
                "type": "status",
                "message": "Executing actions...",
                "status": "executing"
            })
            
            results = await run_action_plan(plan, send_event)

            valid = []
            for r in results:
                name = r.get("name", "").strip()
                price_str = str(r.get("price", "0")).replace(",", "").replace("₹", "")
                if name and len(name) >= 3:
                    try:
                        # For restaurants, price can be 0 or missing
                        price_val = int(price_str) if price_str else 0
                        # Products need price >= 100, restaurants just need name
                        if price_val >= 100 or not price_str or price_str == "0":
                            valid.append(r)
                    except:
                        if not price_str or price_str == "0":
                            valid.append(r)
            
            await send_event({"type": "result", "data": valid, "count": len(valid)})
            if not valid and results:
                await send_event({"type": "warning", "message": "Found items but extraction failed"})

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Server error: {str(e)}"
            }))
        except:
            pass
        print(f"Error in websocket: {e}")
