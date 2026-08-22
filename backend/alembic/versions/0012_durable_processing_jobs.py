"""Add durable verification processing jobs.

Revision ID: 0012_durable_processing_jobs
Revises: 0011_phase11_capture_duration
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_durable_processing_jobs"
down_revision = "0011_phase11_capture_duration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verification_processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("pipeline_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "pipeline_version", name="uq_processing_job_session_pipeline"),
    )
    op.create_index("ix_processing_job_status_next", "verification_processing_jobs", ["status", "next_attempt_at"])
    op.create_index("ix_processing_job_lease", "verification_processing_jobs", ["status", "lease_expires_at"])
    op.create_index("ix_verification_processing_jobs_session_id", "verification_processing_jobs", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_verification_processing_jobs_session_id", table_name="verification_processing_jobs")
    op.drop_index("ix_processing_job_lease", table_name="verification_processing_jobs")
    op.drop_index("ix_processing_job_status_next", table_name="verification_processing_jobs")
    op.drop_table("verification_processing_jobs")
