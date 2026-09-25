"""Trade template access: system templates plus the organization's own.

A different scope from TenantRepository: a template is visible when it's a
system default (organization_id IS NULL) OR belongs to this organization.
This also closes the gap noted in Milestone 1: the database can't express
"quote areas may use same-org OR system template items", so the rule is
enforced here, and services must look template items up through this class.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import TemplateItem, TradeTemplate


class TemplateRepository:
    def __init__(self, session: Session, organization_id: uuid.UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    def _visible(self) -> ColumnElement[bool]:
        return or_(
            TradeTemplate.organization_id.is_(None),
            TradeTemplate.organization_id == self._organization_id,
        )

    def list_visible(self) -> Sequence[TradeTemplate]:
        return self._session.scalars(
            select(TradeTemplate)
            .where(self._visible())
            .options(selectinload(TradeTemplate.items))
            # The org's own templates first, then system ones, then by name.
            .order_by(
                TradeTemplate.organization_id.is_(None), TradeTemplate.trade, TradeTemplate.name
            )
        ).all()

    def get_visible_item(self, item_id: uuid.UUID) -> TemplateItem | None:
        return self._session.scalar(
            select(TemplateItem)
            .join(TradeTemplate, TemplateItem.template_id == TradeTemplate.id)
            .where(TemplateItem.id == item_id, self._visible())
        )
