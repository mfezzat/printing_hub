from fastapi import APIRouter
router = APIRouter(prefix="/catalog", tags=["catalog"])
@router.get("/paper-types")
async def get_papers(): return []
