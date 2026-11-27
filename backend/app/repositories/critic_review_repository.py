from urllib.parse import urlsplit

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Critic, CriticReview, CriticSource
from app.integrations.nyt import NYTArticle
from app.schemas.critic_reviews import (
    CriticAuthorResponse,
    CriticReviewCreate,
    CriticReviewPage,
    CriticReviewResponse,
    CriticSourceResponse,
)

CRITIC_REVIEW_PAGE_SIZE = 10


class InactiveCriticSourceError(Exception):
    pass


def critic_review_response(
    review: CriticReview, source: CriticSource, critic: Critic | None
) -> CriticReviewResponse:
    return CriticReviewResponse(
        id=review.id,
        movie_id=review.movie_id,
        source=CriticSourceResponse.model_validate(source),
        critic=CriticAuthorResponse.model_validate(critic) if critic else None,
        language=review.language,
        external_url=review.external_url,
        title=review.title,
        excerpt=review.excerpt,
        published_at=review.published_at,
    )


async def get_or_create_manual_source(
    session: AsyncSession, source_name: str, external_url: str
) -> CriticSource:
    address = urlsplit(external_url)
    website_url = f"{address.scheme}://{address.netloc}/"
    lock_key = f"critic-source:manual:{source_name}:{website_url}"
    await session.execute(
        select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0)))
    )
    source = await session.scalar(
        select(CriticSource)
        .where(
            CriticSource.name == source_name,
            CriticSource.website_url == website_url,
            CriticSource.source_type == "manual",
        )
        .order_by(CriticSource.id)
        .limit(1)
    )
    if source is None:
        source = CriticSource(
            name=source_name, website_url=website_url, source_type="manual"
        )
        session.add(source)
        await session.flush()
    if not source.is_active:
        raise InactiveCriticSourceError("Источник отключён")
    return source


async def get_or_create_critic(
    session: AsyncSession, source_id: int, critic_name: str | None
) -> Critic | None:
    if critic_name is None:
        return None
    critic = await session.scalar(
        select(Critic)
        .where(Critic.source_id == source_id, Critic.name == critic_name)
        .order_by(Critic.id)
        .limit(1)
    )
    if critic is None:
        critic = Critic(name=critic_name, source_id=source_id)
        session.add(critic)
        await session.flush()
    return critic


async def create_critic_review(
    session: AsyncSession, entry: CriticReviewCreate
) -> CriticReviewResponse | None:
    source = await get_or_create_manual_source(
        session, entry.source_name, str(entry.external_url)
    )
    critic = await get_or_create_critic(session, source.id, entry.critic_name)
    statement = (
        insert(CriticReview)
        .values(
            movie_id=entry.movie_id,
            source_id=source.id,
            critic_id=critic.id if critic else None,
            language=entry.language,
            external_url=str(entry.external_url),
            title=entry.title,
            excerpt=entry.excerpt,
            published_at=entry.published_at,
            moderation_status="published",
        )
        .on_conflict_do_nothing(index_elements=[CriticReview.external_url])
        .returning(CriticReview)
    )
    review = await session.scalar(statement)
    return critic_review_response(review, source, critic) if review else None


async def list_critic_reviews(
    session: AsyncSession, movie_id: int, *, language: str | None, page: int
) -> CriticReviewPage:
    filters = [
        CriticReview.movie_id == movie_id,
        CriticReview.moderation_status == "published",
        CriticSource.is_active.is_(True),
    ]
    if language is not None:
        filters.append(CriticReview.language == language)
    count = (
        await session.scalar(
            select(func.count())
            .select_from(CriticReview)
            .join(CriticSource, CriticSource.id == CriticReview.source_id)
            .where(*filters)
        )
        or 0
    )
    statement = (
        select(CriticReview, CriticSource, Critic)
        .select_from(CriticReview)
        .join(CriticSource, CriticSource.id == CriticReview.source_id)
        .outerjoin(Critic, Critic.id == CriticReview.critic_id)
        .where(*filters)
        .order_by(CriticReview.published_at.desc().nulls_last(), CriticReview.id.desc())
        .offset((page - 1) * CRITIC_REVIEW_PAGE_SIZE)
        .limit(CRITIC_REVIEW_PAGE_SIZE)
    )
    rows = (await session.execute(statement)).all()
    return CriticReviewPage(
        page=page,
        page_size=CRITIC_REVIEW_PAGE_SIZE,
        total_results=count,
        total_pages=(count + CRITIC_REVIEW_PAGE_SIZE - 1) // CRITIC_REVIEW_PAGE_SIZE,
        results=[
            critic_review_response(review, source, critic)
            for review, source, critic in rows
        ],
    )


async def delete_critic_review(session: AsyncSession, review_id: int) -> bool:
    statement = (
        delete(CriticReview)
        .where(CriticReview.id == review_id)
        .returning(CriticReview.id)
    )
    return await session.scalar(statement) is not None


async def get_or_create_nyt_source(session: AsyncSession) -> CriticSource:
    await session.execute(
        select(
            func.pg_advisory_xact_lock(func.hashtextextended("critic-source:nyt", 0))
        )
    )
    source = await session.scalar(
        select(CriticSource)
        .where(
            CriticSource.source_type == "api",
            CriticSource.website_url == "https://www.nytimes.com/",
        )
        .order_by(CriticSource.id)
        .limit(1)
    )
    if source is None:
        source = CriticSource(
            name="The New York Times",
            website_url="https://www.nytimes.com/",
            language="en",
            source_type="api",
        )
        session.add(source)
        await session.flush()
    if not source.is_active:
        raise InactiveCriticSourceError("Источник отключён")
    return source


async def save_nyt_review(
    session: AsyncSession, movie_id: int, source: CriticSource, article: NYTArticle
) -> bool:
    external_url = str(article.web_url).split("?", 1)[0].split("#", 1)[0]
    existing = await session.scalar(
        select(CriticReview.id)
        .where(
            (CriticReview.external_url == external_url)
            | (
                (CriticReview.source_id == source.id)
                & (CriticReview.external_id == article.external_id)
            )
        )
        .limit(1)
    )
    if existing is not None:
        return False
    critic = await get_or_create_critic(session, source.id, article.critic_name)
    statement = (
        insert(CriticReview)
        .values(
            movie_id=movie_id,
            source_id=source.id,
            critic_id=critic.id if critic else None,
            external_id=article.external_id,
            external_url=external_url,
            title=article.headline.main,
            excerpt=article.excerpt,
            language="en",
            published_at=article.pub_date,
            moderation_status="published",
        )
        .on_conflict_do_nothing()
        .returning(CriticReview.id)
    )
    return await session.scalar(statement) is not None
