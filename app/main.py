from fastapi import FastAPI

app = FastAPI(title="Ticket Sales API")


@app.get("/")
def root():
    return {"message": "Ticket Sales API is running"}