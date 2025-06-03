# -*- coding: utf-8 -*-

from __future__ import annotations


async def websocket_application(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
    while True:
        event = await receive()

        if event["type"] == "websocket.connect":
            await send({"type": "websocket.accept"})

        if event["type"] == "websocket.disconnect":
            break

        if event["type"] == "websocket.receive":
            if event["text"] == "ping":
                await send({"type": "websocket.send", "text": "pong!"})
