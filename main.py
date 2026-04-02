import argparse
import asyncio
import sys
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if getattr(sys, 'frozen', False):
    os.system('chcp 65001 >nul 2>&1')

from rat.agent import Agent
from rat.console import Console

def main():
    parser = argparse.ArgumentParser(description="Remote Administration Tool")
    subparsers = parser.add_subparsers(dest="mode", required=True)
    
    agent_parser = subparsers.add_parser("agent")
    agent_parser.add_argument("--server", required=True, help="Server IP:PORT")
    
    console_parser = subparsers.add_parser("console")
    console_parser.add_argument("--host", default="0.0.0.0")
    console_parser.add_argument("--port", type=int, default=9876)
    
    args = parser.parse_args()
    
    if args.mode == "agent":
        host, port = args.server.split(":")
        agent = Agent(host, int(port))
        asyncio.run(agent.run())
    else:
        console = Console(args.host, args.port)
        asyncio.run(console.run())

if __name__ == "__main__":
    main()
