import httpx

from app.config import settings


class BackendAPI:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.BACKEND_BASE_URL,
            timeout=httpx.Timeout(20.0),
        )

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("BackendAPI client is not initialized.")
        return self._client

    async def get(self, path: str, params: dict | None = None) -> dict | list:
        response = await self.client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def post(self, path: str, json: dict | None = None) -> dict | list:
        response = await self.client.post(path, json=json)
        response.raise_for_status()
        return response.json()

    async def patch(self, path: str, json: dict | None = None, params: dict | None = None) -> dict | list:
        response = await self.client.patch(path, json=json, params=params)
        response.raise_for_status()
        return response.json()

    async def delete(self, path: str, params: dict | None = None) -> dict | list:
        response = await self.client.delete(path, params=params)
        response.raise_for_status()
        return response.json()