from pydantic_settings import BaseSettings, SettingsConfigDict


class MinioConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MINIO_",
        case_sensitive=False,
        extra="ignore",
    )

    endpoint: str = "localhost:9000"
    public_endpoint: str | None = None
    access_key: str = "admin"
    secret_key: str = "admin12345"
    bucket: str = "poi-images"
    secure: bool = False
