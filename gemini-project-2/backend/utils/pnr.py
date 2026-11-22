"""
Модуль для генерации и валидации PNR (уникального идентификатора фильма).
PNR состоит ровно из 6 символов: арабские цифры (0-9) и заглавные английские согласные (BCDFGHJKLMNPQRSTVWXYZ).
"""

import re
import secrets

# Разрешенные символы: цифры 0-9 и английские согласные BCDFGHJKLMNPQRSTVWXYZ
ALLOWED_DIGITS = "0123456789"
ALLOWED_CONSONANTS = "BCDFGHJKLMNPQRSTVWXYZ"
PNR_ALPHABET = ALLOWED_DIGITS + ALLOWED_CONSONANTS
PNR_LENGTH = 6

# Регулярное выражение для строгой проверки PNR
PNR_REGEX = re.compile(rf"^[{PNR_ALPHABET}]{{{PNR_LENGTH}}}$")


def is_valid_pnr(pnr: str) -> bool:
    """
    Проверяет валидность PNR:
    - Длина ровно 6 символов;
    - Содержит исключительно цифры (0-9) и заглавные латинские согласные.
    """
    if not isinstance(pnr, str):
        return False
    return bool(PNR_REGEX.match(pnr.strip().upper()))


def generate_pnr(length: int = PNR_LENGTH) -> str:
    """
    Генерирует случайный PNR заданной длины (по умолчанию 6 символов).
    Использует криптографически безопасный генератор secrets.
    """
    return "".join(secrets.choice(PNR_ALPHABET) for _ in range(length))
