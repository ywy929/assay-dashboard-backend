"""
Password hashing utilities using PBKDF2-HMAC-SHA256.
Matches the C# EncryptionHelper implementation.
"""
import os
import hashlib
from config import settings

SALT_SIZE = settings.SALT_SIZE
HASH_SIZE = settings.HASH_SIZE
ITERATIONS = settings.ITERATIONS


def create_hash_with_new_salt(password: str) -> tuple[bytes, bytes]:
    """
    Create a new salt and hash the password.
    Returns (salt, hash) as bytes.
    Equivalent to C# CreateHashWithNewSalt.
    """
    salt = os.urandom(SALT_SIZE)
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS, dklen=HASH_SIZE)
    return salt, hash_bytes


def create_hash_with_existing_salt(password: str, salt: bytes) -> bytes:
    """
    Hash the password with an existing salt.
    Returns hash as bytes.
    Equivalent to C# CreateHashWithExistingSalt and GetHash.
    """
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS, dklen=HASH_SIZE)
    return hash_bytes


def verify_password(password: str, salt: bytes, stored_hash: bytes) -> bool:
    """
    Verify a password against a stored salt and hash.
    """
    computed_hash = create_hash_with_existing_salt(password, salt)
    return computed_hash == stored_hash
