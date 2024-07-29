from pydantic import BaseModel, Field
from typing import List, Optional, Any
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: Any, field) -> ObjectId:
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError('Invalid objectid')

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema: dict[str, Any]) -> None:
        field_schema.update(type='string')

class Input(BaseModel):
    name: str
    value: str
    default_value: int

class UDF(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    name: str
    output_type: str
    inputs: List[Input]
    code: str

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str
        }

class UdfGroup(BaseModel):
    name: str
    udf_ids: List[str]

class Configs(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    name: str
    # udf_ids: List[PyObjectId] = Field(default_factory=list)
    groups: List[UdfGroup]

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str
        }
