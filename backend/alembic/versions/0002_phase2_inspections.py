"""Phase 2 inspection management schema.

Revision ID: 0002_phase2_inspections
Revises: 0001_phase1_baseline
"""
import uuid

from alembic import op
import sqlalchemy as sa

revision = "0002_phase2_inspections"
down_revision = "0001_phase1_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("organization_id", sa.Uuid(), nullable=True))
    connection = op.get_bind()
    existing_users = connection.execute(sa.text("SELECT COUNT(*) FROM users")).scalar_one()
    if existing_users:
        legacy_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        insert_legacy_org = sa.text(
            "INSERT INTO organizations (id, name) VALUES (:id, :name) "
            "ON CONFLICT (name) DO NOTHING"
        ).bindparams(sa.bindparam("id", type_=sa.Uuid()))
        connection.execute(
            insert_legacy_org,
            {"id": legacy_id, "name": "Phase 1 Legacy Organization"},
        )
        legacy_org_id_value = connection.execute(
            sa.text("SELECT id FROM organizations WHERE name = :name"),
            {"name": "Phase 1 Legacy Organization"},
        ).scalar_one()
        legacy_org_id = (
            legacy_org_id_value
            if isinstance(legacy_org_id_value, uuid.UUID)
            else uuid.UUID(str(legacy_org_id_value))
        )
        update_users = sa.text(
            "UPDATE users SET organization_id = :org WHERE organization_id IS NULL"
        ).bindparams(sa.bindparam("org", type_=sa.Uuid()))
        connection.execute(update_users, {"org": legacy_org_id})
    # Batch mode keeps the migration runnable in SQLite-based developer/test environments
    # while emitting normal ALTER statements on PostgreSQL.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("organization_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_users_organization", "organizations", ["organization_id"], ["id"], ondelete="RESTRICT"
        )
    op.create_index("ix_users_organization_id", "users", ["organization_id"], unique=False)

    op.create_table(
        "inspectors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("employee_code", sa.String(length=80), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "employee_code", name="uq_inspector_employee_code"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_inspectors_organization_id", "inspectors", ["organization_id"], unique=False)
    op.create_index("ix_inspectors_user_id", "inspectors", ["user_id"], unique=False)
    op.create_index("ix_inspectors_active", "inspectors", ["active"], unique=False)

    op.create_table(
        "inspections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("inspection_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expected_latitude", sa.Float(), nullable=False),
        sa.Column("expected_longitude", sa.Float(), nullable=False),
        sa.Column("allowed_radius_meters", sa.Integer(), nullable=False),
        sa.Column("location_name", sa.String(length=200), nullable=True),
        sa.Column("location_address", sa.String(length=500), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["organization_id", "title", "inspection_type", "status", "deadline", "priority", "created_at"]:
        op.create_index(f"ix_inspections_{column}", "inspections", [column], unique=False)

    op.create_table(
        "inspection_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("inspection_id", sa.Uuid(), nullable=False),
        sa.Column("inspector_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unassigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inspection_id"], ["inspections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inspector_id"], ["inspectors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["organization_id", "inspection_id", "inspector_id", "status"]:
        op.create_index(f"ix_inspection_assignments_{column}", "inspection_assignments", [column], unique=False)
    op.create_index(
        "uq_active_assignment_per_inspection",
        "inspection_assignments",
        ["inspection_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["organization_id", "actor_user_id", "entity_type", "entity_id", "action", "timestamp"]:
        op.create_index(f"ix_audit_logs_{column}", "audit_logs", [column], unique=False)


def downgrade() -> None:
    for column in ["timestamp", "action", "entity_id", "entity_type", "actor_user_id", "organization_id"]:
        op.drop_index(f"ix_audit_logs_{column}", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("uq_active_assignment_per_inspection", table_name="inspection_assignments")
    for column in ["status", "inspector_id", "inspection_id", "organization_id"]:
        op.drop_index(f"ix_inspection_assignments_{column}", table_name="inspection_assignments")
    op.drop_table("inspection_assignments")

    for column in ["created_at", "priority", "deadline", "status", "inspection_type", "title", "organization_id"]:
        op.drop_index(f"ix_inspections_{column}", table_name="inspections")
    op.drop_table("inspections")

    op.drop_index("ix_inspectors_active", table_name="inspectors")
    op.drop_index("ix_inspectors_user_id", table_name="inspectors")
    op.drop_index("ix_inspectors_organization_id", table_name="inspectors")
    op.drop_table("inspectors")

    op.drop_index("ix_users_organization_id", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_organization", type_="foreignkey")
        batch_op.drop_column("organization_id")
