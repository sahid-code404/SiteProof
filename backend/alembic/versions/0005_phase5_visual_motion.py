"""Phase 5 visual motion analysis results.

Revision ID: 0005_phase5_visual_motion
Revises: 0004_phase4_challenges
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_phase5_visual_motion"
down_revision = "0004_phase4_challenges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visual_motion_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("challenge_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_version", sa.String(length=40), nullable=False),
        sa.Column("analysis_status", sa.String(length=20), nullable=False),
        sa.Column("visual_direction", sa.String(length=16), server_default="NONE", nullable=False),
        sa.Column("visual_quality", sa.String(length=12), server_default="POOR", nullable=False),
        sa.Column("estimated_rotation_degrees", sa.Float(), nullable=True),
        sa.Column("translation_x", sa.Float(), nullable=True),
        sa.Column("translation_y", sa.Float(), nullable=True),
        sa.Column("scale_change", sa.Float(), nullable=True),
        sa.Column("motion_start_ms", sa.Integer(), nullable=True),
        sa.Column("motion_end_ms", sa.Integer(), nullable=True),
        sa.Column("feature_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tracked_feature_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("inlier_ratio", sa.Float(), server_default="0", nullable=False),
        sa.Column("visual_confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("scene_continuity_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("duplicate_frame_ratio", sa.Float(), server_default="0", nullable=False),
        sa.Column("freeze_duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("invalid_frame_ratio", sa.Float(), server_default="0", nullable=False),
        sa.Column("diagnostics_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["challenge_id"], ["verification_challenges.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "challenge_id",
            "analysis_version",
            name="uq_visual_motion_challenge_version",
        ),
    )
    op.create_index(
        "ix_visual_motion_results_organization_id",
        "visual_motion_results",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_visual_motion_results_session_id",
        "visual_motion_results",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_visual_motion_results_challenge_id",
        "visual_motion_results",
        ["challenge_id"],
        unique=False,
    )
    op.create_index(
        "ix_visual_motion_results_analysis_status",
        "visual_motion_results",
        ["analysis_status"],
        unique=False,
    )
    op.create_index(
        "ix_visual_motion_session_status",
        "visual_motion_results",
        ["session_id", "analysis_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_visual_motion_session_status", table_name="visual_motion_results")
    op.drop_index("ix_visual_motion_results_analysis_status", table_name="visual_motion_results")
    op.drop_index("ix_visual_motion_results_challenge_id", table_name="visual_motion_results")
    op.drop_index("ix_visual_motion_results_session_id", table_name="visual_motion_results")
    op.drop_index("ix_visual_motion_results_organization_id", table_name="visual_motion_results")
    op.drop_table("visual_motion_results")
