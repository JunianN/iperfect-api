from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

conn_string = os.getenv("CONN_STRING")
client = MongoClient(conn_string)
db = client["iperfect-db"]
collection = db["function-code"]


class Item(BaseModel):
    code: str


def serialize_dict(document):
    document["_id"] = str(document["_id"])
    return document


@app.get("/")
async def read_root():
    return {"message": "Welcome to the Iperfect API"}


@app.post("/code/")
async def create_code(item: Item):
    code = item.model_dump()
    collection.insert_one(code)
    return [serialize_dict(code)]


@app.get("/code/")
async def read_code():
    code = list(collection.find())
    return [serialize_dict(item) for item in code]

def main(request):
    return app(request)