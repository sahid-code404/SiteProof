"""Phase 8 evidence integrity and signed receipts.

Revision ID: 0008_phase8_evidence_integrity
Revises: 0007_phase7_verification
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_phase8_evidence_integrity"
down_revision = "0007_phase7_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("signing_keys", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("key_id", sa.String(length=120), nullable=False), sa.Column("algorithm", sa.String(length=32), nullable=False), sa.Column("public_key_base64", sa.Text(), nullable=False), sa.Column("status", sa.String(length=24), nullable=False), sa.Column("external_reference", sa.String(length=500), nullable=True), sa.Column("active_from", sa.DateTime(timezone=True), nullable=False), sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("key_id"))
    op.create_index("ix_signing_keys_key_id", "signing_keys", ["key_id"], unique=True)
    op.create_index("ix_signing_keys_status", "signing_keys", ["status"], unique=False)
    op.create_table("evidence_manifests", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("organization_id", sa.Uuid(), nullable=False), sa.Column("inspection_id", sa.Uuid(), nullable=False), sa.Column("session_id", sa.Uuid(), nullable=False), sa.Column("schema_version", sa.String(length=20), nullable=False), sa.Column("canonical_payload", sa.Text(), nullable=False), sa.Column("sha256", sa.String(length=64), nullable=False), sa.Column("evidence_file_count", sa.Integer(), nullable=False), sa.Column("total_size_bytes", sa.BigInteger(), nullable=False), sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["inspection_id"], ["inspections.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("session_id", "schema_version", name="uq_evidence_manifest_session_schema"))
    op.create_index("ix_evidence_manifests_organization_id", "evidence_manifests", ["organization_id"], unique=False)
    op.create_index("ix_evidence_manifests_inspection_id", "evidence_manifests", ["inspection_id"], unique=False)
    op.create_index("ix_evidence_manifests_session_id", "evidence_manifests", ["session_id"], unique=False)
    op.create_index("ix_evidence_manifests_sha256", "evidence_manifests", ["sha256"], unique=False)
    op.create_table("signed_receipts", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("receipt_number", sa.String(length=80), nullable=False), sa.Column("lookup_token", sa.String(length=160), nullable=False), sa.Column("organization_id", sa.Uuid(), nullable=False), sa.Column("inspection_id", sa.Uuid(), nullable=False), sa.Column("session_id", sa.Uuid(), nullable=False), sa.Column("verification_result_id", sa.Uuid(), nullable=False), sa.Column("manifest_id", sa.Uuid(), nullable=False), sa.Column("schema_version", sa.String(length=20), nullable=False), sa.Column("receipt_type", sa.String(length=40), nullable=False), sa.Column("canonical_payload", sa.Text(), nullable=False), sa.Column("manifest_sha256", sa.String(length=64), nullable=False), sa.Column("payload_sha256", sa.String(length=64), nullable=False), sa.Column("score", sa.Float(), nullable=False), sa.Column("verdict", sa.String(length=24), nullable=False), sa.Column("confidence", sa.Float(), nullable=False), sa.Column("policy_version", sa.String(length=32), nullable=False), sa.Column("engine_version", sa.String(length=48), nullable=False), sa.Column("signature_algorithm", sa.String(length=32), nullable=False), sa.Column("signature_base64", sa.Text(), nullable=False), sa.Column("signing_key_id", sa.String(length=120), nullable=False), sa.Column("lifecycle_status", sa.String(length=24), nullable=False), sa.Column("process_status", sa.String(length=32), nullable=False), sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True), sa.Column("revocation_reason", sa.Text(), nullable=True), sa.Column("superseded_by_id", sa.Uuid(), nullable=True), sa.Column("last_evidence_check_at", sa.DateTime(timezone=True), nullable=True), sa.Column("last_evidence_integrity", sa.String(length=32), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["inspection_id"], ["inspections.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["session_id"], ["verification_sessions.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["verification_result_id"], ["verification_results.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["manifest_id"], ["evidence_manifests.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["superseded_by_id"], ["signed_receipts.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("receipt_number"), sa.UniqueConstraint("lookup_token"), sa.UniqueConstraint("verification_result_id", "receipt_type", name="uq_signed_receipt_verification_type"))
    for name, cols, unique in [("ix_signed_receipts_receipt_number", ["receipt_number"], True), ("ix_signed_receipts_lookup_token", ["lookup_token"], True), ("ix_signed_receipts_organization_id", ["organization_id"], False), ("ix_signed_receipts_inspection_id", ["inspection_id"], False), ("ix_signed_receipts_session_id", ["session_id"], False), ("ix_signed_receipts_verification_result_id", ["verification_result_id"], False), ("ix_signed_receipts_payload_sha256", ["payload_sha256"], False), ("ix_signed_receipts_signing_key_id", ["signing_key_id"], False), ("ix_signed_receipts_lifecycle_status", ["lifecycle_status"], False), ("ix_signed_receipts_issued_at", ["issued_at"], False), ("ix_signed_receipt_session_status", ["session_id", "lifecycle_status"], False)]:
        op.create_index(name, "signed_receipts", cols, unique=unique)


def downgrade() -> None:
    for name in ["ix_signed_receipt_session_status", "ix_signed_receipts_issued_at", "ix_signed_receipts_lifecycle_status", "ix_signed_receipts_signing_key_id", "ix_signed_receipts_payload_sha256", "ix_signed_receipts_verification_result_id", "ix_signed_receipts_session_id", "ix_signed_receipts_inspection_id", "ix_signed_receipts_organization_id", "ix_signed_receipts_lookup_token", "ix_signed_receipts_receipt_number"]:
        op.drop_index(name, table_name="signed_receipts")
    op.drop_table("signed_receipts")
    for name in ["ix_evidence_manifests_sha256", "ix_evidence_manifests_session_id", "ix_evidence_manifests_inspection_id", "ix_evidence_manifests_organization_id"]:
        op.drop_index(name, table_name="evidence_manifests")
    op.drop_table("evidence_manifests")
    op.drop_index("ix_signing_keys_status", table_name="signing_keys")
    op.drop_index("ix_signing_keys_key_id", table_name="signing_keys")
    op.drop_table("signing_keys")
