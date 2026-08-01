"""
ALADIN37 Financial Trust Engine - Signing Layer
v1.2

Sicherheitskorrektur gegenueber der vorherigen Version (Copilot-Entwurf):
Dort stand der Ed25519-Seed als Literal-String direkt im Quellcode
(`_SEED = b"aladin37_secret_seed_..."`). Das ist keine akzeptable
V1-Vereinfachung, sondern ein Bug: jeder mit Lesezugriff auf die Datei
(Git-Repo, Backup, geteilter Code) kann damit beliebige Passports faelschen.

Hier gilt stattdessen:
- Der Private Key wird EINMALIG generiert und lokal auf Disk gespeichert
  (Datei-Permission 0600), NICHT im Code, NICHT in Git.
- In Produktion: aus einem Secret-Store/KMS laden (AWS KMS, Vault, etc.),
  dieser lokale Datei-Ansatz ist nur der V1-Ersatz dafuer.
- Der Public Key darf beliebig verteilt werden (Makler/Broker-Seite).
"""

from __future__ import annotations

import json
import os
import stat
from decimal import Decimal
from datetime import datetime
from pathlib import Path

import nacl.signing
import nacl.encoding

KEY_DIR = Path(__file__).parent.parent / "data" / "keys"
PRIVATE_KEY_PATH = KEY_DIR / "aladin37_signing_key.hex"


def _load_or_create_signing_key() -> nacl.signing.SigningKey:
    KEY_DIR.mkdir(parents=True, exist_ok=True)

    if PRIVATE_KEY_PATH.exists():
        seed_hex = PRIVATE_KEY_PATH.read_text().strip()
        return nacl.signing.SigningKey(seed_hex, encoder=nacl.encoding.HexEncoder)

    signing_key = nacl.signing.SigningKey.generate()
    seed_hex = signing_key.encode(encoder=nacl.encoding.HexEncoder).decode("utf-8")

    PRIVATE_KEY_PATH.write_text(seed_hex)
    # Nur der Besitzer darf lesen/schreiben - kein Gruppen-/World-Zugriff.
    os.chmod(PRIVATE_KEY_PATH, stat.S_IRUSR | stat.S_IWUSR)

    return signing_key


class AladinSigner:
    _signing_key = _load_or_create_signing_key()
    verify_key = _signing_key.verify_key

    @classmethod
    def get_public_key_hex(cls) -> str:
        return cls.verify_key.encode(encoder=nacl.encoding.HexEncoder).decode("utf-8")

    @staticmethod
    def _canonical_bytes(data: dict) -> bytes:
        def default(obj):
            if isinstance(obj, Decimal):
                return str(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Nicht serialisierbarer Typ: {type(obj)}")

        return json.dumps(data, sort_keys=True, ensure_ascii=False, default=default).encode("utf-8")

    @classmethod
    def sign(cls, payload: dict) -> str:
        canonical = cls._canonical_bytes(payload)
        signed = cls._signing_key.sign(canonical)
        return nacl.encoding.HexEncoder.encode(signed.signature).decode("utf-8")

    @classmethod
    def verify(cls, payload: dict, signature_hex: str, public_key_hex: str) -> bool:
        try:
            v_key = nacl.signing.VerifyKey(public_key_hex, encoder=nacl.encoding.HexEncoder)
            canonical = cls._canonical_bytes(payload)
            v_key.verify(canonical, bytes.fromhex(signature_hex))
            return True
        except Exception:
            return False
