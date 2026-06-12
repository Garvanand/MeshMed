"""
MeshMed PHI Encryption Layer.

Handles strict application-level encryption for Protected Health Information (PHI)
before it reaches the database.
"""

import base64
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from meshmed.core.config import get_settings


class PHICryptoManager:
    """Manages symmetric encryption for medical data."""
    
    def __init__(self):
        settings = get_settings()
        key = settings.phi_encryption_key
        
        if not key:
            if settings.environment == "production":
                raise ValueError("CRITICAL: PHI_ENCRYPTION_KEY is not set in production!")
            logger.warning("No PHI encryption key found. Using ephemeral mock key for local dev ONLY.")
            key = Fernet.generate_key().decode('utf-8')
            
        try:
            self.fernet = Fernet(key.encode('utf-8'))
        except (ValueError, TypeError) as e:
            logger.error("Invalid PHI_ENCRYPTION_KEY format. Must be 32-byte url-safe base64.")
            raise ValueError(f"Encryption setup failed: {e}")

    def encrypt(self, plain_text: Optional[str]) -> Optional[str]:
        """Encrypts a string into a base64 fernet token."""
        if not plain_text:
            return None
        return self.fernet.encrypt(plain_text.encode('utf-8')).decode('utf-8')

    def decrypt(self, cipher_text: Optional[str]) -> Optional[str]:
        """Decrypts a fernet token back to string."""
        if not cipher_text:
            return None
        try:
            return self.fernet.decrypt(cipher_text.encode('utf-8')).decode('utf-8')
        except InvalidToken:
            logger.error("Failed to decrypt PHI. Token is invalid or key has changed.")
            # Fail closed for security
            return "<DECRYPTION_ERROR_PHI_REDACTED>"
        except Exception as e:
            logger.error(f"Unexpected decryption error: {e}")
            return "<DECRYPTION_ERROR_PHI_REDACTED>"

    def encrypt_dict(self, data: dict, encrypted_fields: list[str]) -> dict:
        """Encrypts specific fields in a dictionary."""
        encrypted_data = data.copy()
        for field in encrypted_fields:
            if field in encrypted_data and isinstance(encrypted_data[field], str):
                encrypted_data[field] = self.encrypt(encrypted_data[field])
        return encrypted_data

    def decrypt_dict(self, data: dict, encrypted_fields: list[str]) -> dict:
        """Decrypts specific fields in a dictionary."""
        decrypted_data = data.copy()
        for field in encrypted_fields:
            if field in decrypted_data and isinstance(decrypted_data[field], str):
                decrypted_data[field] = self.decrypt(decrypted_data[field])
        return decrypted_data


# Singleton
_crypto_manager = None

def get_crypto_manager() -> PHICryptoManager:
    global _crypto_manager
    if _crypto_manager is None:
        _crypto_manager = PHICryptoManager()
    return _crypto_manager
