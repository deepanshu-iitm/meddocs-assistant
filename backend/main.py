from fastapi import FastAPI

app = FastAPI(title="MedDocs Assistant Backend")

@app.get("/")
def read_root():
    return {"message": "Backend is running successfully!"}