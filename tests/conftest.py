import os

os.environ.setdefault("ENDPOINT_URL", "https://test.r2.example.com")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-secret")
os.environ.setdefault("DEFAULT_BUCKET", "test-bucket")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("CF_ACCOUNT_ID", "test-account")
os.environ.setdefault("CF_AI_SEARCH_INSTANCE", "test-instance")
os.environ.setdefault("CF_API_TOKEN", "test-cf-token")
