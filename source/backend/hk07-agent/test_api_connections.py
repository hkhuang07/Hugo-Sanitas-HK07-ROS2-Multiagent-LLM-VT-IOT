import os
import asyncio
import httpx
from dotenv import load_dotenv

# Load env variables
load_dotenv()

async def test_apis():
    hf_key = os.getenv("HUGGINGFACE_API_KEY", "")
    groq_key = os.getenv("GROQ_API_KEY", "")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    cohere_key = os.getenv("COHERE_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")

    async with httpx.AsyncClient(timeout=15.0) as client:
        print("=== PINGING APIs ===")

        # 1. HuggingFace
        print("\n[1] HuggingFace:")
        try:
            resp = await client.post(
                "https://api-inference.huggingface.co/models/facebook/bart-large-mnli",
                headers={"Authorization": f"Bearer {hf_key}"},
                json={"inputs": "hello", "parameters": {"candidate_labels": ["SAFETY", "MEDICAL", "EMPATHETIC"]}}
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Body: {resp.text}")
        except Exception as e:
            print(f"Failed: {e}")

        # 2. Groq
        print("\n[2] Groq:")
        try:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={
                    "model": "llama3-8b-8192",
                    "messages": [{"role": "user", "content": "ping"}],
                    "temperature": 0.1
                }
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Body: {resp.text}")
        except Exception as e:
            print(f"Failed: {e}")

        # 3. OpenRouter
        print("\n[3] OpenRouter:")
        try:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openrouter_key}",
                    "HTTP-Referer": "http://localhost",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "mistralai/mistral-7b-instruct:free",
                    "messages": [{"role": "user", "content": "ping"}]
                }
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Body: {resp.text}")
        except Exception as e:
            print(f"Failed: {e}")

        # 4. Cohere
        print("\n[4] Cohere:")
        try:
            resp = await client.post(
                "https://api.cohere.com/v1/chat",
                headers={"Authorization": f"Bearer {cohere_key}", "Content-Type": "application/json"},
                json={"model": "command-r", "message": "ping"}
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Body: {resp.text}")
        except Exception as e:
            print(f"Failed: {e}")

        # 5. Gemini
        print("\n[5] Gemini:")
        try:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}",
                json={"contents": [{"parts": [{"text": "ping"}]}]}
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Body: {resp.text}")
        except Exception as e:
            print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_apis())
