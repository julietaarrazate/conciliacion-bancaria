from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, accounts, statements, reconciliations

app = FastAPI(
    title="Sistema de Conciliación Bancaria",
    description="API para conciliación bancaria automatizada",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
app.include_router(statements.router, prefix="/statements", tags=["statements"])
app.include_router(reconciliations.router, prefix="/reconciliations", tags=["re