"""
Tests unitarios para los routers REST (paso 4).

Estrategia:
  - SQLite in-memory vía init_db() + create_all_tables()
  - get_session() lee db_module.AsyncSessionLocal en tiempo de ejecución,
    por lo que apunta automáticamente a la base de datos en memoria.
  - No se mockean repositorios — se usan los reales con la BD en memoria.
  - httpx.AsyncClient con ASGITransport levanta la app sin red.

Tests:
  - GET  /api/users
  - GET  /api/users/{user_id}
  - DELETE /api/users/{user_id}/memory
  - POST /api/users/{user_id}/memory
  - GET  /api/users/{user_id}/memory
  - POST /api/face/register
"""

import base64

import pytest
from httpx import ASGITransport, AsyncClient

import db as db_module
from db import create_all_tables, drop_all_tables
from main import app

# API key configurada en conftest.py
API_KEY = "test-api-key-for-unit-tests-only"
HEADERS = {"X-API-Key": API_KEY}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
async def in_memory_db():
    """BD SQLite en memoria, creada y destruida por cada test."""
    db_module.init_db("sqlite+aiosqlite:///:memory:")
    await create_all_tables()
    yield
    await drop_all_tables()
    if db_module.engine is not None:
        await db_module.engine.dispose()


@pytest.fixture
async def client():
    """Cliente HTTP apuntando a la app FastAPI via ASGI (sin red)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _create_user(
    client: AsyncClient, user_id: str = "user_test", name: str = "Test"
) -> dict:
    """Registra un usuario y devuelve el body de respuesta."""
    embedding = base64.b64encode(b"\x01" * 128).decode()
    resp = await client.post(
        "/api/face/register",
        json={"user_id": user_id, "name": name, "embedding_b64": embedding},
        headers=HEADERS,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _save_memory(
    client: AsyncClient,
    user_id: str = "user_test",
    content: str = "Le gusta el café",
    importance: int = 7,
) -> dict:
    resp = await client.post(
        f"/api/users/{user_id}/memory",
        json={"memory_type": "fact", "content": content, "importance": importance},
        headers=HEADERS,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── GET /api/users ─────────────────────────────────────────────────────────────


class TestListUsers:
    async def test_empty_list(self, client):
        resp = await client.get("/api/users", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["users"] == []
        assert body["total"] == 0

    async def test_returns_created_users(self, client):
        await _create_user(client, "user_a", "A")
        await _create_user(client, "user_b", "B")
        resp = await client.get("/api/users", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        user_ids = {u["user_id"] for u in body["users"]}
        assert user_ids == {"user_a", "user_b"}

    async def test_requires_api_key(self, client):
        resp = await client.get("/api/users")
        assert resp.status_code == 401

    async def test_response_shape(self, client):
        await _create_user(client)
        resp = await client.get("/api/users", headers=HEADERS)
        user = resp.json()["users"][0]
        assert "user_id" in user
        assert "name" in user
        assert "created_at" in user
        assert "last_seen" in user
        assert "has_face_embedding" in user
        assert user["has_face_embedding"] is True


# ── GET /api/users/{user_id} ──────────────────────────────────────────────────


class TestGetUser:
    async def test_found(self, client):
        await _create_user(client, "user_juan", "Juan")
        resp = await client.get("/api/users/user_juan", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == "user_juan"
        assert body["name"] == "Juan"

    async def test_not_found_returns_404(self, client):
        resp = await client.get("/api/users/nonexistent", headers=HEADERS)
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] is True
        assert body["error_code"] == "NOT_FOUND"

    async def test_has_face_embedding_true(self, client):
        await _create_user(client)
        resp = await client.get("/api/users/user_test", headers=HEADERS)
        assert resp.json()["has_face_embedding"] is True


# ── DELETE /api/users/{user_id}/memory ───────────────────────────────────────


class TestDeleteUserMemory:
    async def test_deletes_all_memories(self, client):
        await _create_user(client)
        await _save_memory(client, content="Mem 1")
        await _save_memory(client, content="Mem 2")

        resp = await client.delete("/api/users/user_test/memory", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["deleted"] == 2

    async def test_delete_on_empty_returns_zero(self, client):
        await _create_user(client)
        resp = await client.delete("/api/users/user_test/memory", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 0

    async def test_delete_memory_user_not_found(self, client):
        resp = await client.delete("/api/users/ghost/memory", headers=HEADERS)
        assert resp.status_code == 404

    async def test_memories_gone_after_delete(self, client):
        await _create_user(client)
        await _save_memory(client, content="Borrar esto")
        await client.delete("/api/users/user_test/memory", headers=HEADERS)

        resp = await client.get("/api/users/user_test/memory", headers=HEADERS)
        assert resp.json()["total"] == 0


# ── POST /api/users/{user_id}/memory ─────────────────────────────────────────


class TestSaveMemory:
    async def test_saves_and_returns_id(self, client):
        await _create_user(client)
        resp = await client.post(
            "/api/users/user_test/memory",
            json={"memory_type": "fact", "content": "Habla español", "importance": 8},
            headers=HEADERS,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        assert isinstance(body["id"], int)

    async def test_user_not_found_404(self, client):
        resp = await client.post(
            "/api/users/ghost/memory",
            json={"memory_type": "fact", "content": "Habla español", "importance": 5},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    async def test_private_content_rejected_422(self, client):
        await _create_user(client)
        resp = await client.post(
            "/api/users/user_test/memory",
            json={
                "memory_type": "fact",
                "content": "Su contraseña es abc123",
                "importance": 5,
            },
            headers=HEADERS,
        )
        assert resp.status_code == 422

    async def test_invalid_memory_type_422(self, client):
        await _create_user(client)
        resp = await client.post(
            "/api/users/user_test/memory",
            json={"memory_type": "invalid", "content": "Dato", "importance": 5},
            headers=HEADERS,
        )
        assert resp.status_code == 422

    async def test_importance_out_of_range_422(self, client):
        await _create_user(client)
        resp = await client.post(
            "/api/users/user_test/memory",
            json={"memory_type": "fact", "content": "Dato", "importance": 11},
            headers=HEADERS,
        )
        assert resp.status_code == 422

    async def test_invalid_expires_at_422(self, client):
        await _create_user(client)
        resp = await client.post(
            "/api/users/user_test/memory",
            json={
                "memory_type": "fact",
                "content": "Dato",
                "importance": 5,
                "expires_at": "not-a-date",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 422

    async def test_valid_expires_at_accepted(self, client):
        await _create_user(client)
        resp = await client.post(
            "/api/users/user_test/memory",
            json={
                "memory_type": "preference",
                "content": "Prefiere la tarde",
                "importance": 6,
                "expires_at": "2027-12-31T23:59:59",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201

    async def test_default_importance_5(self, client):
        await _create_user(client)
        resp = await client.post(
            "/api/users/user_test/memory",
            json={"content": "Sin importancia explícita"},
            headers=HEADERS,
        )
        assert resp.status_code == 201


# ── GET /api/users/{user_id}/memory ──────────────────────────────────────────


class TestGetMemory:
    async def test_empty_list(self, client):
        await _create_user(client)
        resp = await client.get("/api/users/user_test/memory", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == "user_test"
        assert body["memories"] == []
        assert body["total"] == 0

    async def test_returns_saved_memories(self, client):
        await _create_user(client)
        await _save_memory(client, content="Dato 1", importance=8)
        await _save_memory(client, content="Dato 2", importance=6)
        resp = await client.get("/api/users/user_test/memory", headers=HEADERS)
        body = resp.json()
        assert body["total"] == 2

    async def test_ordered_by_importance_desc(self, client):
        await _create_user(client)
        await _save_memory(client, content="Baja", importance=3)
        await _save_memory(client, content="Alta", importance=9)
        resp = await client.get("/api/users/user_test/memory", headers=HEADERS)
        mems = resp.json()["memories"]
        importances = [m["importance"] for m in mems]
        assert importances == sorted(importances, reverse=True)

    async def test_user_not_found_404(self, client):
        resp = await client.get("/api/users/ghost/memory", headers=HEADERS)
        assert resp.status_code == 404

    async def test_memory_item_shape(self, client):
        await _create_user(client)
        await _save_memory(client)
        resp = await client.get("/api/users/user_test/memory", headers=HEADERS)
        item = resp.json()["memories"][0]
        assert "id" in item
        assert "memory_type" in item
        assert "content" in item
        assert "importance" in item
        assert "timestamp" in item
        assert "expires_at" in item


# ── POST /api/face/register ───────────────────────────────────────────────────


class TestFaceRegister:
    def _payload(self, user_id: str = "user_new", name: str = "New") -> dict:
        embedding = base64.b64encode(b"\x02" * 128).decode()
        return {"user_id": user_id, "name": name, "embedding_b64": embedding}

    async def test_register_creates_user(self, client):
        resp = await client.post(
            "/api/face/register", json=self._payload(), headers=HEADERS
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["user_id"] == "user_new"
        assert body["name"] == "New"

    async def test_duplicate_user_id_409(self, client):
        payload = self._payload()
        await client.post("/api/face/register", json=payload, headers=HEADERS)
        resp = await client.post("/api/face/register", json=payload, headers=HEADERS)
        assert resp.status_code == 409

    async def test_invalid_base64_400(self, client):
        resp = await client.post(
            "/api/face/register",
            json={
                "user_id": "user_b64",
                "name": "B64",
                "embedding_b64": "!!!invalid!!!",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 400

    async def test_user_appears_in_list(self, client):
        await client.post("/api/face/register", json=self._payload(), headers=HEADERS)
        resp = await client.get("/api/users", headers=HEADERS)
        user_ids = [u["user_id"] for u in resp.json()["users"]]
        assert "user_new" in user_ids

    async def test_missing_fields_422(self, client):
        resp = await client.post(
            "/api/face/register",
            json={"user_id": "user_x"},
            headers=HEADERS,
        )
        assert resp.status_code == 422

    async def test_requires_api_key(self, client):
        resp = await client.post("/api/face/register", json=self._payload())
        assert resp.status_code == 401
