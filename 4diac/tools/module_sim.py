"""Modbus TCP simulator of a module's equipment, driven by the ``sim`` sections of its spec.

Every IO point with a Modbus address is a register: coils (c) and holding registers (h) are
written by FORTE, discrete inputs (d) and input registers (i) are computed here. Kinematics per
equipment item (``sim`` in modules/*.yaml):

``axis``   a position 0..1 moved by two BOOL outputs (``forward`` increases it) in ``travel_s``
           seconds; ``speed`` (an LREAL output) scales the rate relative to ``nominal``; the axis
           starts moving only after an output has been on for ``dead_s`` (so brake pulses do not
           move it); ``switches`` are inputs that are TRUE at their end position (0 or 1);
           ``position: {input, span}`` publishes the position as an LREAL input (0..span).
``servo``  records the angle of an LREAL output (None while it is off).
``values`` constant values of inputs.

    python 4diac/tools/module_sim.py modules/filling.yaml [--port 1502]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import socketserver
import struct
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from modgen.spec import ModuleSpec, load  # noqa: E402


class Axis:
    """One simulated axis."""
    def __init__(self, cfg):
        self.forward, self.backward = cfg["forward"], cfg["backward"]
        self.speed, self.nominal = cfg.get("speed"), float(cfg.get("nominal", 1.0))
        self.travel_s, self.dead_s = float(cfg["travel_s"]), float(cfg.get("dead_s", 0.0))
        self.position = float(cfg.get("start", 0.0))
        self.switches = {name: float(at) for name, at in cfg.get("switches", {}).items()}
        self.readout = cfg.get("position")
        self.on_since = None
        self.direction = 0


class ModuleSim:
    """Register image and kinematics of one module."""
    def __init__(self, spec: ModuleSpec):
        self.spec = spec
        self.lock = threading.Lock()
        self.bits = {}        # ("c"|"d", address) -> bool
        self.regs = {}        # ("h"|"i", address) -> int
        self.points = {}      # "<Equipment>.<Point>" -> (table, address)
        self.axes: dict[str, Axis] = {}
        self.servos: dict[str, str] = {}
        self.values: dict[str, float] = {}
        self.trace: list[tuple[float, str, object]] = []   # (time, "<Eq>.<Output>", value) of every output change
        self.shoot_through = 0
        for eq_name, eq in spec.equipment.items():
            for name, io in [*eq.inputs.items(), *eq.outputs.items()]:
                if io.modbus:
                    table, address = io.modbus[0], int(io.modbus[1:])
                    self.points[f"{eq_name}.{name}"] = (table, address)
                    (self.bits if table in "cd" else self.regs)[(table, address)] = 0 if table in "hi" else False
            sim = eq.sim or {}
            if "axis" in sim:
                self.axes[eq_name] = Axis(sim["axis"])
            if "servo" in sim:
                self.servos[eq_name] = sim["servo"]["output"]
            for name, value in sim.get("values", {}).items():
                self.values[f"{eq_name}.{name}"] = value
        self.step(0.0)

    # --- values in engineering units -------------------------------------------------------
    def output(self, eq: str, name: str):
        """Current value of an output: bool, or the LREAL value (None when off, i.e. raw 0)."""
        table, address = self.points[f"{eq}.{name}"]
        if table == "c":
            return self.bits[(table, address)]
        raw = self.regs[(table, address)]
        out = self.spec.equipment[eq].outputs[name]
        return None if raw == 0 else (raw - out.bias) / out.gain

    def set_input(self, eq: str, name: str, value):
        """Set an input in engineering units."""
        key = f"{eq}.{name}"
        if key not in self.points:
            return
        table, address = self.points[key]
        if table == "d":
            self.bits[(table, address)] = bool(value)
        else:
            scale = self.spec.equipment[eq].inputs[name].scale
            self.regs[(table, address)] = max(0, min(65535, int(round(float(value) / scale))))

    def position(self, eq: str) -> float:
        """Axis position 0..1."""
        with self.lock:
            return self.axes[eq].position

    def angle(self, eq: str):
        """Servo angle (None while off)."""
        with self.lock:
            return self.output(eq, self.servos[eq])

    def outputs_on(self):
        """Names of the outputs currently on."""
        with self.lock:
            on = []
            for key, (table, address) in self.points.items():
                if table == "c" and self.bits[(table, address)] or table == "h" and self.regs[(table, address)]:
                    on.append(key)
            return on

    # --- Modbus access ----------------------------------------------------------------------
    def read_bits(self, table, start, count):
        with self.lock:
            return [self.bits.get((table, a), False) for a in range(start, start + count)]

    def read_regs(self, table, start, count):
        with self.lock:
            return [self.regs.get((table, a), 0) for a in range(start, start + count)]

    def _record(self, table, address, value):
        name = next((k for k, v in self.points.items() if v == (table, address)), f"{table}{address}")
        eq, _, out = name.partition(".")
        if table == "h" and eq in self.spec.equipment and out in self.spec.equipment[eq].outputs:
            o = self.spec.equipment[eq].outputs[out]
            value = None if value == 0 else round((value - o.bias) / o.gain, 2)
        self.trace.append((time.monotonic(), name, value))

    def write_bit(self, address, value):
        with self.lock:
            if self.bits.get(("c", address)) != value:
                self._record("c", address, value)
            self.bits[("c", address)] = value
            for eq, axis in self.axes.items():
                if self.output(eq, axis.forward) and self.output(eq, axis.backward):
                    self.shoot_through += 1

    def write_reg(self, address, value):
        with self.lock:
            if self.regs.get(("h", address)) != value:
                self._record("h", address, value)
            self.regs[("h", address)] = value

    # --- kinematics -------------------------------------------------------------------------
    def step(self, dt):
        """Advance the kinematics by ``dt`` seconds."""
        with self.lock:
            now = time.monotonic()
            for eq, axis in self.axes.items():
                fwd, bwd = self.output(eq, axis.forward), self.output(eq, axis.backward)
                direction = (1 if fwd else 0) - (1 if bwd else 0)
                if direction != axis.direction:
                    axis.direction, axis.on_since = direction, now if direction else None
                rate = 1.0
                if axis.speed:
                    speed = self.output(eq, axis.speed)
                    rate = 0.0 if speed is None else speed / axis.nominal
                if direction and now - axis.on_since >= axis.dead_s:
                    axis.position = min(1.0, max(0.0, axis.position + direction * rate * dt / axis.travel_s))
                for name, at in axis.switches.items():
                    self.set_input(eq, name, axis.position >= at if at >= 0.5 else axis.position <= at)
                if axis.readout:
                    self.set_input(eq, axis.readout["input"], axis.position * float(axis.readout["span"]))
            for key, value in self.values.items():
                self.set_input(*key.split("."), value)


def _pack_bits(bits):
    data = bytearray((len(bits) + 7) // 8)
    for i, b in enumerate(bits):
        if b:
            data[i // 8] |= 1 << (i % 8)
    return bytes([len(data)]) + bytes(data)


class _Handler(socketserver.BaseRequestHandler):
    """Modbus TCP handler for one client connection (function codes 1-6, 15, 16)."""
    def handle(self):
        sim: ModuleSim = self.server.sim
        try:
            while True:
                header = self._recv(7)
                if not header:
                    return
                tid, pid, length, unit = struct.unpack(">HHHB", header)
                pdu = self._recv(length - 1)
                if pdu is None:
                    return
                reply = self._dispatch(sim, pdu)
                self.request.sendall(struct.pack(">HHHB", tid, pid, len(reply) + 1, unit) + reply)
        except (ConnectionResetError, ConnectionAbortedError):
            pass

    def _recv(self, n):
        data = b""
        while len(data) < n:
            chunk = self.request.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    @staticmethod
    def _dispatch(sim, pdu):
        fc = pdu[0]
        try:
            if fc in (1, 2):
                start, count = struct.unpack(">HH", pdu[1:5])
                return bytes([fc]) + _pack_bits(sim.read_bits("c" if fc == 1 else "d", start, count))
            if fc in (3, 4):
                start, count = struct.unpack(">HH", pdu[1:5])
                regs = sim.read_regs("h" if fc == 3 else "i", start, count)
                return bytes([fc, 2 * count]) + b"".join(struct.pack(">H", r) for r in regs)
            if fc == 5:
                address, value = struct.unpack(">HH", pdu[1:5])
                sim.write_bit(address, value == 0xFF00)
                return pdu[:5]
            if fc == 6:
                address, value = struct.unpack(">HH", pdu[1:5])
                sim.write_reg(address, value)
                return pdu[:5]
            if fc == 15:
                start, count, _ = struct.unpack(">HHB", pdu[1:6])
                for i in range(count):
                    sim.write_bit(start + i, bool(pdu[6 + i // 8] >> (i % 8) & 1))
                return pdu[:5]
            if fc == 16:
                start, count, _ = struct.unpack(">HHB", pdu[1:6])
                for i in range(count):
                    sim.write_reg(start + i, struct.unpack(">H", pdu[6 + 2 * i:8 + 2 * i])[0])
                return pdu[:5]
        except (IndexError, struct.error):
            return bytes([fc | 0x80, 3])
        return bytes([fc | 0x80, 1])


class SimServer(socketserver.ThreadingTCPServer):
    """Threaded Modbus TCP server with a kinematics loop; use as a context manager."""
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, sim: ModuleSim, host="127.0.0.1", port=1502, period=0.01):
        super().__init__((host, port), _Handler)
        self.sim = sim
        self._halt = threading.Event()
        self._workers = [threading.Thread(target=self.serve_forever, daemon=True),
                         threading.Thread(target=self._loop, args=(period,), daemon=True)]

    def _loop(self, period):
        last = time.monotonic()
        while not self._halt.wait(period):
            now = time.monotonic()
            self.sim.step(now - last)
            last = now

    def __enter__(self):
        for t in self._workers:
            t.start()
        return self

    def __exit__(self, *args):
        self._halt.set()
        self.shutdown()
        self.server_close()


def main():
    """Run the simulator of one module from the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", help="Module specification (modules/*.yaml)")
    parser.add_argument("--port", type=int, help="Default: the spec's Modbus port")
    args = parser.parse_args()
    spec = load(Path(args.spec))
    sim = ModuleSim(spec)
    port = args.port or spec.modbus.port
    with SimServer(sim, port=port):
        print(f"{spec.module} simulator on 127.0.0.1:{port}; Ctrl+C to stop", flush=True)
        try:
            while True:
                time.sleep(1)
                axes = " ".join(f"{eq}={sim.position(eq):.2f}" for eq in sim.axes)
                print(f"{axes} on={sim.outputs_on()}", flush=True)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
