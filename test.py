# test.py  -  quick check that the server works
import asyncio
import aiohttp

URL = "http://localhost:8080/ws"


async def main():
    async with aiohttp.ClientSession() as s:
        a = await s.ws_connect(URL)
        b = await s.ws_connect(URL)
        await a.send_json({"t": "create", "name": "Rahat"})
        m = await a.receive_json()
        print("A lobby:", m)
        await b.send_json({"t": "join", "code": m["code"], "name": "Fahim"})
        print("B lobby:", await b.receive_json())
        print("A lobby:", await a.receive_json())
        await a.send_json({"t": "start"})
        print("A start:", await a.receive_json())
        print("B start:", await b.receive_json())
        await a.send_json({"t": "roll"})
        print("A roll:", await a.receive_json())
        print("B roll:", await b.receive_json())
        print("TEST OK")

asyncio.run(main())
