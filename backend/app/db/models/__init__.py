# Import all models here so Alembic can discover them via Base.metadata
from app.db.models.account import Account  # noqa: F401
from app.db.models.campaign import Campaign  # noqa: F401
from app.db.models.campaign_audience import CampaignAudience  # noqa: F401
from app.db.models.campaign_export import CampaignExport  # noqa: F401
from app.db.models.cluster import Cluster  # noqa: F401
from app.db.models.cluster_metric import ClusterMetric  # noqa: F401
from app.db.models.collection_job import CollectionJob  # noqa: F401
from app.db.models.notification import Notification  # noqa: F401
from app.db.models.post import Post  # noqa: F401
from app.db.models.profile_interest import ProfileInterest  # noqa: F401
from app.db.models.profile_link import ProfileLink  # noqa: F401
from app.db.models.social_profile import SocialProfile  # noqa: F401
from app.db.models.unified_user import UnifiedUser  # noqa: F401
