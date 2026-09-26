"""Quote lookup by public link token.

Deliberately NOT tenant-scoped: the client opening a link isn't logged in.
Possessing the (unguessable) token IS the authorization, and it grants
access to exactly one quote.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Job, Quote


class PublicQuoteRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_token_hash(self, token_hash: str, *, lock: bool = False) -> Quote | None:
        statement = (
            select(Quote)
            .where(Quote.public_token_hash == token_hash)
            .options(
                selectinload(Quote.areas),
                selectinload(Quote.line_items),
                selectinload(Quote.job).selectinload(Job.client),
            )
        )
        if lock:
            # SELECT ... FOR UPDATE: a second approve/decline of the same quote
            # waits here until the first commits, then sees its result.
            statement = statement.with_for_update(of=Quote)
        return self._session.scalar(statement)
