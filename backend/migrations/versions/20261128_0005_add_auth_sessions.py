import sqlalchemy as sa
from alembic import op

revision = "20261128_0005"
down_revision = "20261127_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["movie_service.users.id"],
            ondelete="CASCADE",
            name=op.f("fk_auth_sessions_user_id_users"),
        ),
        schema="movie_service",
    )
    op.create_index(
        "ix_auth_sessions_user_id", "auth_sessions", ["user_id"], schema="movie_service"
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["movie_service.auth_sessions.id"],
            ondelete="CASCADE",
            name=op.f("fk_refresh_tokens_session_id_auth_sessions"),
        ),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
        schema="movie_service",
    )
    op.create_index(
        "ix_refresh_tokens_session_id",
        "refresh_tokens",
        ["session_id"],
        schema="movie_service",
    )
    op.execute("ALTER TABLE movie_service.auth_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE movie_service.refresh_tokens ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("refresh_tokens", schema="movie_service")
    op.drop_table("auth_sessions", schema="movie_service")
