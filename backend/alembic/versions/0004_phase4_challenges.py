"""Phase 4 active challenge-response engine.

Revision ID: 0004_phase4_challenges
Revises: 0003_phase3_live_capture
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_phase4_challenges"
down_revision = "0003_phase3_live_capture"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        "uq_active_verification_session_per_inspection",
        table_name="verification_sessions",
    )
    active_where = sa.text(
        "status IN ('CREATED','CAPTURING','CHALLENGES_IN_PROGRESS','CHALLENGES_COMPLETED',"
        "'CHALLENGE_FAILED','CAPTURE_COMPLETED','UPLOADING','UPLOAD_FAILED')"
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
        "verification_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("inspection_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("challenge_type", sa.String(length=32), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="ISSUED", nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("client_start_monotonic_ns", sa.BigInteger(), nullable=True),
        sa.Column("sensor_score", sa.Float(), nullable=True),
        sa.Column("validation_score", sa.Float(), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=True),
        sa.Column("failure_reason", sa.String(length=160), nullable=True),
        sa.Column("reasons_json", sa.JSON(), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("sensor_quality_json", sa.JSON(), nullable=True),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=True),
        sa.Column("submission_idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("nonce_consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inspection_id"], ["inspections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "sequence_number",
            "attempt_number",
            name="uq_challenge_session_sequence_attempt",
        ),
        sa.UniqueConstraint("nonce", name="uq_verification_challenge_nonce"),
        sa.UniqueConstraint(
            "session_id",
            "submission_idempotency_key",
            name="uq_challenge_submission_idempotency",
        ),
    )
    for column in [
        "organization_id",
        "inspection_id",
        "session_id",
        "challenge_type",
        "status",
        "expires_at",
        "evidence_sha256",
    ]:
        op.create_index(
            f"ix_verification_challenges_{column}",
            "verification_challenges",
            [column],
            unique=False,
        )
    op.create_index(
        "ix_challenge_session_status",
        "verification_challenges",
        ["session_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_challenge_session_status", table_name="verification_challenges")
    for column in [
        "evidence_sha256",
        "expires_at",
        "status",
        "challenge_type",
        "session_id",
        "inspection_id",
        "organization_id",
    ]:
        op.drop_index(f"ix_verification_challenges_{column}", table_name="verification_challenges")
    op.drop_table("verification_challenges")

    op.drop_index(
        "uq_active_verification_session_per_inspection",
        table_name="verification_sessions",
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
