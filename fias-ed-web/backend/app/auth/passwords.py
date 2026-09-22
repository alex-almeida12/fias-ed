import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_PASSWORD_LENGTH = 12
_hasher = PasswordHasher()  # Argon2id, perfil padrão RFC 9106 da biblioteca


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError, UnicodeError):
        # UnicodeError: hash "lixo" com bytes fora de ASCII (não é um hash argon2 válido).
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


def generate_provisional_password() -> str:
    return secrets.token_urlsafe(12)  # 16 caracteres


# Usado para igualar o tempo de resposta quando o usuário não existe.
DUMMY_HASH = hash_password("fias-ed-senha-ficticia")
