from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Usuário administrativo",
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Senha administrativa",
    )

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip()


class AdminLoginResponse(BaseModel):
    access_token: str = Field(..., description="Token de acesso administrativo")
    token_type: str = Field(..., description="Tipo do token")
    expires_in: int = Field(..., description="Tempo restante do token em segundos")
    username: str = Field(..., description="Usuário autenticado")


class AdminMeResponse(BaseModel):
    authenticated: bool = Field(..., description="Indica se a sessão está autenticada")
    username: str = Field(..., description="Usuário administrativo autenticado")
    role: str = Field(..., description="Perfil autenticado")