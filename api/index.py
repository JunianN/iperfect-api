from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from typing import List
from models import PyObjectId, UDF, Configs, UdfGroup, Factory
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
factory_collection = db["factory"]
    
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
    for group in config.groups:
        if not all(udf_collection.find_one({"_id": ObjectId(pid)}) for pid in group.udf_ids):
            raise HTTPException(status_code=404, detail="One or more UDFs not found in group")
    result = config_collection.insert_one(config_dict)
    config_dict["_id"] = result.inserted_id
    return config_dict


@app.get("/config/{config_id}", response_model=Configs)
async def get_config(config_id: str):
    if (config := config_collection.find_one({"_id": ObjectId(config_id)})) is not None:
        config["_id"] = str(config["_id"])
        for group in config["groups"]:
            group["udf_ids"] = [str(pid) for pid in group["udf_ids"]]
        return config
    raise HTTPException(status_code=404, detail="Config not found")


@app.get("/config/", response_model=List[Configs])
async def get_all_configs():
    configs = []
    for config in config_collection.find():
        config["_id"] = str(config["_id"])
        for group in config["groups"]:
            group["udf_ids"] = [str(pid) for pid in group["udf_ids"]]
        configs.append(config)
    return configs


@app.get("/config/{config_id}/details")
async def get_config_details(config_id: str):
    if (config := config_collection.find_one({"_id": ObjectId(config_id)})) is not None:
        detailed_groups = []
        for group in config["groups"]:
            udfs = list(udf_collection.find({"_id": {"$in": group["udf_ids"]}}))
            for udf in udfs:
                udf["_id"] = str(udf["_id"])
            detailed_groups.append({"name": group["name"], "udfs": udfs})
        config["groups"] = detailed_groups
        config["_id"] = str(config["_id"])
        return config
    raise HTTPException(status_code=404, detail="Config not found")


@app.post("/configs/{config_id}/groups/{group_name}/udfs", response_model=Configs)
async def create_udf_and_add_to_config(config_id: str,  group_name: str, udf: UDF = Body(...)):
    udf_dict = udf.model_dump(by_alias=True)
    result = udf_collection.insert_one(udf_dict)
    udf_dict["_id"] = result.inserted_id
    new_udf = UDF(**udf_dict)

    if (config := config_collection.find_one({"_id": ObjectId(config_id)})) is not None:
        group_found = False
        for group in config["groups"]:
            if group["name"] == group_name:
                group["udf_ids"].append(new_udf.id)
                group_found = True
                break
        if not group_found:
            config["groups"].append({"name": group_name, "udf_ids": [new_udf.id]})

        config_collection.update_one({"_id": ObjectId(config_id)}, {"$set": {"groups": config["groups"]}})
        config["_id"] = str(config["_id"])
        for group in config["groups"]:
            group["udf_ids"] = [str(pid) for pid in group["udf_ids"]]
        return Configs(**config)

    raise HTTPException(status_code=404, detail="Config not found")

@app.post("/configs/{config_id}/groups", response_model=Configs)
async def create_group_in_config(config_id: str, group: UdfGroup):
    if (config := config_collection.find_one({"_id": ObjectId(config_id)})) is not None:
        config["groups"].append(group.model_dump())

        config_collection.update_one({"_id": ObjectId(config_id)}, {"$set": {"groups": config["groups"]}})

        config["_id"] = str(config["_id"])
        for g in config["groups"]:
            g["udf_ids"] = [str(pid) for pid in g["udf_ids"]]

        return Configs(**config)

    raise HTTPException(status_code=404, detail="Config not found")

@app.post("/factory", response_model=Factory)
async def create_factory(factory: Factory):
    factory_data = factory.model_dump(by_alias=True)
    factory_collection.insert_one(factory_data)
    factory_data["_id"] = str(factory_data["_id"])
    return Factory(**factory_data)

@app.put("/factory/{factory_id}/config/{config_id}", response_model=Factory)
async def assign_config_to_factory(factory_id: str, config_id: str):
    factory = factory_collection.find_one({"_id": ObjectId(factory_id)})
    config = config_collection.find_one({"_id": ObjectId(config_id)})

    if not factory:
        raise HTTPException(status_code=404, detail="Factory not found")
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    factory["config_id"] = ObjectId(config_id)
    factory_collection.update_one({"_id": ObjectId(factory_id)}, {"$set": {"config_id": ObjectId(config_id)}})
    
    factory["_id"] = str(factory["_id"])
    factory["config_id"] = str(factory["config_id"])
    return Factory(**factory)

@app.get("/factory/{factory_id}", response_model=Factory)
async def get_factory(factory_id: str):
    factory = factory_collection.find_one({"_id": ObjectId(factory_id)})
    if not factory:
        raise HTTPException(status_code=404, detail="Factory not found")
    
    factory["_id"] = str(factory["_id"])
    if factory["order_id"]:
        factory["order_id"] = str(factory["order_id"])
    return Factory(**factory)

# @app.get("/factory", response_model=List[Factory])
# async def get_all_factorys():
#     factorys = []
#     for factory in factory_collection.find():
#         factory["_id"] = str(factory["_id"])
#         if factory.get("order_id"):
#             factory["order_id"] = str(factory["order_id"])
#         factorys.append(Factory(**factory))
#     return factorys

@app.get("/factories")
async def get_all_factories():
    factories = []
    for factory in factory_collection.find():
        factory["_id"] = str(factory["_id"])
        if factory.get("config_id"):
            config = config_collection.find_one({"_id": ObjectId(factory["config_id"])})
            if config:
                config["_id"] = str(config["_id"])
                detailed_groups = []
                for group in config["groups"]:
                    udfs = list(udf_collection.find({"_id": {"$in": group["udf_ids"]}}))
                    for udf in udfs:
                        udf["_id"] = str(udf["_id"])
                    detailed_groups.append({"name": group["name"], "udfs": udfs})
                config["groups"] = detailed_groups
                factory["config"] = config
            else:
                raise HTTPException(status_code=404, detail="Config not found")
        else:
            raise HTTPException(status_code=404, detail="Config_id not found")
        factories.append(factory)
    return factories

    # if (config := config_collection.find_one({"_id": ObjectId(config_id)})) is not None:
    #     detailed_groups = []
    #     for group in config["groups"]:
    #         udfs = list(udf_collection.find({"_id": {"$in": group["udf_ids"]}}))
    #         for udf in udfs:
    #             udf["_id"] = str(udf["_id"])
    #         detailed_groups.append({"name": group["name"], "udfs": udfs})
    #     config["groups"] = detailed_groups
    #     config["_id"] = str(config["_id"])
    #     return config
    # raise HTTPException(status_code=404, detail="Config not found")