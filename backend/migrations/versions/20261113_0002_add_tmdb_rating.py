import sqlalchemy as sa
from alembic import op

revision = "20261113_0002"
down_revision = "20261101_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "movies",
        sa.Column("tmdb_vote_average", sa.Numeric(5, 3), nullable=True),
        schema="movie_service",
    )
    op.add_column(
        "movies",
        sa.Column("tmdb_vote_count", sa.Integer(), nullable=True),
        schema="movie_service",
    )
    op.add_column(
        "movies",
        sa.Column("tmdb_rating_updated_at", sa.DateTime(timezone=True), nullable=True),
        schema="movie_service",
    )
    op.create_check_constraint(
        op.f("ck_movies_tmdb_vote_average_range"),
        "movies",
        "tmdb_vote_average BETWEEN 0 AND 10",
        schema="movie_service",
    )
    op.create_check_constraint(
        op.f("ck_movies_tmdb_vote_count_nonnegative"),
        "movies",
        "tmdb_vote_count >= 0",
        schema="movie_service",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_movies_tmdb_vote_count_nonnegative"),
        "movies",
        type_="check",
        schema="movie_service",
    )
    op.drop_constraint(
        op.f("ck_movies_tmdb_vote_average_range"),
        "movies",
        type_="check",
        schema="movie_service",
    )
    op.drop_column("movies", "tmdb_rating_updated_at", schema="movie_service")
    op.drop_column("movies", "tmdb_vote_count", schema="movie_service")
    op.drop_column("movies", "tmdb_vote_average", schema="movie_service")
