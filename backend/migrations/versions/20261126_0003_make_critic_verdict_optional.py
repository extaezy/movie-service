import sqlalchemy as sa
from alembic import op

revision = "20261126_0003"
down_revision = "20261113_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "critic_reviews",
        "verdict",
        existing_type=sa.Text(),
        nullable=True,
        schema="movie_service",
    )


def downgrade() -> None:
    op.alter_column(
        "critic_reviews",
        "verdict",
        existing_type=sa.Text(),
        nullable=False,
        schema="movie_service",
    )
