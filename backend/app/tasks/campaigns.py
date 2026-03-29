"""
Celery tasks for campaign export generation.
"""

from __future__ import annotations

import logging
import uuid

from app.core.celery_app import celery_app
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.campaigns.generate_export_task", queue="default")
def generate_export_task(self, export_id: str) -> dict:
    """
    Generate a campaign audience export file (Meta / Twitter / CSV).

    1. Load the CampaignExport row and mark it processing
    2. Fetch all SocialProfiles in the campaign audiences
    3. Generate the appropriate CSV
    4. Save to local disk (file_key = exports/<export_id>.<format>.csv)
    5. Mark export ready, fire in-app + email notifications
    """
    from app.db.models.campaign_export import CampaignExport, ExportFormat, ExportStatus
    from app.db.models.campaign_audience import CampaignAudience
    from app.db.models.social_profile import SocialProfile
    from app.db.models.account import Account
    from app.export.csv_generator import (
        generate_meta_csv,
        generate_twitter_csv,
        generate_generic_csv,
        save_export_file,
    )
    from app.notifications.in_app import notify_export_ready, notify_export_failed
    from app.notifications.email import send_export_ready, send_export_failed

    eid = uuid.UUID(export_id)

    with SessionLocal() as db:
        export = db.get(CampaignExport, eid)
        if not export:
            logger.error("Export %s not found", export_id)
            return {"status": "not_found"}

        export.status = ExportStatus.processing
        db.commit()

        campaign = export.campaign
        owner_id = campaign.owner_id

        try:
            # Collect profile IDs from CampaignAudience
            profile_ids = [
                row.profile_id
                for row in db.query(CampaignAudience).filter(
                    CampaignAudience.campaign_id == campaign.id
                ).all()
            ]

            profiles = (
                db.query(SocialProfile)
                .filter(SocialProfile.id.in_(profile_ids))
                .all()
            ) if profile_ids else []

            fmt = export.format
            if fmt == ExportFormat.meta:
                data = generate_meta_csv(profiles)
                ext = "meta.csv"
            elif fmt == ExportFormat.twitter:
                data = generate_twitter_csv(profiles)
                ext = "twitter.csv"
            else:
                data = generate_generic_csv(profiles)
                ext = "csv"

            file_key = f"{export_id}.{ext}"
            save_export_file(data, file_key)

            export.status = ExportStatus.ready
            export.profile_count = len(profiles)
            export.file_key = file_key
            db.commit()

            # Notifications
            if owner_id:
                notify_export_ready(db, owner_id, campaign.name, eid)
                owner = db.get(Account, owner_id)
                if owner and owner.email:
                    send_export_ready(owner.email, campaign.name, export_id)

            logger.info("Export %s ready — %d profiles", export_id, len(profiles))
            return {"status": "ready", "profile_count": len(profiles)}

        except Exception as exc:
            error_msg = str(exc)
            logger.exception("Export %s failed: %s", export_id, error_msg)
            export.status = ExportStatus.failed
            export.error_message = error_msg[:500]
            db.commit()

            if owner_id:
                notify_export_failed(db, owner_id, campaign.name, error_msg)
                owner = db.get(Account, owner_id)
                if owner and owner.email:
                    send_export_failed(owner.email, campaign.name, error_msg)

            return {"status": "failed", "error": error_msg}
