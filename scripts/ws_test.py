import asyncio
import json
import websockets

async def main():
    uri = "ws://127.0.0.1:8000/ws/stream?mode=clean&profile=single&stream=frames&start_at_end=false"
    async with websockets.connect(uri) as ws:
        while True:
            msg = await ws.recv()
            print(msg)

asyncio.run(main())