from app.core.patterns import NAME_EXTRA_CHARS, SUMMARY_ALLOWED_PUNCTUATION


def normalize_name_text(value: str) -> str:
    normalized = " ".join(value.strip().split()).upper()

    if len(normalized) < 3:
        raise ValueError("Nome deve ter pelo menos 3 caracteres")

    for char in normalized:
        if char.isalpha():
            continue
        if char in NAME_EXTRA_CHARS:
            continue
        raise ValueError("Nome deve conter apenas letras, espaços, hífen ou apóstrofo")

    return normalized


def normalize_phone_text(value: str) -> str:
    digits = "".join(char for char in value if char.isdigit())

    if len(digits) not in (10, 11):
        raise ValueError("Telefone deve conter DDD e 10 ou 11 dígitos")

    return digits


def normalize_summary_text(value: str) -> str:
    raw = value.replace("\r\n", "\n").replace("\r", "\n")

    cleaned_chars: list[str] = []
    for char in raw:
        if char.isalpha():
            cleaned_chars.append(char)
            continue

        if char in SUMMARY_ALLOWED_PUNCTUATION:
            cleaned_chars.append(char)
            continue

        # números e demais caracteres são descartados
        if char.isdigit():
            continue

    cleaned = "".join(cleaned_chars)

    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")

    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")

    cleaned = cleaned.strip()

    if len(cleaned) < 20:
        raise ValueError("Resumo do assunto deve ter pelo menos 20 caracteres")

    if len(cleaned) > 500:
        raise ValueError("Resumo do assunto deve ter no máximo 500 caracteres")

    return cleaned