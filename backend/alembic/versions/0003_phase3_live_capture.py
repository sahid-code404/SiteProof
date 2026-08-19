"""Phase 3 verification sessions and evidence metadata.

Revision ID: 0003_phase3_live_capture
Revises: 0002_phase2_inspections
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_phase3_live_capture"
down_revision = "0002_phase2_inspections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verification_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("inspection_id", sa.Uuid(), nullable=False),
        sa.Column("inspector_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="CREATED", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capture_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capture_ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_session_id", sa.String(length=80), nullable=False),
        sa.Column("client_version", sa.String(length=50), nullable=True),
        sa.Column("android_version", sa.String(length=50), nullable=True),
        sa.Column("device_model", sa.String(length=160), nullable=True),
        sa.Column("client_wall_clock", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_monotonic_ns", sa.BigInteger(), nullable=True),
        sa.Column("clock_offset_ms", sa.Float(), nullable=True),
        sa.Column("capture_anchor_wall_clock", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capture_anchor_monotonic_ns", sa.BigInteger(), nullable=True),
        sa.Column("capture_duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=True),
        sa.Column("upload_idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("abort_reason", sa.String(length=40), nullable=True),
        sa.Column("site_snapshot", sa.JSON(), nullable=True),
        sa.Column("pre_capture_location", sa.JSON(), nullable=True),
        sa.Column("device_capabilities", sa.JSON(), nullable=True),
        sa.Column("sensor_summary", sa.JSON(), nullable=True),
        sa.Column("location_summary", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inspection_id"], ["inspections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inspector_id"], ["inspectors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "device_session_id",
            name="uq_verification_session_device_session",
        ),
    )
    for column in [
        "organization_id",
        "inspection_id",
        "inspector_id",
        "status",
        "created_at",
        "expires_at",
    ]:
        op.create_index(
            f"ix_verification_sessions_{column}",
            "verification_sessions",
            [column],
            unique=False,
        )
    active_where = sa.text(
        "status IN ('CREATED','CAPTURING','CAPTURE_COMPLETED','UPLOADING','UPLOAD_FAILED')"
    )
    op.create_index(
        "uq_active_verification_session_per_inspection",
        "verification_sessions",
        ["inspection_id"],
        unique=True,
        postgresql_where=active_where,
        sqlite_where=active_where,
    )

    op.create_table(
        "evidence_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("inspection_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=700), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("upload_status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("hash_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inspection_id"], ["inspections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
        sa.UniqueConstraint("session_id", "file_type", name="uq_evidence_session_file_type"),
    )
    for column in [
        "organization_id",
        "inspection_id",
        "session_id",
        "file_type",
        "sha256",
        "upload_status",
    ]:
        op.create_index(f"ix_evidence_files_{column}", "evidence_files", [column], unique=False)


def downgrade() -> None:
    for column in [
        "upload_status",
        "sha256",
        "file_type",
        "session_id",
        "inspection_id",
        "organization_id",
    ]:
        op.drop_index(f"ix_evidence_files_{column}", table_name="evidence_files")
    op.drop_table("evidence_files")

    op.drop_index(
        "uq_active_verification_session_per_inspection",
        table_name="verification_sessions",
    )
    for column in [
        "expires_at",
        "created_at",
        "status",
        "inspector_id",
        "inspection_id",
        "organization_id",
    ]:
        op.drop_index(f"ix_verification_sessions_{column}", table_name="verification_sessions")
    op.drop_table("verification_sessions")
