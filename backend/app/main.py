import uvicorn

from .app_factory import create_application
from .config import load_settings

app = create_application()


if __name__ == "__main__":
    config = load_settings()
    uvicorn.run("backend.app.main:app", host=config.bind_host, port=config.bind_port)
