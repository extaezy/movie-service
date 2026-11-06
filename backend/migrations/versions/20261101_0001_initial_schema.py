import sqlalchemy as sa
from alembic import op

revision = "20261101_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "critic_sources",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("website_url", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column(
            "source_type", sa.String(length=20), server_default="manual", nullable=False
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.CheckConstraint(
            "source_type IN ('api', 'manual')",
            name=op.f("ck_critic_sources_source_type_values"),
        ),
        sa.CheckConstraint(
            "char_length(btrim(name)) > 0", name=op.f("ck_critic_sources_nonempty_name")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_critic_sources")),
        schema="movie_service",
    )
    op.create_table(
        "genres",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.CheckConstraint(
            "char_length(btrim(name)) > 0", name=op.f("ck_genres_nonempty_name")
        ),
        sa.CheckConstraint("tmdb_id > 0", name=op.f("ck_genres_positive_tmdb_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_genres")),
        sa.UniqueConstraint("tmdb_id", name=op.f("uq_genres_tmdb_id")),
        schema="movie_service",
    )
    op.create_table(
        "movies",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("original_title", sa.Text(), nullable=True),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("poster_path", sa.Text(), nullable=True),
        sa.Column("runtime", sa.Integer(), nullable=True),
        sa.Column("original_language", sa.String(length=10), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(btrim(title)) > 0", name=op.f("ck_movies_nonempty_title")
        ),
        sa.CheckConstraint(
            "runtime IS NULL OR runtime > 0", name=op.f("ck_movies_positive_runtime")
        ),
        sa.CheckConstraint("tmdb_id > 0", name=op.f("ck_movies_positive_tmdb_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_movies")),
        sa.UniqueConstraint("tmdb_id", name=op.f("uq_movies_tmdb_id")),
        schema="movie_service",
    )
    op.create_index(
        "ix_movies_release_date",
        "movies",
        ["release_date"],
        unique=False,
        schema="movie_service",
    )
    op.create_table(
        "users",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("username", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=20), server_default="user", nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'admin')", name=op.f("ck_users_role_values")
        ),
        sa.CheckConstraint(
            "username ~ '^[a-zA-Z0-9]+(_[a-zA-Z0-9]+)*$'",
            name=op.f("ck_users_username_format"),
        ),
        sa.CheckConstraint(
            "char_length(username) BETWEEN 4 AND 20",
            name=op.f("ck_users_username_length"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
        schema="movie_service",
    )
    op.create_table(
        "critics",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("profile_url", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "char_length(btrim(name)) > 0", name=op.f("ck_critics_nonempty_name")
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["movie_service.critic_sources.id"],
            name=op.f("fk_critics_source_id_critic_sources"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_critics")),
        sa.UniqueConstraint("id", "source_id", name="uq_critics_id_source"),
        schema="movie_service",
    )
    op.create_index(
        "ix_critics_source_id",
        "critics",
        ["source_id"],
        unique=False,
        schema="movie_service",
    )
    op.create_table(
        "friendships",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("user_low_id", sa.Uuid(), nullable=False),
        sa.Column("user_high_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="pending", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name=op.f("ck_friendships_status_values"),
        ),
        sa.CheckConstraint(
            "requested_by_id IN (user_low_id, user_high_id)",
            name=op.f("ck_friendships_requester_is_participant"),
        ),
        sa.CheckConstraint(
            "user_low_id < user_high_id", name=op.f("ck_friendships_ordered_pair")
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"],
            ["movie_service.users.id"],
            name=op.f("fk_friendships_requested_by_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_high_id"],
            ["movie_service.users.id"],
            name=op.f("fk_friendships_user_high_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_low_id"],
            ["movie_service.users.id"],
            name=op.f("fk_friendships_user_low_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_friendships")),
        sa.UniqueConstraint("user_low_id", "user_high_id", name="uq_friendships_pair"),
        schema="movie_service",
    )
    op.create_index(
        "ix_friendships_high_status",
        "friendships",
        ["user_high_id", "status"],
        unique=False,
        schema="movie_service",
    )
    op.create_index(
        "ix_friendships_low_status",
        "friendships",
        ["user_low_id", "status"],
        unique=False,
        schema="movie_service",
    )
    op.create_index(
        "ix_friendships_requested_by_id",
        "friendships",
        ["requested_by_id"],
        unique=False,
        schema="movie_service",
    )
    op.create_table(
        "movie_genres",
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("genre_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["genre_id"],
            ["movie_service.genres.id"],
            name=op.f("fk_movie_genres_genre_id_genres"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["movie_id"],
            ["movie_service.movies.id"],
            name=op.f("fk_movie_genres_movie_id_movies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("movie_id", "genre_id", name=op.f("pk_movie_genres")),
        schema="movie_service",
    )
    op.create_index(
        "ix_movie_genres_genre_id",
        "movie_genres",
        ["genre_id"],
        unique=False,
        schema="movie_service",
    )
    op.create_table(
        "profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column(
            "is_private", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.CheckConstraint(
            "bio IS NULL OR char_length(bio) <= 1000",
            name=op.f("ck_profiles_bio_length"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["movie_service.users.id"],
            name=op.f("fk_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_profiles")),
        schema="movie_service",
    )
    op.create_table(
        "ratings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "score BETWEEN 1 AND 10", name=op.f("ck_ratings_score_range")
        ),
        sa.ForeignKeyConstraint(
            ["movie_id"],
            ["movie_service.movies.id"],
            name=op.f("fk_ratings_movie_id_movies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["movie_service.users.id"],
            name=op.f("fk_ratings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "movie_id", name=op.f("pk_ratings")),
        schema="movie_service",
    )
    op.create_index(
        "ix_ratings_movie_id",
        "ratings",
        ["movie_id"],
        unique=False,
        schema="movie_service",
    )
    op.create_table(
        "user_movie_entries",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("list_type", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "list_type IN ('watchlist', 'watched', 'favorite')",
            name=op.f("ck_user_movie_entries_list_type_values"),
        ),
        sa.ForeignKeyConstraint(
            ["movie_id"],
            ["movie_service.movies.id"],
            name=op.f("fk_user_movie_entries_movie_id_movies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["movie_service.users.id"],
            name=op.f("fk_user_movie_entries_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "movie_id", "list_type", name=op.f("pk_user_movie_entries")
        ),
        schema="movie_service",
    )
    op.create_index(
        "ix_user_movie_entries_movie_id",
        "user_movie_entries",
        ["movie_id"],
        unique=False,
        schema="movie_service",
    )
    op.create_index(
        "ix_user_movie_entries_user_list",
        "user_movie_entries",
        ["user_id", "list_type"],
        unique=False,
        schema="movie_service",
    )
    op.create_table(
        "user_reviews",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "contains_spoilers",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(btrim(text)) > 0", name=op.f("ck_user_reviews_nonempty_text")
        ),
        sa.ForeignKeyConstraint(
            ["movie_id"],
            ["movie_service.movies.id"],
            name=op.f("fk_user_reviews_movie_id_movies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["movie_service.users.id"],
            name=op.f("fk_user_reviews_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_reviews")),
        sa.UniqueConstraint("user_id", "movie_id", name="uq_user_reviews_user_movie"),
        schema="movie_service",
    )
    op.create_index(
        "ix_user_reviews_movie_created",
        "user_reviews",
        ["movie_id", "created_at"],
        unique=False,
        schema="movie_service",
    )
    op.create_table(
        "critic_reviews",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("critic_id", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("external_url", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("original_score", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("score_scale", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("normalized_score", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "moderation_status",
            sa.String(length=20),
            server_default="published",
            nullable=False,
        ),
        sa.CheckConstraint(
            "moderation_status IN ('pending', 'published', 'rejected')",
            name=op.f("ck_critic_reviews_moderation_values"),
        ),
        sa.CheckConstraint(
            "(original_score IS NULL AND score_scale IS NULL AND normalized_score IS NULL) OR (original_score IS NOT NULL AND score_scale IS NOT NULL AND normalized_score IS NOT NULL AND score_scale > 0 AND original_score >= 0 AND original_score <= score_scale AND normalized_score BETWEEN 0 AND 10)",
            name=op.f("ck_critic_reviews_score_values"),
        ),
        sa.CheckConstraint(
            "char_length(btrim(excerpt)) > 0",
            name=op.f("ck_critic_reviews_nonempty_excerpt"),
        ),
        sa.CheckConstraint(
            "char_length(btrim(external_url)) > 0",
            name=op.f("ck_critic_reviews_nonempty_external_url"),
        ),
        sa.CheckConstraint(
            "char_length(btrim(verdict)) > 0",
            name=op.f("ck_critic_reviews_nonempty_verdict"),
        ),
        sa.ForeignKeyConstraint(
            ["critic_id", "source_id"],
            ["movie_service.critics.id", "movie_service.critics.source_id"],
            name="fk_critic_reviews_critic_source",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["movie_id"],
            ["movie_service.movies.id"],
            name=op.f("fk_critic_reviews_movie_id_movies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["movie_service.critic_sources.id"],
            name=op.f("fk_critic_reviews_source_id_critic_sources"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_critic_reviews")),
        sa.UniqueConstraint(
            "external_url", name=op.f("uq_critic_reviews_external_url")
        ),
        sa.UniqueConstraint(
            "source_id", "external_id", name="uq_critic_reviews_source_external"
        ),
        schema="movie_service",
    )
    op.create_index(
        "ix_critic_reviews_critic_source",
        "critic_reviews",
        ["critic_id", "source_id"],
        unique=False,
        schema="movie_service",
    )
    op.create_index(
        "ix_critic_reviews_movie_language",
        "critic_reviews",
        ["movie_id", "language"],
        unique=False,
        schema="movie_service",
    )
    op.execute("ALTER TABLE movie_service.critic_sources ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE movie_service.genres ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE movie_service.movies ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE movie_service.users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE movie_service.critics ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE movie_service.friendships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE movie_service.movie_genres ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE movie_service.profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE movie_service.ratings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE movie_service.user_movie_entries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE movie_service.user_reviews ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE movie_service.critic_reviews ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("critic_reviews", schema="movie_service")
    op.drop_table("user_reviews", schema="movie_service")
    op.drop_table("user_movie_entries", schema="movie_service")
    op.drop_table("ratings", schema="movie_service")
    op.drop_table("profiles", schema="movie_service")
    op.drop_table("movie_genres", schema="movie_service")
    op.drop_table("friendships", schema="movie_service")
    op.drop_table("critics", schema="movie_service")
    op.drop_table("users", schema="movie_service")
    op.drop_table("movies", schema="movie_service")
    op.drop_table("genres", schema="movie_service")
    op.drop_table("critic_sources", schema="movie_service")
