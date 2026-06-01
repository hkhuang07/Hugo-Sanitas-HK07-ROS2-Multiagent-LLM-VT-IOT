import os
import asyncio
import httpx
from dotenv import load_dotenv

# Load env variables
load_dotenv()

async def test_apis_v2():
    groq_key = os.getenv("GROQ_API_KEY", "")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    cohere_key = os.getenv("COHERE_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")

    async with httpx.AsyncClient(timeout=15.0) as client:
        print("=== PINGING APIs V2 ===")

        # 1. Groq
        print("\n[1] Groq:")
        try:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "temperature": 0.1
                }
            )
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:300]}")
        except Exception as e:
            print(f"Failed: {e}")

        # 2. OpenRouter
        print("\n[2] OpenRouter:")
        try:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openrouter_key}",
                    "HTTP-Referer": "http://localhost",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openrouter/free",
                    "messages": [{"role": "user", "content": "Hello"}]
                }
            )
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:300]}")
        except Exception as e:
            print(f"Failed: {e}")

        # 3. Cohere
        print("\n[3] Cohere:")
        try:
            resp = await client.post(
                "https://api.cohere.com/v1/chat",
                headers={"Authorization": f"Bearer {cohere_key}", "Content-Type": "application/json"},
                json={"model": "command-r-08-2024", "message": "Hello"}
            )
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:300]}")
        except Exception as e:
            print(f"Failed: {e}")

        # 4. Gemini
        print("\n[4] Gemini:")
        try:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={gemini_key}",
                json={"contents": [{"parts": [{"text": "Hello"}]}]}
            )
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:300]}")
        except Exception as e:
            print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_apis_v2())
