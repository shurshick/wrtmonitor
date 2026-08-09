from fastapi import APIRouter

from .routes_auth import (
    router as routes_auth_router,
)
from .routes_account import (
    router as routes_account_router,
)
from .routes_device import router as routes_device_router
from .routes_clients import (
    router as routes_clients_router,
)
from .routes_commands import (
    router as routes_commands_router,
)
from .routes_lifecycle import (
    router as routes_lifecycle_router,
)
from .routes_setup import router as routes_setup_router
from .routes_fleet import router as routes_fleet_router
from .routes_events import router as routes_events_router

router = APIRouter()
router.include_router(routes_auth_router)
router.include_router(routes_account_router)
router.include_router(routes_device_router)
router.include_router(routes_clients_router)
router.include_router(routes_commands_router)
router.include_router(routes_lifecycle_router)
router.include_router(routes_setup_router)
router.include_router(routes_fleet_router)
router.include_router(routes_events_router)
