"""Phase 9 advanced anti-spoofing and device/capture integrity.

Revision ID: 0009_phase9_advanced_security
Revises: 0008_phase8_evidence_integrity
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_phase9_advanced_security"
down_revision = "0008_phase8_evidence_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attestation_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("nonce_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(96), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attestation_challenges_organization_id", "attestation_challenges", ["organization_id"])
    op.create_index("ix_attestation_challenges_session_id", "attestation_challenges", ["session_id"])
    op.create_index("ix_attestation_challenges_request_hash", "attestation_challenges", ["request_hash"])
    op.create_index("ix_attestation_challenge_session_consumed", "attestation_challenges", ["session_id", "consumed_at"])

    op.create_table(
        "device_attestations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(48), nullable=False),
        sa.Column("provider_version", sa.String(48), nullable=False),
        sa.Column("request_nonce_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(96), nullable=False),
        sa.Column("app_integrity_status", sa.String(24), nullable=False),
        sa.Column("device_integrity_status", sa.String(24), nullable=False),
        sa.Column("licensing_status", sa.String(32), nullable=False),
        sa.Column("token_issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("risk_flags_json", sa.JSON(), nullable=False),
        sa.Column("raw_token_hash", sa.String(64), nullable=False),
        sa.Column("validation_status", sa.String(20), nullable=False),
        sa.Column("diagnostics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_token_hash", name="uq_device_attestation_token_hash"),
    )
    op.create_index("ix_device_attestations_organization_id", "device_attestations", ["organization_id"])
    op.create_index("ix_device_attestations_session_id", "device_attestations", ["session_id"])
    op.create_index("ix_device_attestations_raw_token_hash", "device_attestations", ["raw_token_hash"])
    op.create_index("ix_device_attestations_validation_status", "device_attestations", ["validation_status"])
    op.create_index("ix_device_attestation_session_validated", "device_attestations", ["session_id", "validated_at"])

    op.create_table(
        "location_risk_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("process_status", sa.String(20), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("mock_location_detected", sa.Boolean(), nullable=False),
        sa.Column("max_implied_speed", sa.Float(), nullable=True),
        sa.Column("impossible_jump_count", sa.Integer(), nullable=False),
        sa.Column("sensor_location_consistency", sa.Float(), nullable=True),
        sa.Column("reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("algorithm_version", sa.String(48), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "algorithm_version", name="uq_location_risk_session_version"),
    )
    op.create_index("ix_location_risk_results_organization_id", "location_risk_results", ["organization_id"])
    op.create_index("ix_location_risk_results_session_id", "location_risk_results", ["session_id"])
    op.create_index("ix_location_risk_results_risk_level", "location_risk_results", ["risk_level"])

    op.create_table(
        "replay_risk_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("process_status", sa.String(20), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("display_rectangle_score", sa.Float(), nullable=False),
        sa.Column("moire_score", sa.Float(), nullable=False),
        sa.Column("banding_score", sa.Float(), nullable=False),
        sa.Column("evidence_reuse_score", sa.Float(), nullable=False),
        sa.Column("fusion_mismatch_score", sa.Float(), nullable=False),
        sa.Column("reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("algorithm_version", sa.String(48), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "algorithm_version", name="uq_replay_risk_session_version"),
    )
    op.create_index("ix_replay_risk_results_organization_id", "replay_risk_results", ["organization_id"])
    op.create_index("ix_replay_risk_results_session_id", "replay_risk_results", ["session_id"])
    op.create_index("ix_replay_risk_results_risk_level", "replay_risk_results", ["risk_level"])

    op.create_table(
        "sensor_anomaly_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("process_status", sa.String(20), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("anomaly_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("duplicate_sequence_score", sa.Float(), nullable=False),
        sa.Column("timestamp_anomaly_score", sa.Float(), nullable=False),
        sa.Column("range_anomaly_score", sa.Float(), nullable=False),
        sa.Column("cross_sensor_conflict_score", sa.Float(), nullable=False),
        sa.Column("reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("algorithm_version", sa.String(48), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "algorithm_version", name="uq_sensor_anomaly_session_version"),
    )
    op.create_index("ix_sensor_anomaly_results_organization_id", "sensor_anomaly_results", ["organization_id"])
    op.create_index("ix_sensor_anomaly_results_session_id", "sensor_anomaly_results", ["session_id"])
    op.create_index("ix_sensor_anomaly_results_risk_level", "sensor_anomaly_results", ["risk_level"])

    op.create_table(
        "advanced_security_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("inspection_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("process_status", sa.String(20), nullable=False),
        sa.Column("overall_risk", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("location_risk_score", sa.Float(), nullable=False),
        sa.Column("sensor_anomaly_score", sa.Float(), nullable=False),
        sa.Column("replay_risk_score", sa.Float(), nullable=False),
        sa.Column("evidence_reuse_score", sa.Float(), nullable=False),
        sa.Column("device_integrity_status", sa.String(32), nullable=False),
        sa.Column("device_risk_score", sa.Float(), nullable=False),
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
        sa.UniqueConstraint("session_id", "algorithm_version", name="uq_advanced_security_session_version"),
    )
    op.create_index("ix_advanced_security_results_organization_id", "advanced_security_results", ["organization_id"])
    op.create_index("ix_advanced_security_results_inspection_id", "advanced_security_results", ["inspection_id"])
    op.create_index("ix_advanced_security_results_session_id", "advanced_security_results", ["session_id"])
    op.create_index("ix_advanced_security_results_overall_risk", "advanced_security_results", ["overall_risk"])


def downgrade() -> None:
    for table, indexes in [
        ("advanced_security_results", ["ix_advanced_security_results_overall_risk", "ix_advanced_security_results_session_id", "ix_advanced_security_results_inspection_id", "ix_advanced_security_results_organization_id"]),
        ("sensor_anomaly_results", ["ix_sensor_anomaly_results_risk_level", "ix_sensor_anomaly_results_session_id", "ix_sensor_anomaly_results_organization_id"]),
        ("replay_risk_results", ["ix_replay_risk_results_risk_level", "ix_replay_risk_results_session_id", "ix_replay_risk_results_organization_id"]),
        ("location_risk_results", ["ix_location_risk_results_risk_level", "ix_location_risk_results_session_id", "ix_location_risk_results_organization_id"]),
        ("device_attestations", ["ix_device_attestation_session_validated", "ix_device_attestations_validation_status", "ix_device_attestations_raw_token_hash", "ix_device_attestations_session_id", "ix_device_attestations_organization_id"]),
        ("attestation_challenges", ["ix_attestation_challenge_session_consumed", "ix_attestation_challenges_request_hash", "ix_attestation_challenges_session_id", "ix_attestation_challenges_organization_id"]),
    ]:
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
