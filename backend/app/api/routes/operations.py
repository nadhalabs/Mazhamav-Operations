from fastapi import APIRouter, Depends
from app.api.dependencies import operations_viewer
from app.models import User

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/status")
def operational_status(user: User = Depends(operations_viewer)):
    return {"status": "ready", "viewer_role": user.role}

