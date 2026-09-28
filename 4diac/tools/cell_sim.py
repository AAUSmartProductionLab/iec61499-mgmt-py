"""Minimal Modbus TCP simulator of the filling cell (no dependencies).

Register map (unit id ignored), matching generate_filling_cell.py:
  discrete inputs d0..d5: NeedleUp, NeedleDown, VialPresent, Stoppered, Checked, DoorClosed
  input registers i0, i1: FilledMl * 100, needle position below the top in 0.1 mm
  coils           c0..c4: MoveDown, Dose, MoveUp, Stopper, Inspect

Physics (when ``physics`` is on): the needle travels while exactly one of MoveDown/MoveUp is
energised; dosing adds ``fill_rate`` mL/s while the Dose coil is on; Stopper and Inspect set
their feedback after ``actuation_s``. Energising MoveDown and MoveUp together is recorded as a
shoot-through and moves nothing.

    python cell_sim.py --port 1502
"""
from __future__ import annotations

import argparse
import socketserver
import struct
import threading
import time

SENSORS = ["NeedleUp", "NeedleDown", "VialPresent", "Stoppered", "Checked", "DoorClosed"]
COILS = ["MoveDown", "Dose", "MoveUp", "Stopper", "Inspect"]


class Cell:
    """Simulated cell state and physics."""
    def __init__(self, physics=True, travel_s=0.3, actuation_s=0.3, fill_rate=1.0, travel_mm=50.0):
        self.lock = threading.Lock()
        self.inputs = {"NeedleUp": True, "NeedleDown": False, "VialPresent": True, "Stoppered": False,
                       "Checked": False, "DoorClosed": True}
        self.filled_ml = 0.0
        self.coils = {c: False for c in COILS}
        self.physics, self.travel_s, self.actuation_s, self.fill_rate = physics, travel_s, actuation_s, fill_rate
        self.travel_mm = travel_mm
        self.shoot_through = 0
        self.coil_trace: list[tuple[float, str, bool]] = []
        self._position = 0.0  # 0 = up, 1 = down
        self._since = {c: None for c in COILS}

    @property
    def position_mm(self):
        """Needle position below the top in mm."""
        with self.lock:
            return self._position * self.travel_mm

    def new_vial(self):
        """Replace the vial: present, empty, not stoppered, not checked."""
        with self.lock:
            self.inputs.update(VialPresent=True, Stoppered=False, Checked=False)
            self.filled_ml = 0.0

    def write_coil(self, index, value):
        """Set a coil from a Modbus write and record it."""
        with self.lock:
            name = COILS[index]
            if self.coils[name] != value:
                self.coil_trace.append((time.monotonic(), name, value))
            self.coils[name] = value
            self._since[name] = time.monotonic() if value else None
            if self.coils["MoveDown"] and self.coils["MoveUp"]:
                self.shoot_through += 1

    def step(self, dt):
        """Advance the physics by ``dt`` seconds."""
        with self.lock:
            if not self.physics:
                return
            down, up = self.coils["MoveDown"], self.coils["MoveUp"]
            if down != up:
                self._position += (dt if down else -dt) / self.travel_s
                self._position = min(1.0, max(0.0, self._position))
                self.inputs["NeedleUp"] = self._position <= 0.0
                self.inputs["NeedleDown"] = self._position >= 1.0
            if self.coils["Dose"] and self.inputs["NeedleDown"]:
                self.filled_ml += self.fill_rate * dt
            now = time.monotonic()
            for coil, feedback in [("Stopper", "Stoppered"), ("Inspect", "Checked")]:
                since = self._since[coil]
                if since is not None and now - since >= self.actuation_s:
                    self.inputs[feedback] = True

    def read_bits(self, table, start, count):
        """Read coils (c) or discrete inputs (d)."""
        with self.lock:
            source = [self.coils[c] for c in COILS] if table == "c" else [self.inputs[s] for s in SENSORS]
            return [source[i] if i < len(source) else False for i in range(start, start + count)]

    def read_registers(self, start, count):
        """Read input registers (i0 = FilledMl * 100, i1 = position in 0.1 mm)."""
        with self.lock:
            values = [min(65535, int(round(self.filled_ml * 100))), int(round(self._position * self.travel_mm * 10))]
            return [values[i] if i < len(values) else 0 for i in range(start, start + count)]


