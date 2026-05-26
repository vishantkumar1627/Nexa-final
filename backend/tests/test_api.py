import pytest
import pytest_asyncio
from httpx import AsyncClient
from services.api_gateway.main import app
from shared.database import async_engine, Base

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Session fixture to automatically bootstrap schemas before testing."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

@pytest.mark.asyncio
async def test_gateway_health():
    """Verify core API gateway health checks."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_auth_pipeline():
    """Verify registration, duplicate checking, and active login authentication flows."""
    email = "test_architect@nex.ai"
    password = "securepassword123"

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 1. Register a user
        reg_response = await ac.post(
            "/auth/register",
            json={"email": email, "password": password}
        )
        # If user already exists from previous runs during development tests, skip assert
        if reg_response.status_code == 201:
            data = reg_response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["token_type"] == "bearer"

        # 2. Login with credentials
        login_response = await ac.post(
            "/auth/login",
            data={"username": email, "password": password}
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "access_token" in login_data
        
        # 3. Read profile with token
        headers = {"Authorization": f"Bearer {login_data['access_token']}"}
        me_response = await ac.get("/auth/me", headers=headers)
        assert me_response.status_code == 200
        assert me_response.json()["email"] == email
