"""Add fail-closed autonomous semantic verification results.

Revision ID: 0013_autonomous_verification_v2
Revises: 0012_durable_processing_jobs
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_autonomous_verification_v2"
down_revision = "0012_durable_processing_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "autonomous_verification_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("inspection_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("analysis_version", sa.String(length=48), nullable=False),
        sa.Column("contract_version", sa.String(length=48), nullable=False),
        sa.Column("contract_prompt_version", sa.String(length=48), nullable=False),
        sa.Column("vision_prompt_version", sa.String(length=48), nullable=False),
        sa.Column("compiler_model", sa.String(length=160), nullable=True),
        sa.Column("primary_vlm_model", sa.String(length=160), nullable=True),
        sa.Column("secondary_vlm_model", sa.String(length=160), nullable=True),
        sa.Column("contract_source_hash", sa.String(length=64), nullable=False),
        sa.Column("contract_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("contract_json", sa.JSON(), nullable=False),
        sa.Column("sampled_frame_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("frame_hashes_json", sa.JSON(), nullable=False),
        sa.Column("task_match_score", sa.Float(), nullable=True),
        sa.Column("task_match_confidence", sa.Float(), nullable=True),
        sa.Column("asset_identity_score", sa.Float(), nullable=True),
        sa.Column("asset_identity_confidence", sa.Float(), nullable=True),
        sa.Column("evidence_coverage_score", sa.Float(), nullable=True),
        sa.Column("evidence_coverage_confidence", sa.Float(), nullable=True),
        sa.Column("live_scene_score", sa.Float(), nullable=True),
        sa.Column("live_scene_confidence", sa.Float(), nullable=True),
        sa.Column("presentation_attack_score", sa.Float(), nullable=True),
        sa.Column("presentation_attack_confidence", sa.Float(), nullable=True),
        sa.Column("mandatory_failures_json", sa.JSON(), nullable=False),
        sa.Column("model_disagreement", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("observations_json", sa.JSON(), nullable=False),
        sa.Column("raw_response_hashes_json", sa.JSON(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inspection_id"], ["inspections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "analysis_version",
            name="uq_autonomous_verification_session_version",
        ),
    )
    op.create_index(
        "ix_autonomous_verification_results_organization_id",
        "autonomous_verification_results",
        ["organization_id"],
    )
    op.create_index(
        "ix_autonomous_verification_results_inspection_id",
        "autonomous_verification_results",
        ["inspection_id"],
    )
    op.create_index(
        "ix_autonomous_verification_results_session_id",
        "autonomous_verification_results",
        ["session_id"],
    )
    op.create_index(
        "ix_autonomous_verification_results_status",
        "autonomous_verification_results",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_autonomous_verification_results_status", table_name="autonomous_verification_results")
    op.drop_index("ix_autonomous_verification_results_session_id", table_name="autonomous_verification_results")
    op.drop_index("ix_autonomous_verification_results_inspection_id", table_name="autonomous_verification_results")
    op.drop_index("ix_autonomous_verification_results_organization_id", table_name="autonomous_verification_results")
    op.drop_table("autonomous_verification_results")
