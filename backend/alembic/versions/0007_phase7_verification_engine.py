"""Phase 7 explainable verification, policy and review results.

Revision ID: 0007_phase7_verification_engine
Revises: 0006_phase6_visual_inertial
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_phase7_verification_engine"
down_revision = "0006_phase6_visual_inertial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verification_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("verified_threshold", sa.Float(), nullable=False),
        sa.Column("review_threshold", sa.Float(), nullable=False),
        sa.Column("minimum_required_confidence", sa.Float(), nullable=False),
        sa.Column("weights_json", sa.JSON(), nullable=False),
        sa.Column("required_signals_json", sa.JSON(), nullable=False),
        sa.Column("hard_rules_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "name",
            "version",
            name="uq_verification_policy_org_name_version",
        ),
    )
    op.create_index(
        "ix_verification_policies_organization_id",
        "verification_policies",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_verification_policies_active",
        "verification_policies",
        ["active"],
        unique=False,
    )
    op.create_index(
        "ix_verification_policy_org_active",
        "verification_policies",
        ["organization_id", "active"],
        unique=False,
    )

    op.create_table(
        "verification_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("inspection_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("engine_version", sa.String(length=48), nullable=False),
        sa.Column(
            "calculation_revision",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("raw_score", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("verdict", sa.String(length=32), nullable=True),
        sa.Column("overall_confidence", sa.Float(), nullable=True),
        sa.Column(
            "hard_rule_triggered",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("hard_rule_codes_json", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_reasons_json", sa.JSON(), nullable=False),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["inspections.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["verification_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["verification_policies.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "policy_id",
            "engine_version",
            "calculation_revision",
            name="uq_verification_result_session_policy_engine_revision",
        ),
    )
    for column in (
        "organization_id",
        "inspection_id",
        "session_id",
        "policy_id",
        "processing_status",
        "verdict",
    ):
        op.create_index(
            f"ix_verification_results_{column}",
            "verification_results",
            [column],
            unique=False,
        )
    op.create_index(
        "ix_verification_result_session_current",
        "verification_results",
        ["session_id", "calculated_at"],
        unique=False,
    )

    op.create_table(
        "verification_signal_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("verification_result_id", sa.Uuid(), nullable=False),
        sa.Column("signal_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("configured_weight", sa.Float(), nullable=False),
        sa.Column("effective_weight", sa.Float(), nullable=False),
        sa.Column("weighted_contribution", sa.Float(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("reason_summary", sa.String(length=500), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("source_algorithm_version", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["verification_result_id"],
            ["verification_results.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "verification_result_id",
            "signal_type",
            name="uq_verification_signal_result_type",
        ),
    )
    op.create_index(
        "ix_verification_signal_results_verification_result_id",
        "verification_signal_results",
        ["verification_result_id"],
        unique=False,
    )
    op.create_index(
        "ix_verification_signal_results_signal_type",
        "verification_signal_results",
        ["signal_type"],
        unique=False,
    )

    op.create_table(
        "review_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("inspection_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("verification_result_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["inspections.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["verification_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["verification_result_id"],
            ["verification_results.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "organization_id",
        "inspection_id",
        "session_id",
        "verification_result_id",
        "reviewer_user_id",
        "decision",
        "created_at",
    ):
        op.create_index(
            f"ix_review_decisions_{column}",
            "review_decisions",
            [column],
            unique=False,
        )
    op.create_index(
        "ix_review_decision_inspection_created",
        "review_decisions",
        ["inspection_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_review_decision_inspection_created",
        table_name="review_decisions",
    )
    for column in (
        "created_at",
        "decision",
        "reviewer_user_id",
        "verification_result_id",
        "session_id",
        "inspection_id",
        "organization_id",
    ):
        op.drop_index(f"ix_review_decisions_{column}", table_name="review_decisions")
    op.drop_table("review_decisions")

    op.drop_index(
        "ix_verification_signal_results_signal_type",
        table_name="verification_signal_results",
    )
    op.drop_index(
        "ix_verification_signal_results_verification_result_id",
        table_name="verification_signal_results",
    )
    op.drop_table("verification_signal_results")

    op.drop_index(
        "ix_verification_result_session_current",
        table_name="verification_results",
    )
    for column in (
        "verdict",
        "processing_status",
        "policy_id",
        "session_id",
        "inspection_id",
        "organization_id",
    ):
        op.drop_index(
            f"ix_verification_results_{column}",
            table_name="verification_results",
        )
    op.drop_table("verification_results")

    op.drop_index(
        "ix_verification_policy_org_active",
        table_name="verification_policies",
    )
    op.drop_index(
        "ix_verification_policies_active",
        table_name="verification_policies",
    )
    op.drop_index(
        "ix_verification_policies_organization_id",
        table_name="verification_policies",
    )
    op.drop_table("verification_policies")
