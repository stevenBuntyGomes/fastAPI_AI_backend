from fastapi import HTTPException
from bson import ObjectId
from ..schemas.mypod_schema import MyPodModel
from ..db.mongo import mypod_collection


# ✅ Get MyPod by Authenticated User ID
async def get_mypod_by_user_id(user_id: str):
    result = await mypod_collection.find_one({"user_id": ObjectId(user_id)})
    if not result:
        raise HTTPException(status_code=404, detail="MyPod data not found")
    return MyPodModel(**result)


# ✅ Create or Update MyPod
async def create_or_update_mypod(user_id: str, data: MyPodModel):
    existing = await mypod_collection.find_one({"user_id": ObjectId(user_id)})
    payload = data.model_dump(by_alias=True, exclude_unset=True)
    payload["user_id"] = ObjectId(user_id)

    if existing:
        payload["updated_at"] = data.updated_at or existing.get("updated_at")
        await mypod_collection.update_one(
            {"user_id": ObjectId(user_id)},
            {"$set": payload}
        )
    else:
        await mypod_collection.insert_one(payload)

    updated = await mypod_collection.find_one({"user_id": ObjectId(user_id)})
    return MyPodModel(**updated)
