"""Add requested capture duration to inspections.

Revision ID: 0011_phase11_capture_duration
Revises: 0010_phase10_advanced_signals
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_phase11_capture_duration"
down_revision = "0010_phase10_advanced_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inspections",
        sa.Column("capture_duration_seconds", sa.Integer(), nullable=False, server_default="30"),
    )
    op.alter_column("inspections", "capture_duration_seconds", server_default=None)


def downgrade() -> None:
    op.drop_column("inspections", "capture_duration_seconds")
