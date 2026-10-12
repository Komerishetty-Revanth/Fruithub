"""manual owner UPI payments

Revision ID: 4f82b6a3c1d0
Revises: d7b4c6a9e215
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4f82b6a3c1d0"
down_revision: Union[str, Sequence[str], None] = "d7b4c6a9e215"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("upi_vpa", sa.String(length=128), nullable=True))
    op.execute("ALTER TYPE payment_method ADD VALUE IF NOT EXISTS 'UPI_MANUAL'")


def downgrade() -> None:
    op.drop_column("stores", "upi_vpa")
