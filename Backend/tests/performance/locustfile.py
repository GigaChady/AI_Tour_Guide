import uuid

from locust import HttpUser, between, task


class BackendSmokeUser(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self):
        self.email = f"locust_{uuid.uuid4()}@example.com"
        self.password = "Testpass1234****"
        self.headers = {}

        with self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "name": "Locust User",
            },
            name="POST /auth/register",
            catch_response=True,
        ) as register_response:
            if register_response.status_code != 200:
                register_response.failure(f"register failed with {register_response.status_code}")
                return
            register_response.success()

        with self.client.post(
            "/auth/login",
            json={"email": self.email, "password": self.password},
            name="POST /auth/login",
            catch_response=True,
        ) as login_response:
            if login_response.status_code != 200:
                login_response.failure(f"login failed with {login_response.status_code}")
                return
            token = login_response.json()["access_token"]
            login_response.success()

        self.headers = {"Authorization": f"Bearer {token}"}

    @task(2)
    def health(self):
        self.client.get("/health", name="GET /health")

    @task(1)
    def readiness(self):
        self.client.get("/ready", name="GET /ready")

    @task(1)
    def version(self):
        self.client.get("/version", name="GET /version")

    @task(2)
    def onboarding_questions(self):
        self.client.get(
            "/user/onboarding/questions?lang=pl",
            headers=self.headers,
            name="GET /user/onboarding/questions",
        )

    @task(2)
    def narration_settings(self):
        self.client.get(
            "/user/narration-settings",
            headers=self.headers,
            name="GET /user/narration-settings",
        )
