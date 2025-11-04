#!/usr/bin/env python

import sys
import platform

if platform.system() == 'Windows':
    import asyncio
    if sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print("✓ Set WindowsProactorEventLoopPolicy for Playwright")
    else:
        print("✗ ERROR: Python 3.8+ required on Windows")
        sys.exit(1)

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("Starting Quash Browser Agent Backend...")
    print("=" * 60)
    print(f"Python: {sys.version}")
    print(f"Platform: {platform.system()} {platform.release()}")
    if platform.system() == 'Windows':
        policy = asyncio.get_event_loop_policy()
        print(f"Event Loop Policy: {type(policy).__name__}")
        print("✓ Windows subprocess support enabled")
    print("=" * 60)
    print("\nServer starting at http://localhost:8000")
    print("WebSocket endpoint: ws://localhost:8000/ws/chat")
    print("\nPress CTRL+C to stop\n")
    
    try:
        uvicorn.run(
            "backend.app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\nServer stopped by user")
    except Exception as e:
        print(f"\n\nERROR: {e}")
        print("\nIf you see NotImplementedError, make sure:")
        print("1. You're using Python 3.8+")
        print("2. You're running: python start_server.py (not uvicorn directly)")
        print("3. Playwright browsers are installed: playwright install chromium")
        sys.exit(1)

