"""Layout of a basic block's ECC (its state machine) as the 4diac IDE draws it.

The IDE draws a state as its name in a box with one row per action to its right (the algorithm,
then the output event), and a transition as a curve from its source through its condition, at the
transition's x and y, to its destination. So the states go in rows by how many transitions they
are from the initial state, each row ordered to keep the curves short, and every condition halfway
between its two states, moved aside where conditions would land on each other.

Sizes are IDE units (``layout``: a text row is about 100 units high, a character about 45 wide).
"""
from __future__ import annotations

from collections import defaultdict
import re

from .layout import CHAR, PIN_ROW

BOX = 100            # padding of each box of a state (name, algorithm, output)
COL_GAP = 700        # between the states of a row
ROW_GAP = 1100       # between rows: room for the conditions of the transitions between them
MOST = 10            # states in a row; a longer row goes on in the next
SPREAD = 160         # how far conditions that would overlap are moved apart
BOW, BOW_STEP = 1400, 500   # how far a transition over several rows bows out, and further each next one


def state_size(state) -> tuple[int, int]:
    """Width and height of a state as the IDE draws it."""
    actions = state.findall("ECAction")
    algorithm = max((len(a.get("Algorithm") or "") for a in actions), default=0)
    output = max((len(a.get("Output") or "") for a in actions), default=0)
    width = len(state.get("Name")) * CHAR + BOX
    if actions:
        width += (algorithm * CHAR + BOX if algorithm else 0) + (output * CHAR + BOX if output else 0)
    return width, max(1, len(actions)) * PIN_ROW + 60


