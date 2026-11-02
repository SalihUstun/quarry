import secrets
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status

from app.bootstrap import AppServices


@dataclass(frozen=True, slots=True)
class Identity:
    tenant_id: UUID
    user_id: str


def get_services(request: Request) -> AppServices:
    services: AppServices = request.app.state.services
    return services


ServicesDep = Annotated[AppServices, Depends(get_services)]


def require_internal_token(
    services: ServicesDep,
    x_internal_token: Annotated[str, Header()] = "",
) -> None:
    expected = services.internal_token
    if not expected or not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal token")


def get_identity(
    x_tenant_id: Annotated[UUID, Header()],
    x_user_id: Annotated[str, Header(min_length=1, max_length=320)],
) -> Identity:
    return Identity(tenant_id=x_tenant_id, user_id=x_user_id)


IdentityDep = Annotated[Identity, Depends(get_identity)]
