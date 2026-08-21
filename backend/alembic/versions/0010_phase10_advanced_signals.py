"""Phase 10 environment continuity and statistical anomaly signals.

Revision ID: 0010_phase10_advanced_signals
Revises: 0009_phase9_advanced_security
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_phase10_advanced_signals"
down_revision = "0009_phase9_advanced_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "advanced_signal_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("inspection_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("process_status", sa.String(20), nullable=False),
        sa.Column("environment_status", sa.String(24), nullable=False),
        sa.Column("environment_consistency_score", sa.Float(), nullable=True),
        sa.Column("environment_risk_score", sa.Float(), nullable=False),
        sa.Column("environment_confidence", sa.Float(), nullable=False),
        sa.Column("statistical_anomaly_status", sa.String(24), nullable=False),
        sa.Column("statistical_anomaly_score", sa.Float(), nullable=False),
        sa.Column("statistical_anomaly_confidence", sa.Float(), nullable=False),
        sa.Column("reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("algorithm_version", sa.String(48), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inspection_id"], ["inspections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "algorithm_version", name="uq_advanced_signal_session_version"),
    )
    op.create_index("ix_advanced_signal_results_organization_id", "advanced_signal_results", ["organization_id"])
    op.create_index("ix_advanced_signal_results_inspection_id", "advanced_signal_results", ["inspection_id"])
    op.create_index("ix_advanced_signal_results_session_id", "advanced_signal_results", ["session_id"])
    op.create_index(
        "ix_advanced_signal_inspection_created",
        "advanced_signal_results",
        ["inspection_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_advanced_signal_inspection_created", table_name="advanced_signal_results")
    op.drop_index("ix_advanced_signal_results_session_id", table_name="advanced_signal_results")
    op.drop_index("ix_advanced_signal_results_inspection_id", table_name="advanced_signal_results")
    op.drop_index("ix_advanced_signal_results_organization_id", table_name="advanced_signal_results")
    op.drop_table("advanced_signal_results")
