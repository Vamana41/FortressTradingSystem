from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates
from pathlib import Path

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

web_router = APIRouter()

@web_router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@web_router.get("/symbols", response_class=HTMLResponse)
async def symbols(request: Request):
    return templates.TemplateResponse("symbols.html", {"request": request})

@web_router.get("/risk", response_class=HTMLResponse)
async def risk(request: Request):
    return templates.TemplateResponse("risk.html", {"request": request})

@web_router.get("/timeframes", response_class=HTMLResponse)
async def timeframes(request: Request):
    return templates.TemplateResponse("timeframes.html", {"request": request})

@web_router.get("/performance", response_class=HTMLResponse)
async def performance(request: Request):
    return templates.TemplateResponse("performance.html", {"request": request})

@web_router.get("/scanner", response_class=HTMLResponse)
async def scanner(request: Request):
    return templates.TemplateResponse("scanner.html", {"request": request})