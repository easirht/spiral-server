# server.py  -  Spiral Race relay server
import json
import os
import random
from aiohttp import web, WSMsgType

rooms = {}  # code -> room dict


def new_code():
    while True:
        code = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=4))
        if code not in rooms:
            return code


def clean_name(name, fallback):
    name = str(name or "").strip()[:12]
    return name or fallback


def free_color(room, wanted=None):
    used = {p["color"] for p in room["players"]}
    if wanted in (0, 1, 2, 3) and wanted not in used:
        return wanted
    for c in range(4):
        if c not in used:
            return c
    return 0


async def send(ws, msg):
    try:
        await ws.send_str(json.dumps(msg))
    except Exception:
        pass


async def broadcast(room, msg):
    for p in room["players"]:
        await send(p["ws"], msg)


def lobby(room):
    return {
        "t": "lobby",
        "code": room["code"],
        "started": room["started"],
        "players": [{"name": p["name"], "color": p["color"]} for p in room["players"]],
    }


async def handle_ws(request):
    ws = web.WebSocketResponse(heartbeat=25)
    await ws.prepare(request)
    room = None
    me = None

    async for msg in ws:
        if msg.type != WSMsgType.TEXT:
            continue
        try:
            data = json.loads(msg.data)
        except Exception:
            continue
        t = data.get("t")

        if t == "create" and room is None:
            code = new_code()
            me = {"ws": ws, "name": clean_name(data.get("name"), "Player 1"), "color": 0}
            room = {"code": code, "players": [me], "started": False,
                    "current": 0, "rolling": False}
            rooms[code] = room
            await send(ws, lobby(room))

        elif t == "join" and room is None:
            code = str(data.get("code", "")).upper().strip()
            r = rooms.get(code)
            if r is None:
                await send(ws, {"t": "error", "msg": "Room not found"})
            elif r["started"]:
                await send(ws, {"t": "error", "msg": "Game already started"})
            elif len(r["players"]) >= 4:
                await send(ws, {"t": "error", "msg": "Room is full"})
            else:
                room = r
                n = len(room["players"]) + 1
                me = {"ws": ws, "name": clean_name(data.get("name"), f"Player {n}"),
                      "color": free_color(room)}
                room["players"].append(me)
                await broadcast(room, lobby(room))

        elif room is None:
            continue

        elif t == "color" and not room["started"]:
            c = data.get("color")
            if c in (0, 1, 2, 3) and all(p["color"] != c for p in room["players"]):
                me["color"] = c
                await broadcast(room, lobby(room))

        elif t == "start":
            if room["players"][0] is me and not room["started"] and len(room["players"]) >= 2:
                room["started"] = True
                room["current"] = 0
                room["rolling"] = False
                await broadcast(room, {
                    "t": "start",
                    "seed": random.randrange(1 << 30),
                    "players": [{"name": p["name"], "color": p["color"]} for p in room["players"]],
                })

        elif t == "roll":
            idx = room["players"].index(me)
            if room["started"] and room["current"] == idx and not room["rolling"]:
                room["rolling"] = True
                await broadcast(room, {"t": "roll", "i": idx, "v": random.randint(1, 6)})

        elif t == "done":
            idx = room["players"].index(me)
            if room["started"] and room["current"] == idx and room["rolling"]:
                room["rolling"] = False
                room["current"] = (idx + 1) % len(room["players"])
                await broadcast(room, {"t": "turn", "i": room["current"]})

        elif t == "win":
            idx = room["players"].index(me)
            if room["started"] and room["current"] == idx:
                room["started"] = False
                await broadcast(room, {"t": "over", "i": idx})
                await broadcast(room, lobby(room))

    # disconnect cleanup
    if room is not None and me in room["players"]:
        room["players"].remove(me)
        if not room["players"]:
            rooms.pop(room["code"], None)
        else:
            if room["started"]:
                room["started"] = False
                await broadcast(room, {"t": "abort", "name": me["name"]})
            await broadcast(room, lobby(room))
    return ws


async def health(request):
    return web.Response(text="Spiral Race server OK")


app = web.Application()
app.add_routes([web.get("/", health), web.get("/ws", handle_ws)])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    web.run_app(app, host="0.0.0.0", port=port)
