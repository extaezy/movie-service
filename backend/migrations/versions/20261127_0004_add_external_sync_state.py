import sqlalchemy as sa
from alembic import op

revision = "20261127_0004"
down_revision = "20261126_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_sync_states",
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("initial_sync_date", sa.Date(), nullable=True),
        sa.Column("last_synced_date", sa.Date(), nullable=True),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_external_sync_states")),
        schema="movie_service",
    )
    op.execute(
        "ALTER TABLE movie_service.external_sync_states ENABLE ROW LEVEL SECURITY"
    )


def downgrade() -> None:
    op.drop_table("external_sync_states", schema="movie_service")