def _pack_bits(bits):
    """Pack bits into a byte-count-prefixed Modbus payload."""
    data = bytearray((len(bits) + 7) // 8)
    for i, b in enumerate(bits):
        if b:
            data[i // 8] |= 1 << (i % 8)
    return bytes([len(data)]) + bytes(data)


class _Handler(socketserver.BaseRequestHandler):
    """Modbus TCP handler for one client connection."""
    def handle(self):
        """Serve requests until the client disconnects."""
        cell: Cell = self.server.cell
        try:
            self._serve(cell)
        except (ConnectionResetError, ConnectionAbortedError):
            pass  # client went away

    def _serve(self, cell):
        """Read frames, dispatch them and send replies."""
        while True:
            header = self._recv(7)
            if not header:
                return
            tid, pid, length, unit = struct.unpack(">HHHB", header)
            pdu = self._recv(length - 1)
            if pdu is None:
                return
            reply = self._dispatch(cell, pdu)
            self.request.sendall(struct.pack(">HHHB", tid, pid, len(reply) + 1, unit) + reply)

    def _recv(self, n):
        """Read exactly ``n`` bytes, or None if the client closed."""
        data = b""
        while len(data) < n:
            chunk = self.request.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    @staticmethod
    def _dispatch(cell, pdu):
        """Execute one Modbus PDU and return the reply PDU."""
        fc = pdu[0]
        try:
            if fc in (1, 2):
                start, count = struct.unpack(">HH", pdu[1:5])
                return bytes([fc]) + _pack_bits(cell.read_bits("c" if fc == 1 else "d", start, count))
            if fc in (3, 4):
                start, count = struct.unpack(">HH", pdu[1:5])
                regs = cell.read_registers(start, count) if fc == 4 else [0] * count
                return bytes([fc, 2 * count]) + b"".join(struct.pack(">H", r) for r in regs)
            if fc == 5:
                address, value = struct.unpack(">HH", pdu[1:5])
                cell.write_coil(address, value == 0xFF00)
                return pdu[:5]
            if fc == 15:
                start, count, nbytes = struct.unpack(">HHB", pdu[1:6])
                for i in range(count):
                    cell.write_coil(start + i, bool(pdu[6 + i // 8] >> (i % 8) & 1))
                return pdu[:5]
            if fc in (6, 16):
                return pdu[:5]
        except (IndexError, struct.error):
            return bytes([fc | 0x80, 3])
        return bytes([fc | 0x80, 1])


class CellServer(socketserver.ThreadingTCPServer):
    """Threaded Modbus TCP server with a physics loop; use as a context manager."""
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, cell, host="127.0.0.1", port=1502, period=0.02):
        super().__init__((host, port), _Handler)
        self.cell = cell
        self._halt = threading.Event()
        self._workers = [threading.Thread(target=self.serve_forever, daemon=True),
                         threading.Thread(target=self._physics, args=(period,), daemon=True)]

    def _physics(self, period):
        """Step the physics every ``period`` seconds until stopped."""
        last = time.monotonic()
        while not self._halt.wait(period):
            now = time.monotonic()
            self.cell.step(now - last)
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
    """Run the simulator from the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1502)
    args = parser.parse_args()
    cell = Cell()
    with CellServer(cell, args.host, args.port):
        print(f"Filling-cell Modbus simulator on {args.host}:{args.port}; Ctrl+C to stop")
        try:
            while True:
                time.sleep(1)
                print({**cell.inputs, "FilledMl": round(cell.filled_ml, 2), "coils": cell.coils,
                       "shoot_through": cell.shoot_through})
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
