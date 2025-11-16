import sys
import asyncio
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from fortress.core.logging import get_logger
from fortress.core.events import EventType
from fortress.core.event_bus import subscribe_to_event, start_event_consumers
from .state import get_event_bus, get_brain
from .routers.api import api_router
from .routers.web import web_router
from .routers.ws import ws_manager, ws_router
from .performance_monitor import performance_monitor

logger = get_logger(__name__)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

templates_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

app = FastAPI(title="Fortress Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=str(templates_dir))

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(api_router, prefix="/api")
app.include_router(web_router)
app.include_router(ws_router)

async def _on_event(e):
    payload: Dict[str, Any] = {
        "event_id": e.event_id,
        "event_type": e.event_type,
        "priority": e.priority,
        "timestamp": e.timestamp.isoformat(),
        "source": e.source,
        "data": e.data,
    }
    await ws_manager.broadcast_json(payload)
    return True

@app.on_event("startup")
async def on_startup():
    bus = get_event_bus()
    await bus.connect()
    await subscribe_to_event(EventType.SIGNAL_RECEIVED, _on_event, bus_name="fortress")
    await subscribe_to_event(EventType.POSITION_UPDATED, _on_event, bus_name="fortress")
    await subscribe_to_event(EventType.RISK_CHECK_PASSED, _on_event, bus_name="fortress")
    await subscribe_to_event(EventType.RISK_CHECK_FAILED, _on_event, bus_name="fortress")
    await subscribe_to_event(EventType.ERROR_OCCURRED, _on_event, bus_name="fortress")
    await start_event_consumers("fortress")
    
    # Start performance monitoring
    await performance_monitor.start_monitoring(interval_seconds=30)
    
    brain = get_brain()
    if brain:
        logger.info("Dashboard connected to brain", brain_id=brain.brain_id)

@app.on_event("shutdown")
async def on_shutdown():
    # Stop performance monitoring
    await performance_monitor.stop_monitoring()
    ws_manager.clear()

def create_app() -> FastAPI:
    return app