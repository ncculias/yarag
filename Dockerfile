# 後端映像：uv 官方基底（內含 Python 3.13）
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
ENV UV_LINK_MODE=copy

# 先裝依賴（獨立快取層：pyproject/lock 沒變就不重裝）
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# 再放程式碼並安裝專案本身
COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8010
CMD ["uv", "run", "--no-sync", "uvicorn", "yarag.app:app", "--host", "0.0.0.0", "--port", "8010"]
