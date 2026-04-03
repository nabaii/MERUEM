import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.db.session import get_db

from app.processing.legibility import LegibilityAuditor

# In MERUEM, api routes are organized using a router
router = APIRouter()

@router.post("/audit")
async def run_legibility_audit(
    video: UploadFile = File(...),
    caption: str = Form(""),
    primary_keyword: str = Form(""),
    secondary_keywords: str = Form(""), # Comma separated list
    db: Session = Depends(get_db)
):
    """
    Runs the TikTok Algorithmic Legibility Auditor.
    Accepts video file, caption text, and keywords.
    """
    try:
        # Create temp file
        temp_dir = "raw_data/tiktok_audits"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, video.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
            
        secondary_keys = [k.strip() for k in secondary_keywords.split(",")] if secondary_keywords else []
        
        auditor = LegibilityAuditor()
        report = auditor.run_audit(
            video_path=file_path,
            caption=caption,
            primary_keyword=primary_keyword,
            secondary_keywords=secondary_keys
        )
        
        return {"status": "success", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up video manually or leave it for later analysis
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

@router.post("/webhook")
async def tiktok_webhook(payload: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Webhook endpoint to receive real-time metric updates or post published events from TikTok Business API.
    """
    # Sample payload processing for Sprint 1
    event_type = payload.get("event")
    
    if event_type == "video_publish":
        post_id = payload.get("video_id")
        # Start metric fetching
        from app.tasks.tiktok import fetch_tiktok_video_metrics
        background_tasks.add_task(fetch_tiktok_video_metrics, post_id)
        
    return {"status": "ok"}

@router.post("/onboarding")
async def onboard_tiktok_client(business_account_id: str, db: Session = Depends(get_db)):
    """
    Admin endpoint to onboard a TikTok client and set their Business Account ID.
    Will eventually trigger initial video backfill.
    """
    # Just a placeholder for sprint 1 integration
    return {"status": "onboarded", "business_account_id": business_account_id}
