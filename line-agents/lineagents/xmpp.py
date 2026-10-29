"""The XMPP server the agents talk through.

SPADE brings one (pyjabber, ``spade run``): enough for a line on one computer, for the tests and for
the demo, with agents registering themselves on first start. A lab-wide deployment can use another
XMPP server (Prosody, ejabberd, Openfire) with in-band registration, or with the agents' accounts
made beforehand (docs/agents.md).
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import os
import socket
import tempfile


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@asynccontextmanager
async def embedded_server(domain: str = "localhost", port: int = 5222, server_port: int | None = None):
    """SPADE's XMPP server in this event loop, its accounts in a temporary file; yields its client port
    (``port=0``: a free one)."""
    import loguru
    from pyjabber.server import Server
    from pyjabber.server_parameters import Parameters
    loguru.logger.remove()                     # pyjabber logs every stanza
    port = port or free_port()
    # The accounts in a file of a folder of its own: with the database in memory, an account registered
    # by an agent in another process once the server runs was never answered.
    folder = tempfile.mkdtemp(prefix="xmpp-")
    server = Server(Parameters(host=domain, client_port=port, server_port=server_port or free_port(),
                               database_path=os.path.join(folder, "accounts.db"), database_purge=True,
                               message_persistence=False))
    task = asyncio.get_running_loop().create_task(server.start())
    await asyncio.wait_for(server.ready.wait(), 20)
    try:
        yield port
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):        # noqa: BLE001 (stopping)
            pass


def run(coro):
    """Run ``coro`` on SPADE's event loop (its container's: agents' queues belong to it) and return
    its result. The loop stays open for the next run."""
    from spade.container import Container
    return Container().loop.run_until_complete(coro)
