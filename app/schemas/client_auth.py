from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ClientInvitePreviewResponse(BaseModel):
    invite_email: EmailStr
    contact_name: str
    workspace_status: str
    invite_status: str
    expires_at: str | None
    accepted_at: str | None
    is_expired: bool
    can_activate: bool


class ClientFirstAccessRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    invite_token: str = Field(..., min_length=20, max_length=1024)
    password: str = Field(..., min_length=8, max_length=255)


class ClientLoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=255)


class ClientForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr


class ClientResetPasswordRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    token: str = Field(..., min_length=20, max_length=1024)
    password: str = Field(..., min_length=8, max_length=255)


class ClientGoogleStartResponse(BaseModel):
    authorization_url: str
    state: str


class ClientGoogleExchangeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(..., min_length=1, max_length=4096)
    state: str = Field(..., min_length=1, max_length=4096)
    redirect_uri: str = Field(..., min_length=1, max_length=2048)


class ClientAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_in: int
    workspace_id: int
    email: EmailStr
    auth_provider: str


class ClientAuthMessageResponse(BaseModel):
    message: str


class ClientMeResponse(BaseModel):
    authenticated: bool
    account_id: int
    workspace_id: int
    workspace_status: str
    email: EmailStr
    full_name: str | None
    auth_provider: str
    has_password: bool
    google_linked: bool
    last_login_at: str | None


class ClientGoogleExchangeResponse(ClientAuthTokenResponse):
    avatar_url: str | None = None