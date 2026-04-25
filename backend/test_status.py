import httpx
import asyncio

async def test():
    base_url = "https://gestor-noticias-backend-production.up.railway.app"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{base_url}/api/auth/login", json={"username": "admin", "password": "admin123"})
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Trigger retry
        print("Triggering retry (synchronous debug)...")
        retry = await client.post(f"{base_url}/api/escaneo/retry-errors", headers=headers)
        print("Retry result:", retry.json())

asyncio.run(test())