def layers(names: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """States in rows below every state that leads to them (the longest way from the initial state,
    not counting the transitions back), so that no transition runs along a row; unreachable ones last."""
    out: dict[str, list[str]] = defaultdict(list)
    for s, d in edges:
        if d not in out[s]:
            out[s].append(d)
    back, seen, active = set(), set(), set()

    def visit(n):                       # depth first: a transition to a state still open goes back
        seen.add(n)
        active.add(n)
        for d in out[n]:
            if d in active:
                back.add((n, d))
            elif d not in seen:
                visit(d)
        active.discard(n)
    visit(names[0])
    forward = [(s, d) for s, d in edges if (s, d) not in back and s != d and s in seen and d in seen]
    depth = {names[0]: 0}
    for _ in range(len(names)):         # longest path over the forward transitions
        changed = False
        for s, d in forward:
            if s in depth and depth.get(d, -1) < depth[s] + 1:
                depth[d] = depth[s] + 1
                changed = True
        if not changed:
            break
    last = max(depth.values()) + 1
    rows: dict[int, list[str]] = defaultdict(list)
    for n in names:
        rows[depth.get(n, last)].append(n)
    return [rows[k] for k in sorted(rows)]


def order(rows: list[list[str]], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Each row ordered by where the states it is reached from are (two sweeps down)."""
    for _ in range(2):
        place: dict[str, float] = {}
        for row in rows:
            was = {n: i - (len(row) - 1) / 2 for i, n in enumerate(row)}
            key = {}
            for n in row:
                before = [place[s] for s, d in edges if d == n and s in place and s != n]
                key[n] = sum(before) / len(before) if before else was[n]
            row.sort(key=lambda n: (key[n], was[n]))
            for i, n in enumerate(row):
                place[n] = i - (len(row) - 1) / 2
    return rows


def lay_out(ecc) -> None:
    """Place every state and every transition's condition of an ECC element."""
    states = {s.get("Name"): s for s in ecc.findall("ECState")}
    transitions = ecc.findall("ECTransition")
    if not states:
        return
    edges = [(t.get("Source"), t.get("Destination")) for t in transitions]
    rows = []
    for row in order(layers(list(states), edges), edges):
        rows += [row[i:i + MOST] for i in range(0, len(row), MOST)]
    sizes = {n: state_size(s) for n, s in states.items()}
    widths = [sum(sizes[n][0] for n in row) + COL_GAP * (len(row) - 1) for row in rows]
    widest = max(widths)
    centre, y = {}, 0
    for row, width in zip(rows, widths):
        x = (widest - width) / 2
        height = max(sizes[n][1] for n in row)
        for n in row:
            states[n].set("x", str(round(x)))
            states[n].set("y", str(round(y)))
            x += sizes[n][0] + COL_GAP
        y += height + ROW_GAP
    place_transitions(ecc)


def place_transitions(ecc) -> None:
    """Every condition halfway between its states; those that would land on (nearly) the same place
    are spread apart."""
    centre = {}
    for s in ecc.findall("ECState"):
        w, h = state_size(s)
        centre[s.get("Name")] = (float(s.get("x", 0)) + w / 2, float(s.get("y", 0)) + h / 2)
    tops = {s.get("Name"): round(float(s.get("y", 0))) for s in ecc.findall("ECState")}
    rows = sorted(set(tops.values()))
    row = {n: rows.index(y) for n, y in tops.items()}
    transitions = ecc.findall("ECTransition")
    taken: dict[tuple[int, int], int] = defaultdict(int)
    bowed = 0
    for t in transitions:
        (x1, y1), (x2, y2) = centre[t.get("Source")], centre[t.get("Destination")]
        x, y = (x1 + x2) / 2, (y1 + y2) / 2
        if t.get("Source") == t.get("Destination"):
            x, y = x1, y1 - 500
        elif abs(row[t.get("Source")] - row[t.get("Destination")]) > 1:
            # Over rows between: bowed out to one side or the other, a little further each time, so
            # that such transitions neither lie on each other nor run through the states between.
            bowed += 1
            x += (1 if bowed % 2 else -1) * (BOW + BOW_STEP * ((bowed - 1) // 2))
        spot = (round(x / 400), round(y / 200))
        k = taken[spot]
        taken[spot] += 1
        # Every other one moves right, every other left; and down by a row of text each.
        shift = (k + 1) // 2 * (1 if k % 2 else -1)
        t.set("x", str(round(x + shift * SPREAD * 3)))
        t.set("y", str(round(y + shift * SPREAD)))


def condition(text: str, events: set[str]) -> str:
    """A condition as the IDE writes it: a guard without an event in brackets (``[Accepted]``)."""
    head = text.split("[", 1)[0].strip()
    adapter_event = bool(re.fullmatch(r"[A-Za-z_]\w*\.[A-Za-z_]\w*", head))   # Plug.EVENT, Socket.EVENT
    if text == "1" or head in events or adapter_event or text.startswith("["):
        return text
    return f"[{text}]"


OLD_GRID_X = {150 + 420 * k for k in range(4)}


def generated_before(ecc) -> bool:
    """Whether an ECC still has the grid the generator wrote before 4 Nov 2026 (nobody arranged it)."""
    states = ecc.findall("ECState")
    return all(int(float(s.get("x", 0))) in OLD_GRID_X and (int(float(s.get("y", 0))) - 100) % 230 == 0
               for s in states) and all(t.get("x") in (None, "0") and t.get("y") in (None, "0")
                                        for t in ecc.findall("ECTransition"))


def plain(text: str) -> str:
    """A condition without the IDE's brackets around a guard, to compare two ECCs."""
    return text[1:-1] if text.startswith("[") and text.endswith("]") else text


def structure(ecc) -> tuple:
    """What an ECC is, apart from where it is drawn."""
    return (tuple(s.get("Name") for s in ecc.findall("ECState")),
            tuple((t.get("Source"), t.get("Destination"), plain(t.get("Condition", "")))
                  for t in ecc.findall("ECTransition")))


def keep(new, old) -> bool:
    """Take an ECC's drawing from the file it replaces: only if somebody arranged it (it is not the
    old generated grid) and it is still the same state machine. Returns whether it was taken."""
    if old is None or generated_before(old) or structure(old) != structure(new):
        return False
    before = {s.get("Name"): s for s in old.findall("ECState")}
    for s in new.findall("ECState"):
        for attr in ("x", "y"):
            if attr in before[s.get("Name")].attrib:
                s.set(attr, before[s.get("Name")].get(attr))
    old_transitions = old.findall("ECTransition")
    if all(t.get("x") in (None, "0") and t.get("y") in (None, "0") for t in old_transitions):
        place_transitions(new)          # states arranged, conditions never moved: put them between
    else:
        for t, was in zip(new.findall("ECTransition"), old_transitions):
            for attr in ("x", "y"):
                if attr in was.attrib:
                    t.set(attr, was.get(attr))
    return True
