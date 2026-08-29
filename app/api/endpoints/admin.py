from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from app.services.provider_sync import ProviderSyncService

router = APIRouter()

class SyncRequest(BaseModel):
    provider: str

class SyncResponse(BaseModel):
    success: bool
    reason: Optional[str] = None
    errors: Optional[List[str]] = None
    counts: Optional[Dict[str, int]] = None
    source_counts: Optional[Dict[str, int]] = None

@router.post("/transport/sync", response_model=SyncResponse)
def sync_transport_data(request: SyncRequest, db: Session = Depends(get_db)):
    try:
        result = ProviderSyncService.sync(db, request.provider)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "reason": result.get("reason"),
                    "errors": result.get("errors", [])
                }
            )
            
        return SyncResponse(
            success=True,
            counts=result.get("counts"),
            source_counts=result.get("source_counts")
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during sync: {str(e)}"
        )
