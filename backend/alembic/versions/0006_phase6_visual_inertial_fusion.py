"""Phase 6 visual-inertial fusion results.

Revision ID: 0006_phase6_visual_inertial
Revises: 0005_phase5_visual_motion
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_phase6_visual_inertial"
down_revision = "0005_phase5_visual_motion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visual_inertial_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("challenge_id", sa.Uuid(), nullable=False),
        sa.Column("fusion_version", sa.String(length=40), nullable=False),
        sa.Column("analysis_status", sa.String(length=20), nullable=False),
        sa.Column("consistency_status", sa.String(length=32), server_default="INCONCLUSIVE", nullable=False),
        sa.Column("sensor_direction", sa.String(length=16), server_default="NONE", nullable=False),
        sa.Column("visual_direction", sa.String(length=16), server_default="NONE", nullable=False),
        sa.Column("sensor_angle_deg", sa.Float(), nullable=True),
        sa.Column("visual_angle_deg", sa.Float(), nullable=True),
        sa.Column("angle_difference_deg", sa.Float(), nullable=True),
        sa.Column("relative_angle_error", sa.Float(), nullable=True),
        sa.Column("sensor_start_ms", sa.Integer(), nullable=True),
        sa.Column("visual_start_ms", sa.Integer(), nullable=True),
        sa.Column("start_offset_ms", sa.Integer(), nullable=True),
        sa.Column("sensor_peak_ms", sa.Integer(), nullable=True),
        sa.Column("visual_peak_ms", sa.Integer(), nullable=True),
        sa.Column("sensor_end_ms", sa.Integer(), nullable=True),
        sa.Column("visual_end_ms", sa.Integer(), nullable=True),
        sa.Column("end_offset_ms", sa.Integer(), nullable=True),
        sa.Column("sensor_duration_ms", sa.Integer(), nullable=True),
        sa.Column("visual_duration_ms", sa.Integer(), nullable=True),
        sa.Column("motion_curve_correlation", sa.Float(), nullable=True),
        sa.Column("best_lag_ms", sa.Integer(), nullable=True),
        sa.Column("direction_score", sa.Float(), nullable=True),
        sa.Column("magnitude_score", sa.Float(), nullable=True),
        sa.Column("timing_score", sa.Float(), nullable=True),
        sa.Column("duration_score", sa.Float(), nullable=True),
        sa.Column("correlation_score", sa.Float(), nullable=True),
        sa.Column("raw_consistency_score", sa.Float(), nullable=True),
        sa.Column("effective_consistency_score", sa.Float(), nullable=True),
        sa.Column("fusion_confidence", sa.Float(), nullable=True),
        sa.Column("sensor_confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("visual_confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("mismatch_reasons_json", sa.JSON(), nullable=True),
        sa.Column("diagnostics_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["challenge_id"], ["verification_challenges.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "challenge_id",
            "fusion_version",
            name="uq_visual_inertial_challenge_version",
        ),
    )
    op.create_index(
        "ix_visual_inertial_results_organization_id",
        "visual_inertial_results",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_visual_inertial_results_session_id",
        "visual_inertial_results",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_visual_inertial_results_challenge_id",
        "visual_inertial_results",
        ["challenge_id"],
        unique=False,
    )
    op.create_index(
        "ix_visual_inertial_results_analysis_status",
        "visual_inertial_results",
        ["analysis_status"],
        unique=False,
    )
    op.create_index(
        "ix_visual_inertial_results_consistency_status",
        "visual_inertial_results",
        ["consistency_status"],
        unique=False,
    )
    op.create_index(
        "ix_visual_inertial_session_status",
        "visual_inertial_results",
        ["session_id", "consistency_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_visual_inertial_session_status", table_name="visual_inertial_results")
    op.drop_index("ix_visual_inertial_results_consistency_status", table_name="visual_inertial_results")
    op.drop_index("ix_visual_inertial_results_analysis_status", table_name="visual_inertial_results")
    op.drop_index("ix_visual_inertial_results_challenge_id", table_name="visual_inertial_results")
    op.drop_index("ix_visual_inertial_results_session_id", table_name="visual_inertial_results")
    op.drop_index("ix_visual_inertial_results_organization_id", table_name="visual_inertial_results")
    op.drop_table("visual_inertial_results")
