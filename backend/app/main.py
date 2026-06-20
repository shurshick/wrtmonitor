import uvicorn

from .app_factory import app, register_routers
from .config import load_settings

register_routers()


if __name__ == "__main__":
    config = load_settings()
    uvicorn.run("backend.app.main:app", host=config.bind_host, port=config.bind_port)
