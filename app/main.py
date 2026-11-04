from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import auth, chains, dashboard, documents, employees, review, settings as settings_router

# Dev/test convenience only: creates any tables that don't exist yet, but never
# alters an existing one. Real deployments manage schema changes with Alembic
# instead (`alembic upgrade head`) — see migrations/.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="DocuFlow")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(chains.router)
app.include_router(documents.router)
app.include_router(employees.router)
app.include_router(review.router)
app.include_router(settings_router.router)
