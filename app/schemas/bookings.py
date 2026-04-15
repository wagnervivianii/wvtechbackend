from pydantic import BaseModel, ConfigDict, EmailStr, Field


class BookingRequestCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    slot_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Identificador do horário selecionado",
    )
    name: str = Field(
        ...,
        min_length=2,
        max_length=120,
        description="Nome do visitante",
    )
    email: EmailStr = Field(
        ...,
        description="Email do visitante",
    )
    phone: str = Field(
        ...,
        min_length=8,
        max_length=30,
        description="Telefone do visitante",
    )
    subject_summary: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Resumo do assunto da reunião",
    )


class BookingRequestCreated(BaseModel):
    status: str = Field(..., description="Status do recebimento da solicitação")
    message: str = Field(..., description="Mensagem de retorno da API")
    slot_id: str = Field(..., description="Identificador do horário solicitado")
    name: str = Field(..., description="Nome do visitante")
    email: EmailStr = Field(..., description="Email do visitante")
    phone: str = Field(..., description="Telefone do visitante")
    subject_summary: str = Field(..., description="Resumo do assunto da reunião")