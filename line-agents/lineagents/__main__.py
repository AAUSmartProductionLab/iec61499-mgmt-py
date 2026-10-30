"""python -m lineagents: the line's agents.

    python -m lineagents --aas http://localhost:8081 --embedded                 # a resource agent per module
    python -m lineagents --aas http://localhost:8081 --embedded --order Vial2mLAAS:3   # ... and three vials
    python -m lineagents --aas http://localhost:8081 --mqtt localhost:1883 --http 8095   # the lab stack

The manager starts a resource agent for every module the AAS server holds and keeps them in step with
it, and the order agent, which starts a product agent for every product ordered (lineagents.manager,
lineagents.orders). ``--embedded`` runs SPADE's own XMPP server in this process. Skills run on the
modules over OPC UA (``--executor opcua``), through the AAS server and the DMP (``--executor dmp``), or
are only simulated (``--executor simulated``). ``--http``: orders over HTTP as well (``POST /orders``
``{"product": "Vial2mLAAS", "quantity": 3}``, ``GET /orders``).
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from .manager import Manager
from .xmpp import embedded_server, run


async def main_async(args) -> int:
    async def go(port: int) -> int:
        manager = Manager(args.aas, args.xmpp_domain, port, args.executor, args.every, not args.no_reconfigure,
                          args.mqtt, args.http)
        await manager.start()
        print(f"agents: {', '.join(manager.resources()) or 'no module yet'}; orders to {manager.taker.jid}"
              f"{f' and http://localhost:{args.http}/orders' if args.http else ''}; watching {args.aas}", flush=True)
        try:
            orders = []
            for asked in args.order:
                product, _, quantity = asked.partition(":")
                orders += await manager.place(product, int(quantity or 1))
            for order in orders:
                await order.finished.wait()
                print(f"{order.jid}:", flush=True)
                for done in order.history:
                    print(f"  {done.step}: {done.outcome} by {done.resource or '-'} ({done.skill or '-'}), "
                          f"{done.proposals} proposals, {done.refusals} refusals, {done.seconds:.1f} s"
                          f"{'; ' + done.detail if done.detail else ''}", flush=True)
            if args.order and not args.stay:
                return 0 if all(d.outcome == "done" for o in orders for d in o.history) else 1
            while True:
                await asyncio.sleep(3600)
        finally:
            await manager.stop()

    if args.embedded:
        async with embedded_server(args.xmpp_domain, args.xmpp_port) as port:
            return await go(port)
    return await go(args.xmpp_port)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="lineagents", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aas", required=True, help="the AAS server, e.g. http://localhost:8081")
    parser.add_argument("--xmpp-domain", default="localhost")
    parser.add_argument("--xmpp-port", type=int, default=5222)
    parser.add_argument("--embedded", action="store_true", help="run SPADE's own XMPP server in this process")
    parser.add_argument("--executor", choices=("opcua", "dmp", "simulated"), default="opcua",
                        help="how skills run: over the module's OPC UA, through the AAS server and the DMP, or simulated")
    parser.add_argument("--every", type=float, default=5.0, help="seconds between reading the AAS server")
    parser.add_argument("--mqtt", help="the broker the AAS server publishes its events to (host:port): an agent starts "
                                       "as soon as its module's AAS is published")
    parser.add_argument("--no-reconfigure", action="store_true", help="never create a described skill on a module")
    parser.add_argument("--order", nargs="*", default=[], help="products to order once the agents run: AAS idShort[:quantity]")
    parser.add_argument("--http", type=int, help="take orders over HTTP on this port as well (POST /orders, GET /orders)")
    parser.add_argument("--stay", action="store_true", help="keep running after the orders")
    args = parser.parse_args(argv)
    try:
        return run(main_async(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
