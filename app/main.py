from fastapi import FastAPI

from app.api.routes.events import router as events_router 
from app.api.routes.reservations import router as reservations_router


app = FastAPI(title="Ticket Sales API")

app.include_router(events_router)
app.include_router(reservations_router)


@app.get("/")
def root():
    return {"status": "ok"}