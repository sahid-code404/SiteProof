"""Phase 1 baseline tables.

Revision ID: 0001_phase1_baseline
Revises: None

Phase 1 used SQLAlchemy ``create_all`` instead of Alembic. This baseline therefore
adopts matching pre-Alembic ``organizations``/``users`` tables when they already
exist, while creating them for fresh databases.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_phase1_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "organizations" not in tables:
        op.create_table(
            "organizations",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
        op.create_index("ix_organizations_name", "organizations", ["name"], unique=False)

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("full_name", sa.String(length=160), nullable=False),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=False)
        op.create_index("ix_users_role", "users", ["role"], unique=False)


def downgrade() -> None:
    # A downgrade below the adopted baseline is intentionally destructive and should
    # only be used on disposable development/test databases.
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_organizations_name", table_name="organizations")
    op.drop_table("organizations")
