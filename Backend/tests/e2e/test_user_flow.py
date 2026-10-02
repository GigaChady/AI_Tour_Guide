import asyncio
import json
import uuid

import httpx
import pytest
import websockets


BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/route/ws"


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_user_flow_with_preferences_and_mocked_ai_response():
    email = f"e2e_{uuid.uuid4()}@example.com"
    password = "Testpass1"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        health = await client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        register = await client.post(
            "/auth/register",
            json={"email": email, "password": password, "name": "E2E User"},
        )
        assert register.status_code == 200, register.text
        register_tokens = register.json()
        assert register_tokens["access_token"]
        assert register_tokens["refresh_token"]

        login = await client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        assert login.status_code == 200, login.text
        access_token = login.json()["access_token"]
        headers = _auth_headers(access_token)

        questions = await client.get("/user/onboarding/questions?lang=pl", headers=headers)
        assert questions.status_code == 200, questions.text
        question_keys = {item["key"] for item in questions.json()["items"]}
        assert {"gender", "interests"} <= question_keys

        answers = await client.post(
            "/user/onboarding/answers",
            headers=headers,
            json={
                "items": [
                    {"question_key": "gender", "answer_key": "male"},
                    {"question_key": "interests", "answer_keys": ["history", "nature"]},
                ]
            },
        )
        assert answers.status_code == 204, answers.text

        saved_questions = await client.get("/user/onboarding/questions?lang=pl", headers=headers)
        assert saved_questions.status_code == 200, saved_questions.text
        selected = saved_questions.json()["selected_answers"]
        assert selected["gender"] == "male"
        assert set(selected["interests"]) == {"history", "nature"}

        narration_settings = {
            "language": "pl",
            "pitch": 50,
            "speed": 5,
            "detail_level": "normal",
            "auto_play": False,
        }
        save_settings = await client.post(
            "/user/narration-settings",
            headers=headers,
            json=narration_settings,
        )
        assert save_settings.status_code == 204, save_settings.text

        get_settings = await client.get("/user/narration-settings", headers=headers)
        assert get_settings.status_code == 200, get_settings.text
        assert get_settings.json() == narration_settings

        dashboard = await client.get("/web/dashboard", headers=headers)
        assert dashboard.status_code == 200, dashboard.text

    async with websockets.connect(WS_URL, open_timeout=10) as websocket:
        await websocket.send(json.dumps({"token": access_token}))

        session_message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=10))
        assert session_message["type"] == "session_start"
        assert session_message["session_id"]

        await websocket.send(json.dumps({"lat": 51.1079, "lng": 17.0385, "ai": True}))

        pois_message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=20))
        assert pois_message["type"] == "pois"
        assert pois_message["data"]

