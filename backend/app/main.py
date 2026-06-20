import uvicorn

from .app_factory import app
from .config import load_settings


if __name__ == "__main__":
    config = load_settings()
    uvicorn.run("backend.app.main:app", host=config.bind_host, port=config.bind_port)
