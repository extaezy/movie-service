from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "movie_service"


class Base(DeclarativeBase):
    metadata = MetaData(
        schema=SCHEMA,
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        },
    )


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "char_length(username) BETWEEN 4 AND 20", name="username_length"
        ),
        CheckConstraint(
            "username ~ '^[a-zA-Z0-9]+(_[a-zA-Z0-9]+)*$'", name="username_format"
        ),
        CheckConstraint("role IN ('user', 'admin')", name="role_values"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    username: Mapped[str] = mapped_column(String(20), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    hashed_password: Mapped[str] = mapped_column("password_hash", Text)
    role: Mapped[str] = mapped_column(String(20), server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("bio IS NULL OR char_length(bio) <= 1000", name="bio_length"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str | None] = mapped_column(String(100))
    bio: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    is_private: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))


class Friendship(Timestamps, Base):
    __tablename__ = "friendships"
    __table_args__ = (
        UniqueConstraint("user_low_id", "user_high_id", name="uq_friendships_pair"),
        CheckConstraint("user_low_id < user_high_id", name="ordered_pair"),
        CheckConstraint(
            "requested_by_id IN (user_low_id, user_high_id)",
            name="requester_is_participant",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')", name="status_values"
        ),
        Index("ix_friendships_low_status", "user_low_id", "status"),
        Index("ix_friendships_high_status", "user_high_id", "status"),
        Index("ix_friendships_requested_by_id", "requested_by_id"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    user_low_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE")
    )
    user_high_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE")
    )
    requested_by_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(20), server_default="pending")


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (
        CheckConstraint("tmdb_id > 0", name="positive_tmdb_id"),
        CheckConstraint("char_length(btrim(title)) > 0", name="nonempty_title"),
        CheckConstraint("runtime IS NULL OR runtime > 0", name="positive_runtime"),
        CheckConstraint(
            "tmdb_vote_average BETWEEN 0 AND 10", name="tmdb_vote_average_range"
        ),
        CheckConstraint("tmdb_vote_count >= 0", name="tmdb_vote_count_nonnegative"),
        Index("ix_movies_release_date", "release_date"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    tmdb_id: Mapped[int] = mapped_column(Integer, unique=True)
    title: Mapped[str] = mapped_column(Text)
    original_title: Mapped[str | None] = mapped_column(Text)
    overview: Mapped[str | None] = mapped_column(Text)
    release_date: Mapped[date | None] = mapped_column(Date)
    poster_path: Mapped[str | None] = mapped_column(Text)
    runtime: Mapped[int | None] = mapped_column(Integer)
    original_language: Mapped[str | None] = mapped_column(String(10))
    tmdb_vote_average: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    tmdb_vote_count: Mapped[int | None] = mapped_column(Integer)
    tmdb_rating_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Genre(Base):
    __tablename__ = "genres"
    __table_args__ = (
        CheckConstraint("tmdb_id > 0", name="positive_tmdb_id"),
        CheckConstraint("char_length(btrim(name)) > 0", name="nonempty_name"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    tmdb_id: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(100))


class MovieGenre(Base):
    __tablename__ = "movie_genres"
    __table_args__ = (Index("ix_movie_genres_genre_id", "genre_id"),)

    movie_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.movies.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.genres.id", ondelete="CASCADE"), primary_key=True
    )


class UserMovieEntry(Base):
    __tablename__ = "user_movie_entries"
    __table_args__ = (
        CheckConstraint(
            "list_type IN ('watchlist', 'watched', 'favorite')", name="list_type_values"
        ),
        Index("ix_user_movie_entries_user_list", "user_id", "list_type"),
        Index("ix_user_movie_entries_movie_id", "movie_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), primary_key=True
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.movies.id", ondelete="CASCADE"), primary_key=True
    )
    list_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Rating(Timestamps, Base):
    __tablename__ = "ratings"
    __table_args__ = (
        CheckConstraint("score BETWEEN 1 AND 10", name="score_range"),
        Index("ix_ratings_movie_id", "movie_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), primary_key=True
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.movies.id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[int] = mapped_column(SmallInteger)


class UserReview(Timestamps, Base):
    __tablename__ = "user_reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_user_reviews_user_movie"),
        CheckConstraint("char_length(btrim(text)) > 0", name="nonempty_text"),
        Index("ix_user_reviews_movie_created", "movie_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE")
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.movies.id", ondelete="CASCADE")
    )
    text: Mapped[str] = mapped_column(Text)
    contains_spoilers: Mapped[bool] = mapped_column(
        Boolean, server_default=sql_text("false")
    )


class CriticSource(Base):
    __tablename__ = "critic_sources"
    __table_args__ = (
        CheckConstraint("source_type IN ('api', 'manual')", name="source_type_values"),
        CheckConstraint("char_length(btrim(name)) > 0", name="nonempty_name"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(10))
    source_type: Mapped[str] = mapped_column(String(20), server_default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("true"))


class Critic(Base):
    __tablename__ = "critics"
    __table_args__ = (
        UniqueConstraint("id", "source_id", name="uq_critics_id_source"),
        CheckConstraint("char_length(btrim(name)) > 0", name="nonempty_name"),
        Index("ix_critics_source_id", "source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    source_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.critic_sources.id", ondelete="RESTRICT")
    )
    profile_url: Mapped[str | None] = mapped_column(Text)


class CriticReview(Base):
    __tablename__ = "critic_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["critic_id", "source_id"],
            [f"{SCHEMA}.critics.id", f"{SCHEMA}.critics.source_id"],
            ondelete="RESTRICT",
            name="fk_critic_reviews_critic_source",
        ),
        UniqueConstraint(
            "source_id", "external_id", name="uq_critic_reviews_source_external"
        ),
        CheckConstraint(
            "char_length(btrim(external_url)) > 0", name="nonempty_external_url"
        ),
        CheckConstraint("char_length(btrim(excerpt)) > 0", name="nonempty_excerpt"),
        CheckConstraint("char_length(btrim(verdict)) > 0", name="nonempty_verdict"),
        CheckConstraint(
            "(original_score IS NULL AND score_scale IS NULL AND normalized_score IS NULL) OR "
            "(original_score IS NOT NULL AND score_scale IS NOT NULL AND normalized_score IS NOT NULL "
            "AND score_scale > 0 AND original_score >= 0 AND original_score <= score_scale "
            "AND normalized_score BETWEEN 0 AND 10)",
            name="score_values",
        ),
        CheckConstraint(
            "moderation_status IN ('pending', 'published', 'rejected')",
            name="moderation_values",
        ),
        Index("ix_critic_reviews_movie_language", "movie_id", "language"),
        Index("ix_critic_reviews_critic_source", "critic_id", "source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.movies.id", ondelete="CASCADE")
    )
    critic_id: Mapped[int | None] = mapped_column(Integer)
    source_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.critic_sources.id", ondelete="RESTRICT")
    )
    external_id: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str] = mapped_column(Text)
    external_url: Mapped[str] = mapped_column(Text, unique=True)
    language: Mapped[str] = mapped_column(String(10))
    original_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    score_scale: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    normalized_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    verdict: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    moderation_status: Mapped[str] = mapped_column(
        String(20), server_default="published"
    )
