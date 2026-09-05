"""Add server-issued semantic capture challenges.

Revision ID: 0014_semantic_capture_challenges
Revises: 0013_autonomous_verification_v2
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_semantic_capture_challenges"
down_revision = "0013_autonomous_verification_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_capture_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("inspection_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("challenge_type", sa.String(length=32), nullable=False),
        sa.Column("instruction", sa.String(length=1200), nullable=False),
        sa.Column("target_json", sa.JSON(), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ISSUED"),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_start_monotonic_ns", sa.BigInteger(), nullable=True),
        sa.Column("client_complete_monotonic_ns", sa.BigInteger(), nullable=True),
        sa.Column("window_start_ms", sa.BigInteger(), nullable=True),
        sa.Column("window_end_ms", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inspection_id"], ["inspections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nonce", name="uq_semantic_challenge_nonce"),
        sa.UniqueConstraint(
            "session_id",
            "sequence_number",
            "attempt_number",
            name="uq_semantic_challenge_session_sequence_attempt",
        ),
    )
    op.create_index(
        "ix_semantic_capture_challenges_organization_id",
        "semantic_capture_challenges",
        ["organization_id"],
    )
    op.create_index(
        "ix_semantic_capture_challenges_inspection_id",
        "semantic_capture_challenges",
        ["inspection_id"],
    )
    op.create_index(
        "ix_semantic_capture_challenges_session_id",
        "semantic_capture_challenges",
        ["session_id"],
    )
    op.create_index(
        "ix_semantic_capture_challenges_challenge_type",
        "semantic_capture_challenges",
        ["challenge_type"],
    )
    op.create_index(
        "ix_semantic_capture_challenges_status",
        "semantic_capture_challenges",
        ["status"],
    )
    op.create_index(
        "ix_semantic_challenge_session_status",
        "semantic_capture_challenges",
        ["session_id", "status"],
    )
    op.create_index(
        "ix_semantic_capture_challenges_expires_at",
        "semantic_capture_challenges",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_semantic_capture_challenges_expires_at", table_name="semantic_capture_challenges")
    op.drop_index("ix_semantic_challenge_session_status", table_name="semantic_capture_challenges")
    op.drop_index("ix_semantic_capture_challenges_status", table_name="semantic_capture_challenges")
    op.drop_index("ix_semantic_capture_challenges_challenge_type", table_name="semantic_capture_challenges")
    op.drop_index("ix_semantic_capture_challenges_session_id", table_name="semantic_capture_challenges")
    op.drop_index("ix_semantic_capture_challenges_inspection_id", table_name="semantic_capture_challenges")
    op.drop_index("ix_semantic_capture_challenges_organization_id", table_name="semantic_capture_challenges")
    op.drop_table("semantic_capture_challenges")
