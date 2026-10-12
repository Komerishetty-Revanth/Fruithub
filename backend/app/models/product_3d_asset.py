import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AssetStatus(str, enum.Enum):
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"


class AssetType(str, enum.Enum):
    LAYERED_IMAGE = "LAYERED_IMAGE"   # current local method
    GLB = "GLB"                       # future real 3D model


class Product3DAsset(Base):
    __tablename__ = "product_3d_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, name="asset_type"), default=AssetType.LAYERED_IMAGE
    )
    status: Mapped[AssetStatus] = mapped_column(
        Enum(AssetStatus, name="asset_status"), default=AssetStatus.PENDING
    )
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )