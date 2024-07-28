from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from typing import List
from models import PyObjectId, UDF, Configs
from bson import ObjectId

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
udf_collection = db["function-code"]
config_collection = db["config"]


@app.post("/udf/", response_model=UDF)
async def create_udf(udf: UDF):
    udf_dict = udf.model_dump(by_alias=True)
    result = udf_collection.insert_one(udf_dict)
    udf_dict["_id"] = result.inserted_id
    return udf_dict


@app.get("/udf/{udf_id}", response_model=UDF)
async def get_udf(udf_id: str):
    if (udf := udf_collection.find_one({"_id": ObjectId(udf_id)})) is not None:
        return udf
    raise HTTPException(status_code=404, detail="UDF not found")


@app.get("/udf/", response_model=List[UDF])
async def get_all_udfs():
    udfs = []
    for udf in udf_collection.find():
        udf["_id"] = str(udf["_id"])
        udfs.append(udf)
    return udfs


@app.put("/udf/{udf_id}", response_model=UDF)
async def update_udf(udf_id: str, udf: UDF):
    udf_dict = udf.model_dump(by_alias=True)
    udf_dict.pop("_id", None)
    if not udf_collection.find_one({"_id": ObjectId(udf_id)}):
        raise HTTPException(status_code=404, detail="Udf not found")
    udf_collection.update_one({"_id": ObjectId(udf_id)}, {"$set": udf_dict})
    updated_udf = udf_collection.find_one({"_id": ObjectId(udf_id)})
    updated_udf["_id"] = str(updated_udf["_id"])
    return UDF(**updated_udf)


@app.post("/config/", response_model=Configs)
async def create_config(config: Configs):
    config_dict = config.model_dump(by_alias=True)
    if not all(udf_collection.find_one({"_id": pid}) for pid in config.udf_ids):
        raise HTTPException(status_code=404, detail="One or more UDF not found")
    result = config_collection.insert_one(config_dict)
    config_dict["_id"] = result.inserted_id
    return config_dict


@app.get("/config/{config_id}", response_model=Configs)
async def get_config(config_id: str):
    if (config := config_collection.find_one({"_id": ObjectId(config_id)})) is not None:
        config["_id"] = str(config["_id"])
        config["udf_ids"] = [str(pid) for pid in config["udf_ids"]]
        return config
    raise HTTPException(status_code=404, detail="Config not found")


@app.get("/config/", response_model=List[Configs])
async def get_all_configs():
    configs = []
    for config in config_collection.find():
        config["_id"] = str(config["_id"])
        config["udf_ids"] = [str(pid) for pid in config["udf_ids"]]
        configs.append(config)
    return configs


@app.get("/config/{config_id}/details")
async def get_config_details(config_id: str):
    if (config := config_collection.find_one({"_id": ObjectId(config_id)})) is not None:
        udfs = list(udf_collection.find({"_id": {"$in": config["udf_ids"]}}))
        for udf in udfs:
            udf["_id"] = str(udf["_id"])
        config["udfs"] = udfs
        config["_id"] = str(config["_id"])
        config["udf_ids"] = [str(pid) for pid in config["udf_ids"]]
        return config
    raise HTTPException(status_code=404, detail="Config not found")


@app.post("/udf/{config_id}/add", response_model=Configs)
async def create_udf_and_add_to_config(config_id: str, udf: UDF):
    udf_dict = udf.model_dump(by_alias=True)
    result = udf_collection.insert_one(udf_dict)
    udf_dict["_id"] = result.inserted_id
    new_udf = UDF(**udf_dict)

    if (config := config_collection.find_one({"_id": ObjectId(config_id)})) is not None:
        config_collection.update_one(
            {"_id": ObjectId(config_id)}, {"$push": {"udf_ids": new_udf.id}}
        )
        config["udf_ids"].append(new_udf.id)
        config["_id"] = str(config["_id"])
        config["udf_ids"] = [str(pid) for pid in config["udf_ids"]]
        return config

    raise HTTPException(status_code=404, detail="config not found")


# class Formula(BaseModel):
#     name: str
#     function: UDF

# class Group(BaseModel):
#     name: str
#     formulas: List[Formula]

# class Config(BaseModel):
#     name: str
#     groups: List[Group]

# def serialize_dict(document):
#     document["_id"] = str(document["_id"])
#     return document


# @app.get("/")
# async def read_root():
#     return {"message": "Welcome to the Iperfect API"}


# @app.post("/code/")
# async def create_code(item: UDF):
#     code = item.model_dump()
#     collection.insert_one(code)
#     return [serialize_dict(code)]


# @app.get("/code/")
# async def read_code():
#     code = list(collection.find())
#     return [serialize_dict(item) for item in code]


def main(request):
    return app(request)
