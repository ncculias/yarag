from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Without init=False, BasedPyright reports missing constructor arguments.
    # https://github.com/pydantic/pydantic/issues/3753
    endpoint_url: str = Field(init=False)
    aws_access_key_id: str = Field(init=False)
    aws_secret_access_key: str = Field(init=False)
    region_name: str = "auto"
    default_bucket: str = "my-bucket"
    default_expires_in: int = 3600
    database_url: str = "sqlite:///data.db"
    jwt_secret: str = Field(init=False)
    jwt_expires_hours: int = 8
    cf_account_id: str = Field(init=False)
    cf_ai_search_instance: str = Field(init=False)
    cf_api_token: str = Field(init=False)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
