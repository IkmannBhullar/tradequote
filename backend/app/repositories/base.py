"""TenantRepository: the single place tenant isolation is enforced in code.

Architecture rule 2: every query on a tenant-owned table filters by the
caller's organization. Instead of trusting every future query to remember a
`WHERE organization_id = ...`, repositories for tenant-owned models inherit
from this class, which is constructed with ONE organization id and builds
every query from `_scoped()`.

The organization id comes from the authenticated user (see api/deps.py),
never from the request body or URL.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.base import TenantScopedModel


@dataclass(frozen=True)
class PageResult[T]:
    items: Sequence[T]
    total: int  # matching rows across ALL pages, for "showing 1-50 of 312"


class TenantRepository[ModelT: TenantScopedModel]:
    # Set by each subclass, e.g. `model = Client`.
    model: type[ModelT]

    def __init__(self, session: Session, organization_id: uuid.UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    def _scoped(self) -> Select[ModelT]:
        """SELECT ... WHERE organization_id = <this tenant>.

        Every read in this class and its subclasses must start from here.
        """
        return select(self.model).where(self.model.organization_id == self._organization_id)

    def get(self, entity_id: uuid.UUID) -> ModelT | None:
        """Fetch by id *within this tenant*.

        Another org's row returns None, exactly like a row that doesn't exist.
        Callers turn that into a 404, so an attacker can't even learn that the
        id exists elsewhere.
        """
        return self._session.scalar(self._scoped().where(self.model.id == entity_id))

    def list(self) -> Sequence[ModelT]:
        return self._session.scalars(self._scoped().order_by(self.model.created_at)).all()

    def page(self, *, limit: int, offset: int) -> PageResult[ModelT]:
        return self._page(self._scoped().order_by(self.model.created_at), limit, offset)

    def _page(self, statement: Select[ModelT], limit: int, offset: int) -> PageResult[ModelT]:
        """Run an (already tenant-scoped) query one page at a time.

        Two queries: COUNT(*) over the filtered rows, then the page itself.
        A stable ORDER BY (plus id as a tie-breaker) keeps pages from
        overlapping or skipping rows between requests.
        """
        total = self._session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        items = self._session.scalars(
            statement.order_by(self.model.id).limit(limit).offset(offset)
        ).all()
        return PageResult(items=items, total=total or 0)

    def delete(self, entity: ModelT) -> None:
        # The entity was obtained through this repository, so it's ours.
        self._session.delete(entity)
        self._session.flush()

    def add(self, entity: ModelT) -> ModelT:
        """Insert a new row owned by this tenant.

        The organization is always overwritten with ours: even if a caller
        (or a bug) sets another org's id, the row lands in this tenant.
        """
        entity.organization_id = self._organization_id
        self._session.add(entity)
        self._session.flush()
        return entity
