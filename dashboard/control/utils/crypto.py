import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', 'default-super-secret-key-32-chars!')

def get_key_bytes() -> bytes:
    k = ENCRYPTION_KEY.encode('utf-8')
    if len(k) >= 32:
        return k[:32]
    return k.ljust(32, b'\0')

def encrypt(text: str) -> str:
    key = get_key_bytes()
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(text.encode('utf-8')) + padder.finalize()
    
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    
    return iv.hex() + ":" + encrypted_data.hex()

def decrypt(text: str) -> str:
    try:
        parts = text.split(":")
        if len(parts) != 2:
            return text
            
        iv = bytes.fromhex(parts[0])
        encrypted_data = bytes.fromhex(parts[1])
        
        key = get_key_bytes()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        decrypted_padded = decryptor.update(encrypted_data) + decryptor.finalize()
        
        unpadder = padding.PKCS7(128).unpadder()
        unpadded = unpadder.update(decrypted_padded) + unpadder.finalize()
        
        return unpadded.decode('utf-8')
    except Exception:
        return text
