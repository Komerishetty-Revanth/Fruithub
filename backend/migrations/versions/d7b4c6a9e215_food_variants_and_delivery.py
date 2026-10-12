"""food product fields, variants, and customer-arranged delivery

Revision ID: d7b4c6a9e215
Revises: 61870b76defc
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7b4c6a9e215"
down_revision: Union[str, Sequence[str], None] = "61870b76defc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("product_type", sa.String(length=20), server_default="FRUIT", nullable=False),
    )
    op.add_column("stores", sa.Column("fssai_number", sa.String(length=50), nullable=True))
    op.add_column("products", sa.Column("ingredients", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("allergens", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("is_veg", sa.Boolean(), nullable=True))
    op.add_column("products", sa.Column("shelf_life_days", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("best_before", sa.Date(), nullable=True))
    op.add_column("products", sa.Column("storage_note", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("sugar_info", sa.Text(), nullable=True))
    op.add_column(
        "products",
        sa.Column("is_made_to_order", sa.Boolean(), server_default=sa.false(), nullable=False),
    )

    op.create_table(
        "product_variants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("size_value", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("size_unit", sa.String(length=20), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("discount_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("stock_quantity", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint("size_value >= 0", name="ck_variant_size_nonneg"),
        sa.CheckConstraint("price >= 0", name="ck_variant_price_nonneg"),
        sa.CheckConstraint(
            "discount_price IS NULL OR (discount_price >= 0 AND discount_price <= price)",
            name="ck_variant_discount_valid",
        ),
        sa.CheckConstraint("stock_quantity >= 0", name="ck_variant_stock_nonneg"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "label", name="uq_product_variant_label"),
    )
    op.create_index(
        op.f("ix_product_variants_product_id"), "product_variants", ["product_id"], unique=False
    )

    op.add_column("cart_items", sa.Column("variant_id", sa.UUID(), nullable=True))
    op.add_column("cart_items", sa.Column("variant_label", sa.String(length=50), nullable=True))
    op.add_column("cart_items", sa.Column("variant_price", sa.Numeric(precision=10, scale=2), nullable=True))
    op.drop_constraint("uq_cart_product", "cart_items", type_="unique")
    op.create_foreign_key(
        "fk_cart_items_variant_id_product_variants",
        "cart_items", "product_variants", ["variant_id"], ["id"], ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_cart_product_variant", "cart_items", ["cart_id", "product_id", "variant_id"]
    )

    op.add_column("order_items", sa.Column("variant_id", sa.UUID(), nullable=True))
    op.add_column("order_items", sa.Column("variant_label", sa.String(length=50), nullable=True))
    op.add_column("order_items", sa.Column("variant_price", sa.Numeric(precision=10, scale=2), nullable=True))
    op.create_foreign_key(
        "fk_order_items_variant_id_product_variants",
        "order_items", "product_variants", ["variant_id"], ["id"], ondelete="SET NULL",
    )

    op.add_column(
        "orders",
        sa.Column("seller_delivery_available", sa.Boolean(), server_default=sa.true(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("orders", "seller_delivery_available")
    op.drop_constraint("fk_order_items_variant_id_product_variants", "order_items", type_="foreignkey")
    op.drop_column("order_items", "variant_price")
    op.drop_column("order_items", "variant_label")
    op.drop_column("order_items", "variant_id")
    op.drop_constraint("uq_cart_product_variant", "cart_items", type_="unique")
    op.drop_constraint("fk_cart_items_variant_id_product_variants", "cart_items", type_="foreignkey")
    op.create_unique_constraint("uq_cart_product", "cart_items", ["cart_id", "product_id"])
    op.drop_column("cart_items", "variant_price")
    op.drop_column("cart_items", "variant_label")
    op.drop_column("cart_items", "variant_id")
    op.drop_index(op.f("ix_product_variants_product_id"), table_name="product_variants")
    op.drop_table("product_variants")
    op.drop_column("products", "is_made_to_order")
    op.drop_column("products", "sugar_info")
    op.drop_column("products", "storage_note")
    op.drop_column("products", "best_before")
    op.drop_column("products", "shelf_life_days")
    op.drop_column("products", "is_veg")
    op.drop_column("products", "allergens")
    op.drop_column("products", "ingredients")
    op.drop_column("stores", "fssai_number")
    op.drop_column("categories", "product_type")
