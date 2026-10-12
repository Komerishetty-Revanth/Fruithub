import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(50), default="Home")

    # Step 1 (required): the pin chosen on the map
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    location_label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    location_source: Mapped[str] = mapped_column(
        String(20), default="MAP_PIN", server_default="MAP_PIN"
    )  # MAP_PIN, GPS or SEARCH

    # Step 2 (optional until checkout): the main address, added later
    line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    landmark: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )