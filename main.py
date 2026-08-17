from fastapi import FastAPI

import database
import models
from routers import menu, orders, reservations

app = FastAPI()

models.Base.metadata.create_all(bind=database.engine)


@app.get("/")
def root():
    return {"status": "backend is alive"}


app.include_router(menu.router)
app.include_router(orders.router)
app.include_router(reservations.router)