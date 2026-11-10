from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import auth, chains, dashboard, documents, employees, notifications, review, settings as settings_router

# Dev/test convenience only: creates any tables that don't exist yet, but never
# alters an existing one. Real deployments manage schema changes with Alembic
# instead (`alembic upgrade head`) — see migrations/.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="DocuFlow")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        accept = request.headers.get("accept", "")
        if "text/html" in accept or "*/*" in accept:
            return RedirectResponse(url="/auth/login", status_code=303)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(chains.router)
app.include_router(documents.router)
app.include_router(employees.router)
app.include_router(notifications.router)
app.include_router(review.router)
app.include_router(settings_router.router)
