"""
MeshMed Advanced PHI Encryption.

Extends GhostCFO's pattern using Fernet symmetric encryption.
Crucially, derives per-user encryption keys from a master secret + user_id
to enforce cryptographic isolation between patients.
"""

import base64
import hashlib
from functools import wraps
from typing import Any, Callable, TypeVar, Union

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger
from pydantic import BaseModel

from meshmed.core.config import get_settings

T = TypeVar("T")

class AdvancedPHICrypto:
    """Manages per-user symmetric encryption for medical data."""
    
    def __init__(self):
        self.settings = get_settings()
        self.master_secret = self.settings.phi_encryption_key
        
        if not self.master_secret:
            logger.warning("No Master PHI Key! Using insecure ephemeral key for local dev ONLY.")
            self.master_secret = Fernet.generate_key().decode('utf-8')
            
        # Global PHI Field Registry (Maps Schema Class Name -> List of PHI Fields)
        self.PHI_FIELDS = {
            "Patient": ["name", "phone_number", "dob"],
            "MedicalDocument": ["source_provider", "raw_text"],
            "Prescription": ["prescribing_doctor", "hospital_clinic", "diagnosis_mentioned", "instructions", "follow_up_instructions"],
            "MedicationItem": ["brand_name", "instructions", "stopped_reason"],
            "LabReport": ["lab_name", "ordering_doctor", "overall_interpretation"],
            "LabTestResult": ["test_name", "value"],
            "CareEpisode": ["condition", "managing_doctors", "summary"],
            "HandoffPacket": ["whatsapp_summary"]
        }

    def _derive_user_key(self, user_id: str) -> bytes:
        """
        Derives a deterministic, unique 32-byte Fernet key for a specific user
        using HKDF-like approach (SHA256 of master secret + user_id).
        """
        material = f"{self.master_secret}:{user_id}".encode('utf-8')
        digest = hashlib.sha256(material).digest()
        # Fernet requires url-safe base64 encoded 32-byte string
        return base64.urlsafe_b64encode(digest)

    def _get_fernet(self, user_id: str) -> Fernet:
        key = self._derive_user_key(user_id)
        return Fernet(key)

    def encrypt_field(self, user_id: str, plain_text: Optional[str]) -> Optional[str]:
        if not plain_text:
            return None
        f = self._get_fernet(user_id)
        return f.encrypt(plain_text.encode('utf-8')).decode('utf-8')

    def decrypt_field(self, user_id: str, cipher_text: Optional[str]) -> Optional[str]:
        if not cipher_text:
            return None
        f = self._get_fernet(user_id)
        try:
            return f.decrypt(cipher_text.encode('utf-8')).decode('utf-8')
        except InvalidToken:
            logger.error(f"Decryption failed for user {user_id}. Key mismatch or corrupted data.")
            return "<DECRYPTION_FAILED>"


# Singleton
_crypto = None

def get_crypto() -> AdvancedPHICrypto:
    global _crypto
    if _crypto is None:
        _crypto = AdvancedPHICrypto()
    return _crypto


def encrypt_phi(model_name: str):
    """
    Decorator for repository methods (e.g. `save_prescription(user_id, data)`).
    Automatically intercepts dictionaries or Pydantic models, looks up `model_name` 
    in PHI_FIELDS, and encrypts those fields using `user_id` derived keys before executing.
    Assumes `user_id` is passed as a keyword argument or is the first positional argument.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            crypto = get_crypto()
            fields_to_encrypt = crypto.PHI_FIELDS.get(model_name, [])
            
            if not fields_to_encrypt:
                return await func(*args, **kwargs)
                
            # Extract user_id (crude assumption: kwargs['user_id'] or args[1] if self is args[0])
            user_id = kwargs.get('user_id')
            if not user_id and len(args) > 1:
                user_id = args[1] if isinstance(args[1], str) else None
                
            if not user_id:
                logger.warning(f"@encrypt_phi requires user_id. Proceeding unencrypted for {model_name}.")
                return await func(*args, **kwargs)

            # Find the payload (dict or BaseModel)
            payload_idx = None
            payload = None
            for k, v in kwargs.items():
                if isinstance(v, (dict, BaseModel)):
                    payload = v
                    payload_key = k
                    break
                    
            if payload is None:
                for i, arg in enumerate(args):
                    if isinstance(arg, (dict, BaseModel)):
                        payload = arg
                        payload_idx = i
                        break

            if payload:
                is_pydantic = isinstance(payload, BaseModel)
                data_dict = payload.model_dump() if is_pydantic else payload.copy()
                
                for field in fields_to_encrypt:
                    if field in data_dict and isinstance(data_dict[field], str):
                        data_dict[field] = crypto.encrypt_field(user_id, data_dict[field])
                        
                # Reconstruct payload
                if is_pydantic:
                    # Depending on strictness, we might need to bypass validation for encrypted strings
                    # Since schemas expect raw text, storing encrypted string is fine if type is str
                    payload = payload.__class__(**data_dict)
                else:
                    payload = data_dict
                    
                # Inject modified payload back
                if payload_idx is not None:
                    args = list(args)
                    args[payload_idx] = payload
                    args = tuple(args)
                else:
                    kwargs[payload_key] = payload

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def decrypt_phi(model_name: str):
    """
    Decorator for repository read methods (e.g. `get_prescriptions(user_id)`).
    Automatically decrypts returned dicts or lists of dicts using the user's key.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            crypto = get_crypto()
            fields_to_decrypt = crypto.PHI_FIELDS.get(model_name, [])
            
            result = await func(*args, **kwargs)
            if not fields_to_decrypt or not result:
                return result
                
            user_id = kwargs.get('user_id')
            if not user_id and len(args) > 1:
                user_id = args[1] if isinstance(args[1], str) else None
                
            if not user_id:
                return result
                
            def _decrypt_obj(obj):
                is_pydantic = isinstance(obj, BaseModel)
                data = obj.model_dump() if is_pydantic else obj.copy()
                for field in fields_to_decrypt:
                    if field in data and isinstance(data[field], str):
                        data[field] = crypto.decrypt_field(user_id, data[field])
                return obj.__class__(**data) if is_pydantic else data

            if isinstance(result, list):
                return [_decrypt_obj(item) for item in result]
            return _decrypt_obj(result)
            
        return wrapper
    return decorator
