"""
Standalone entry point for the FastAPI server.

Uses loop="none" to bypass uvicorn's asyncio_setup() which on Windows 3.10
deliberately switches to WindowsSelectorEventLoopPolicy — a loop that cannot
spawn subprocesses (NotImplementedError). Keeping the default
WindowsProactorEventLoopPolicy lets Playwright launch Chromium.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        loop="none",
    )
