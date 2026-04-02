import struct
import os
import logging
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger("rat.crypto")

class CryptoEngine:
    def __init__(self):
        self._private = ec.generate_private_key(ec.SECP384R1())
        self._shared = None
        self._aesgcm = None
        self._nonce = 0

    @property
    def public_key(self):
        return self._private.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint
        )

    def derive_key(self, peer_public):
        peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP384R1(), peer_public)
        secret = self._private.exchange(ec.ECDH(), peer)
        self._shared = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"rat-session-v1",
            info=b"session-key",
        ).derive(secret)
        self._aesgcm = AESGCM(self._shared)
        logger.info("Session key established")

    def encrypt(self, data):
        self._nonce += 1
        nonce = struct.pack(">I", self._nonce) + os.urandom(8)
        return nonce, self._aesgcm.encrypt(nonce, data, None)

    def decrypt(self, nonce, ciphertext):
        return self._aesgcm.decrypt(nonce, ciphertext, None)

    @property
    def ready(self):
        return self._aesgcm is not None
