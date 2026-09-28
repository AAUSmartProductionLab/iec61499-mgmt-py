"""Reproducible, dependency-free source for the editable filling-cell 4diac project.

Run explicitly to regenerate XML; this overwrites edits to generated project files.

Structure (see docs/design.md, "Skill building blocks"):
  * one generic PackML state machine (SKILL_PackML), command gate (SKILL_Gate) and status
    chain link (SKILL_Chain) shared by every skill;
  * one SimpleFB per skill (SL_*) holding the only skill-specific code: its contract;
  * IO primitives (IO_DO/IO_DI/IO_AI) that select GPIO (IX/QX), Modbus (CLIENT) or simulated values;
  * OPC UA facades built from FORTE's generic SERVER/PUBLISH SIFBs;
  * one composite per skill (SK_*) wiring all of the above behind a uniform interface.
"""
from pathlib import Path
import copy
import json
import re
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / "FillingCellFixed"
TYPES = ROOT / "Type Library"
PKG = "fillingcell"
# Interface declarations of the few standard types used here, vendored from the 4diac IDE (3.3) type libraries
# type libraries (EPL-2.0). The headless IDE does not resolve library dependencies, so they are
# copied into the project instead of linked; FORTE provides their implementations.
STDTYPES = Path(__file__).resolve().parent / "stdtypes"
MANIFEST = []  # (qualified name, kind, relative file, exported to C++)

STD = {
    "E_DELAY": "iec61499::events::E_DELAY",
    "E_CYCLE": "iec61499::events::E_CYCLE",
    "E_RESTART": "iec61499::events::E_RESTART",
    "IX": "eclipse4diac::io::IX",
    "QX": "eclipse4diac::io::QX",
    "IW": "eclipse4diac::io::IW",
    "GPIOChip": "eclipse4diac::io::gpiochip::GPIOChip",
    "CLIENT_1_0": "iec61499::net::CLIENT_1_0",
    "CLIENT_0_1": "iec61499::net::CLIENT_0_1",
    "E_CTU": "iec61499::events::E_CTU",
    "E_T_FF": "iec61499::events::E_T_FF",
    "EMB_RES": "iec61499::system::EMB_RES",
    "FORTE_PC": "iec61499::system::FORTE_PC",
}


def q(name):
    """Qualify a type name with the project package."""
    return f"{PKG}::{name}"


def publish(n):
    """Qualified name of the generic PUBLISH_n SIFB."""
    return f"iec61499::net::PUBLISH_{n}"


# ---------------------------------------------------------------------------------------------
# Cell model: sensors, skills and their contracts. This table is the single source for the
# SL_* logic blocks and, later, for the AAS skills submodel (Requires/Ensures/Invariant).
# ---------------------------------------------------------------------------------------------
SENSORS = {"NeedleUp": "BOOL", "NeedleDown": "BOOL", "VialPresent": "BOOL",
           "FilledMl": "LREAL", "Stoppered": "BOOL", "Checked": "BOOL", "DoorClosed": "BOOL"}
CELL = {**SENSORS, "Valid": "BOOL", "Safe": "BOOL"}
CELL_TYPE = q("ST_CellState")
PARAMS = ["P1", "P2", "P3", "P4"]

SKILLS = {
    "MoveDown": dict(requires="NeedleUp AND NOT NeedleDown AND VialPresent",
                     ensures="NeedleDown AND NOT NeedleUp", invariant="VialPresent"),
    "Dose": dict(requires="NeedleDown AND VialPresent AND NOT Stoppered AND (P1 >= 0.1) AND (P1 <= 2.0)",
                 ensures="FilledMl >= TargetMl", invariant="NeedleDown AND VialPresent AND NOT Stoppered",
                 params={"P1": "VolumeMl [mL] 0.1..2.0"},
                 latch="TargetMl := Cell.FilledMl + P1;", internal={"TargetMl": "LREAL"}),
    "MoveUp": dict(requires="NeedleDown AND NOT NeedleUp",
                   ensures="NeedleUp AND NOT NeedleDown", invariant="TRUE"),
    "Stopper": dict(requires="NeedleUp AND VialPresent AND (FilledMl > 0.0) AND NOT Stoppered",
                    ensures="Stoppered", invariant="NeedleUp AND VialPresent"),
    "Inspect": dict(requires="NeedleUp AND VialPresent AND Stoppered AND NOT Checked",
                    ensures="Checked", invariant="NeedleUp AND VialPresent"),
}

# PackML state numbers, shared by unit, skills and the management boundary.
STATES = {"Clearing": 1, "Stopped": 2, "Starting": 3, "Idle": 4, "Suspended": 5, "Execute": 6,
          "Stopping": 7, "Aborting": 8, "Aborted": 9, "Holding": 10, "Held": 11,
          "Unholding": 12, "Suspending": 13, "Unsuspending": 14, "Resetting": 15,
          "Completing": 16, "Complete": 17}
QUIESCENT = ["Idle", "Complete", "Stopped", "Aborted"]
PROCEDURE_ACTIVE = ["Execute", "Holding", "Held", "Unholding", "Suspending", "Suspended", "Unsuspending"]
# Commands: Reset=1 Start=2 Hold=3 Unhold=4 Stop=5 Abort=6 Clear=7 Suspend=8 Unsuspend=9.
SKILL_COMMANDS = {"Reset": 1, "Start": 2, "Hold": 3, "Unhold": 4, "Stop": 5, "Abort": 6, "Clear": 7}
UNIT_COMMANDS = {"Reset": 1, "Start": 2, "Hold": 3, "Unhold": 4, "Stop": 5, "Abort": 6, "Clear": 7,
                 "Suspend": 8, "Unsuspend": 9}
# Occupation commands: Occupy=1 Release=2 Local=3 Prioritize=4 Remote=5.
OCC_COMMANDS = {"Occupy": 1, "Release": 2, "Local": 3, "Prioritize": 4, "Remote": 5}
# Error codes reported by skills and gates.
ERRORS = {"PreconditionViolated": 1, "InvariantViolated": 2, "Timeout": 3, "NotReady": 4,
          "NotPermitted": 5, "Busy": 6, "Interrupted": 7}

# Example hardware binding. Sensor/actuator names double as FORTE IO handle names on the Pi
# (GPIOChip VALUE = IX/QX PARAMS); Modbus addresses match cell/sim (unit 1 on port 1502).
MODBUS = "127.0.0.1:1502:1"
SENSOR_IO = {  # name: (BCM line, Modbus read address)
    "NeedleUp": (17, "d0"), "NeedleDown": (27, "d1"), "VialPresent": (22, "d2"),
    "Stoppered": (23, "d3"), "Checked": (24, "d4"), "DoorClosed": (25, "d5"),
    "FilledMl": (None, "i0"),
}
ACTUATOR_IO = {"MoveDown": (5, "c0"), "Dose": (13, "c1"), "MoveUp": (6, "c2"),
               "Stopper": (19, "c3"), "Inspect": (26, "c4")}
UA_ROOT = "/Objects/FillingCell/Filler"


def modbus_read(addr):
    """Modbus ID that polls one input address."""
    return f"modbus[{MODBUS}:50:{addr}:]"


def modbus_write(addr):
    """Modbus ID that writes one output address."""
    return f"modbus[{MODBUS}:0::{addr}]"


def cell_expr(expr):
    """Rewrite a contract expression over state variables into ST over the Cell struct."""
    return re.sub(r"\b(" + "|".join(CELL) + r")\b", r"Cell.\1", expr)


# ---------------------------------------------------------------------------------------------
# XML builders
# ---------------------------------------------------------------------------------------------
def elem(parent, tag, **attrs):
    """Append an XML child with stringified attributes."""
    return ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})


def save(root, path):
    """Indent and write an XML tree, creating folders."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def spec(v):
    """Split a variable spec into (type, initial value)."""
    return v if isinstance(v, tuple) else (v, None)


def interface(root, inputs, outputs, iv=None, ov=None):
    """inputs/outputs: {event: [vars]} or {event: ([vars], "EInit")}."""
    iface = elem(root, "InterfaceList")
    for tag, events in [("EventInputs", inputs), ("EventOutputs", outputs)]:
        group = elem(iface, tag)
        for name, variables in events.items():
            variables, etype = variables if isinstance(variables, tuple) else (variables, "Event")
            event = elem(group, "Event", Name=name, Type=etype)
            for var in variables:
                elem(event, "With", Var=var)
    for tag, variables in [("InputVars", iv or {}), ("OutputVars", ov or {})]:
        group = elem(iface, tag)
        for name, value in variables.items():
            typ, initial = spec(value)
            attrs = dict(Name=name, Type=typ)
            if initial is not None:
                attrs["InitialValue"] = initial
            elem(group, "VarDeclaration", **attrs)
    return iface


class TypeFile:
    """Header and writing shared by all 4diac type files."""
    folder = ""
    ext = ".fbt"
    exported = True
    kind = ""

    def header(self, tag, name, comment, package=PKG):
        """Create the root element with identification, version and package."""
        self.name = name
        self.package = package
        self.root = ET.Element(tag, Name=name, Comment=comment)
        elem(self.root, "Identification", Standard="61499-2")
        elem(self.root, "VersionInfo", Organization="Filling cell reference model", Version="2.0",
             Author="Project contributors", Date="2026-09-27")
        elem(self.root, "CompilerInfo", packageName=package)

    def write(self):
        """Write the file and record it in the type manifest."""
        rel = Path(self.folder) / (self.name + self.ext)
        save(self.root, TYPES / rel)
        MANIFEST.append((f"{self.package}::{self.name}", self.kind, rel.as_posix(), self.exported))


class Struct(TypeFile):
    """Structured data type (.dtp)."""
    ext = ".dtp"
    kind = "Struct"

    def __init__(self, name, comment, members, folder):
        self.header("DataType", name, comment)
        self.folder = folder
        st = elem(self.root, "StructuredType")
        for n, t in members.items():
            elem(st, "VarDeclaration", Name=n, Type=t)


class FB(TypeFile):
    """FB type with an interface list."""
    def __init__(self, name, comment, ei, eo, iv=None, ov=None, folder="", package=PKG):
        self.header("FBType", name, comment, package)
        self.folder = folder
        interface(self.root, ei, eo, iv, ov)


class Basic(FB):
    """Basic FB built from ECC states, transitions and ST algorithms."""
    kind = "BasicFB"

    def __init__(self, name, comment, ei, eo, iv=None, ov=None, internal=None, folder=""):
        super().__init__(name, comment, ei, eo, iv, ov, folder)
        self.body = elem(self.root, "BasicFB")
        if internal:
            vs = elem(self.body, "InternalVars")
            for n, t in internal.items():
                typ, initial = spec(t)
                attrs = dict(Name=n, Type=typ)
                if initial is not None:
                    attrs["InitialValue"] = initial
                elem(vs, "VarDeclaration", **attrs)
        self.ecc = elem(self.body, "ECC")
        self.transitions = []
        self.algorithms = {}

    def state(self, name, code=None, output=None, extra=()):
        """Add an ECC state with an optional algorithm and output events."""
        n = len(self.ecc)
        state = elem(self.ecc, "ECState", Name=name, x=150 + (n % 4) * 420, y=100 + (n // 4) * 230)
        outputs = ([output] if output else []) + list(extra)
        if code is not None:
            self.algorithms[name] = code
            attrs = {"Algorithm": "Alg_" + name}
            if outputs:
                attrs["Output"] = outputs.pop(0)
            elem(state, "ECAction", **attrs)
        for out in outputs:
            elem(state, "ECAction", Output=out)

    def trans(self, source, target, condition):
        """Add an ECC transition; earlier transitions have priority."""
        self.transitions.append((source, target, condition))

    def write(self):
        """Emit transitions and algorithms, then write the file."""
        for source, target, condition in self.transitions:
            elem(self.ecc, "ECTransition", Source=source, Destination=target, Condition=condition, x=0, y=0)
        for name, code in self.algorithms.items():
            alg = elem(self.body, "Algorithm", Name="Alg_" + name)
            elem(alg, "ST", Text=code)
        super().write()


class Simple(FB):
    """SimpleFB: one algorithm per input event, each confirmed by one output event."""
    kind = "SimpleFB"

    def __init__(self, name, comment, ei, eo, iv, ov, algorithms, internal=None, folder=""):
        super().__init__(name, comment, ei, eo, iv, ov, folder)
        body = elem(self.root, "SimpleFB")
        if internal:
            vs = elem(body, "InternalVars")
            for n, t in internal.items():
                elem(vs, "VarDeclaration", Name=n, Type=t)
        for event, (code, output) in algorithms.items():
            state = elem(body, "ECState", Name=event)
            elem(state, "ECAction", Algorithm=event, Output=output)
        for event, (code, _) in algorithms.items():
            alg = elem(body, "Algorithm", Name=event)
            elem(alg, "ST", Text=code)


class Composite(FB):
    """Composite FB with an internal FB network."""
    kind = "CompositeFB"

    def __init__(self, name, comment, ei, eo, iv=None, ov=None, folder=""):
        super().__init__(name, comment, ei, eo, iv, ov, folder)
        self.net = elem(self.root, "FBNetwork")
        self.fbs = []
        self.events = []
        self.data = []

    def fb(self, name, typ, **params):
        """Add an internal FB instance."""
        self.fbs.append((name, typ, params))
        return name

    def ev(self, source, *destinations):
        """Add event connections from ``source`` to each destination."""
        for d in destinations:
            self.events.append((source, d))

    def da(self, source, *destinations):
        """Add data connections from ``source`` to each destination."""
        for d in destinations:
            self.data.append((source, d))

    def write(self):
        """Emit the network, then write the file."""
        for i, (name, typ, params) in enumerate(self.fbs):
            fb = elem(self.net, "FB", Name=name, Type=typ, x=400 + (i % 4) * 2600, y=200 + (i // 4) * 1800)
            for p, v in params.items():
                elem(fb, "Parameter", Name=p, Value=v)
        ec, dc = elem(self.net, "EventConnections"), elem(self.net, "DataConnections")
        for s, d in self.events:
            elem(ec, "Connection", Source=s, Destination=d)
        for s, d in self.data:
            elem(dc, "Connection", Source=s, Destination=d)
        super().write()


class GenericComm(FB):
    """Interface-only declaration of a generic FORTE comm FB size missing from the IDE library.

    FORTE instantiates these from GEN_SERVER at runtime; they must not be exported to C++.
    """
    kind = "GenericComm"
    exported = False

    def __init__(self, sds, rds):
        name = f"SERVER_{sds}_{rds}"
        super().__init__(name, f"OPC UA method/Server FB: {rds} arguments in, {sds} out (generic)",
                         {"INIT": (["QI", "ID"], "EInit"), "RSP": ["QI"] + [f"SD_{i}" for i in range(1, sds + 1)]},
                         {"INITO": (["QO", "STATUS"], "EInit"),
                          "IND": ["QO", "STATUS"] + [f"RD_{i}" for i in range(1, rds + 1)]},
                         {"QI": "BOOL", "ID": "WSTRING", **{f"SD_{i}": "ANY" for i in range(1, sds + 1)}},
                         {"QO": "BOOL", "STATUS": "WSTRING", **{f"RD_{i}": "ANY" for i in range(1, rds + 1)}},
                         folder="Generic", package="iec61499::net")
        elem(self.root, "Attribute", Name="eclipse4diac::core::GenericClassName", Value="'GEN_SERVER'")


def server(sds, rds):
    """Qualified SERVER_x_y type; records the size for a declaration."""
    SERVERS.add((sds, rds))
    return f"iec61499::net::SERVER_{sds}_{rds}"


SERVERS = set()


def wstr(text):
    """Quote text as a WSTRING literal."""
    return '"' + text + '"'


# ---------------------------------------------------------------------------------------------
# Generic skill building blocks
# ---------------------------------------------------------------------------------------------
def make_cell_state():
    """Generate the ST_CellState struct."""
    Struct("ST_CellState", "Coherent snapshot of the cell state variables (contract vocabulary)",
           CELL, "DataTypes").write()


def make_packml():
    """Generate the shared PackML skill state machine."""
    b = Basic("SKILL_PackML",
              "Reduced PackML skill state machine shared by all skills; completion by Ensures, "
              "abort on Invariant violation or watchdog timeout",
              {"CMD": ["Command", "RequiresOK"], "COND": ["EnsuresOK", "InvariantOK"], "TIMEOUT": []},
              {"CNF": ["State", "ErrorID", "Active"], "LATCH": [], "REJECTED": ["ErrorID"],
               "WD_START": [], "WD_STOP": []},
              {"Command": "USINT", "RequiresOK": "BOOL", "EnsuresOK": "BOOL", "InvariantOK": "BOOL"},
              {"State": ("USINT", "4"), "ErrorID": "UINT", "Active": "BOOL"}, folder="Skills/Base")
    extra = {"Starting": ["LATCH", "CNF"], "Execute": ["CNF", "WD_START"],
             "Completing": ["CNF", "WD_STOP"], "Holding": ["CNF", "WD_STOP"],
             "Stopping": ["CNF", "WD_STOP"], "Aborting": ["CNF", "WD_STOP"]}
    for s in ["Idle", "Starting", "Execute", "Completing", "Complete", "Resetting", "Holding", "Held",
              "Unholding", "Stopping", "Stopped", "Aborting", "Aborted", "Clearing"]:
        code = f"State := {STATES[s]};\nActive := {'TRUE' if s == 'Execute' else 'FALSE'};"
        if s in ["Starting", "Resetting", "Clearing"]:
            code += "\nErrorID := 0;"
        outs = extra.get(s, ["CNF"])
        b.state(s, code, outs[0], outs[1:])
    b.state("Rejected", f"ErrorID := {ERRORS['PreconditionViolated']};", "REJECTED")
    b.state("Unsafe", f"ErrorID := {ERRORS['InvariantViolated']};")
    b.state("Timeout", f"ErrorID := {ERRORS['Timeout']};")
    b.trans("Idle", "Starting", "CMD[(Command = 2) AND RequiresOK]")
    b.trans("Idle", "Rejected", "CMD[Command = 2]")
    b.trans("Rejected", "Idle", "1")
    b.trans("Starting", "Execute", "1")
    # Safety is checked before completion on the same condition event.
    b.trans("Execute", "Unsafe", "COND[NOT InvariantOK]")
    b.trans("Execute", "Completing", "COND[EnsuresOK]")
    b.trans("Execute", "Timeout", "TIMEOUT")
    b.trans("Unsafe", "Aborting", "1")
    b.trans("Timeout", "Aborting", "1")
    b.trans("Execute", "Holding", "CMD[Command = 3]")
    b.trans("Holding", "Held", "1")
    b.trans("Held", "Unholding", "CMD[(Command = 4) AND InvariantOK]")
    b.trans("Held", "Unsafe", "COND[NOT InvariantOK]")
    b.trans("Unholding", "Execute", "1")
    b.trans("Completing", "Complete", "1")
    for s in ["Idle", "Complete", "Stopped"]:
        b.trans(s, "Resetting", "CMD[Command = 1]")
    b.trans("Resetting", "Idle", "1")
    for s in ["Idle", "Execute", "Held", "Complete", "Stopped"]:
        b.trans(s, "Aborting", "CMD[Command = 6]")
        if s != "Stopped":
            b.trans(s, "Stopping", "CMD[Command = 5]")
    b.trans("Stopping", "Stopped", "1")
    b.trans("Aborting", "Aborted", "1")
    b.trans("Aborted", "Clearing", "CMD[Command = 7]")
    b.trans("Clearing", "Stopped", "1")
    b.write()


def make_gate():
    """Arbitrates procedure calls, OPC UA manual commands and unit control for one skill."""
    unit = ["UnitRunning", "UnitQuiescent", "UnitState", "Mode", "Owner", "RemoteAllowed"]
    iv = {**{p: "LREAL" for p in PARAMS}, "ControlCode": "USINT",
          "UnitRunning": "BOOL", "UnitQuiescent": "BOOL", "UnitState": "USINT", "Mode": "USINT",
          "Owner": "UDINT", "RemoteAllowed": "BOOL",
          "Requester": "UDINT", "MCode": "USINT", **{"M" + p: "LREAL" for p in PARAMS},
          "State": ("USINT", "4"), "SkillError": "UINT"}
    ov = {"Command": "USINT", **{"PO" + p[1]: "LREAL" for p in PARAMS}, "CallError": "UINT", "MErr": "UINT"}
    b = Basic("SKILL_Gate",
              "Command authority for one skill: procedure calls only while the unit runs; OPC UA "
              "commands only from the occupation owner outside Production; unit control always",
              {"CALL": PARAMS, "UNIT_CTL": ["ControlCode"], "UNIT_STAT": unit,
               "MCMD": ["Requester", "MCode"] + ["M" + p for p in PARAMS],
               "TRACK": ["State", "SkillError"], "REJ": ["SkillError"]},
              {"CMD": ["Command"], "START": ["Command"] + ["PO" + p[1] for p in PARAMS],
               "DONE": [], "FAILED": ["CallError"], "M_ACK": [], "M_REJ": ["MErr"], "POKE": []},
              iv, ov, {"CallPending": "BOOL", "PendingStart": "BOOL", "MPending": "BOOL",
                       "ManualOK": "BOOL", "Valid": "BOOL"}, folder="Skills/Base")
    e = ERRORS
    copy_call = "\n".join(f"PO{p[1]} := {p};" for p in PARAMS)
    copy_manual = "\n".join(f"PO{p[1]} := M{p};" for p in PARAMS)
    b.state("START")
    # Procedure call port.
    b.state("Call", f"CallError := 0;\nIF NOT UnitRunning THEN CallError := {e['NotPermitted']};\n"
                    f"ELSIF CallPending OR MPending THEN CallError := {e['Busy']};\nEND_IF;\n{copy_call}")
    b.state("CallFail", None, "FAILED")
    b.state("CallStart", "CallPending := TRUE;\nCommand := 2;", "START")
    b.state("CallReset", "CallPending := TRUE;\nPendingStart := TRUE;\nCommand := 1;", "CMD")
    b.state("CallNotReady", f"CallError := {e['NotReady']};", "FAILED")
    b.trans("START", "Call", "CALL")
    b.trans("Call", "CallFail", "CallError <> 0")
    b.trans("Call", "CallStart", "State = 4")
    b.trans("Call", "CallReset", "(State = 17) OR (State = 2)")
    b.trans("Call", "CallNotReady", "1")
    for s in ["CallFail", "CallStart", "CallReset", "CallNotReady"]:
        b.trans(s, "START", "1")
    # Unit control is forwarded unconditionally; POKE refreshes the status chain even when the
    # skill ignores the command, so the unit always gets a STATUS after CONTROL.
    b.state("Control", "Command := ControlCode;\nIF (ControlCode = 5) OR (ControlCode = 6) THEN PendingStart := FALSE; END_IF;",
            "CMD", ["POKE"])
    b.trans("START", "Control", "UNIT_CTL")
    b.trans("Control", "START", "1")
    # OPC UA manual commands.
    valid = {1: "(State = 4) OR (State = 17) OR (State = 2)", 2: "State = 4", 3: "State = 6", 4: "State = 11",
             5: "(State = 4) OR (State = 6) OR (State = 11) OR (State = 17)",
             6: "(State = 4) OR (State = 6) OR (State = 11) OR (State = 17) OR (State = 2)", 7: "State = 9"}
    case = "\n".join(f"{c}: Valid := {x};" for c, x in valid.items())
    b.state("Manual",
            f"MErr := 0;\nValid := FALSE;\nCASE MCode OF\n{case}\nEND_CASE;\n"
            "ManualOK := RemoteAllowed AND (Requester = Owner) AND (Requester <> 0) AND (Mode <> 0) "
            "AND NOT CallPending AND NOT MPending;\n"
            "IF MCode = 2 THEN ManualOK := ManualOK AND UnitQuiescent AND (UnitState <> 9); END_IF;\n"
            f"IF NOT ManualOK THEN MErr := {e['NotPermitted']};\nELSIF NOT Valid THEN MErr := {e['NotReady']};\nEND_IF;\n"
            f"Command := MCode;\n{copy_manual}")
    b.state("MReject", None, "M_REJ")
    b.state("MStart", "MPending := TRUE;", "START")
    b.state("MForward", None, "CMD", ["M_ACK"])
    b.trans("START", "Manual", "MCMD")
    b.trans("Manual", "MReject", "MErr <> 0")
    b.trans("Manual", "MStart", "MCode = 2")
    b.trans("Manual", "MForward", "1")
    for s in ["MReject", "MStart", "MForward"]:
        b.trans(s, "START", "1")
    # Skill state tracking: start handshake, completion and failure reporting.
    b.state("MStarted", "MPending := FALSE;", "M_ACK")
    b.state("StartAfterReset", "PendingStart := FALSE;\nCommand := 2;", "START")
    b.state("CallDone", "CallPending := FALSE;", "DONE")
    b.state("CallAborted", f"CallPending := FALSE;\nPendingStart := FALSE;\nCallError := SkillError;\n"
                           f"IF CallError = 0 THEN CallError := {e['Interrupted']}; END_IF;", "FAILED")
    # Starting passes to Execute in the same ECC run, so TRACK may already read Execute (or
    # later): data at event reception is the current output value, not the value at emission.
    b.trans("START", "MStarted", "TRACK[MPending AND (State <> 4)]")
    b.trans("START", "StartAfterReset", "TRACK[PendingStart AND (State = 4)]")
    b.trans("START", "CallDone", "TRACK[CallPending AND (State = 17)]")
    b.trans("START", "CallAborted", "TRACK[CallPending AND ((State = 9) OR ((State = 2) AND NOT PendingStart))]")
    b.state("MStartRejected", "MPending := FALSE;\nMErr := SkillError;", "M_REJ")
    b.state("CallRejected", "CallPending := FALSE;\nCallError := SkillError;", "FAILED")
    b.trans("START", "MStartRejected", "REJ[MPending]")
    b.trans("START", "CallRejected", "REJ[CallPending]")
    for s in ["MStarted", "StartAfterReset", "CallDone", "CallAborted", "MStartRejected", "CallRejected"]:
        b.trans(s, "START", "1")
    b.write()


def make_chain():
    """Generate the status-chain link."""
    Simple("SKILL_Chain",
           "Status chain link: aggregates Busy/Held/Running along the skills of an equipment module",
           {"REQ": ["BusyIn", "HeldIn", "RunIn", "State"]}, {"CNF": ["BusyOut", "HeldOut", "RunOut"]},
           {"BusyIn": "BOOL", "HeldIn": ("BOOL", "TRUE"), "RunIn": ("BOOL", "TRUE"), "State": ("USINT", "4")},
           {"BusyOut": "BOOL", "HeldOut": "BOOL", "RunOut": "BOOL"},
           {"REQ": ("MyBusy := NOT ((State = 4) OR (State = 17) OR (State = 2) OR (State = 9));\n"
                    "BusyOut := BusyIn OR MyBusy;\n"
                    "HeldOut := HeldIn AND ((NOT MyBusy) OR (State = 11));\n"
                    "RunOut := RunIn AND ((NOT MyBusy) OR (State = 6));", "CNF")},
           {"MyBusy": "BOOL"}, folder="Skills/Base").write()


def make_skill_logic(name, s):
    """Generate the contract SimpleFB SL_<name> of one skill."""
    params = "\n".join(f"{p}L := {p};" for p in PARAMS)
    requires = cell_expr(s["requires"])
    Simple("SL_" + name,
           f"{name} contract: Requires {s['requires']}; Ensures {s['ensures']}; Invariant {s['invariant']}",
           {"CHECK": ["Cell"] + PARAMS, "LATCH": ["Cell"] + PARAMS, "EVAL": ["Cell"]},
           {"CHECKED": ["RequiresOK"], "LATCHED": [p + "L" for p in PARAMS], "COND": ["EnsuresOK", "InvariantOK"]},
           {"Cell": CELL_TYPE, **{p: "LREAL" for p in PARAMS}},
           {"RequiresOK": "BOOL", "EnsuresOK": "BOOL", "InvariantOK": "BOOL", **{p + "L": "LREAL" for p in PARAMS}},
           {"CHECK": (f"RequiresOK := Cell.Valid AND Cell.Safe AND ({requires});", "CHECKED"),
            "LATCH": (params + ("\n" + s["latch"] if s.get("latch") else ""), "LATCHED"),
            "EVAL": (f"EnsuresOK := {cell_expr(s['ensures'])};\n"
                     f"InvariantOK := Cell.Valid AND Cell.Safe AND ({cell_expr(s['invariant'])});", "COND")},
           s.get("internal"), folder="Skills/Logic").write()


# ---------------------------------------------------------------------------------------------
# IO primitives: GPIO (IX/QX via GPIOChip handles), Modbus (CLIENT) or simulated values
# ---------------------------------------------------------------------------------------------
def make_io_route(kind):
    """Backend 0 = simulated, 1 = GPIO (IX/QX/IW), 2 = Modbus CLIENT."""
    vtype = {"DO": "BOOL", "DI": "BOOL", "AI": "LREAL"}[kind]
    raw = {"DO": "BOOL", "DI": "BOOL", "AI": "WORD"}[kind]
    ei = {"INIT": ["Backend"], "IO_READY": ["QO_G", "QO_M"], "CNF_G": ["QO_G"], "CNF_M": ["QO_M"]}
    iv = {"Backend": "USINT", "QO_G": "BOOL", "QO_M": "BOOL"}
    eo = {"INIT_IO": ["GQI", "MQI"], "INITO": ["QO"], "REQ_G": [], "REQ_M": [], "CNF": ["QO"]}
    ov = {"GQI": "BOOL", "MQI": "BOOL", "QO": "BOOL"}
    if kind == "DO":
        ei["REQ"] = ["OUT"]
        iv["OUT"] = "BOOL"
        eo["REQ_G"] = eo["REQ_M"] = ["Value"]
        ov["Value"] = "BOOL"
    else:
        ei["REQ"] = ["SimValue"] + (["Scale"] if kind == "AI" else [])
        ei["CNF_G"] = ["QO_G", "IN_G"]
        ei["CNF_M"] = ["QO_M", "IN_M"]
        iv.update({"SimValue": vtype, "IN_G": raw, "IN_M": raw})
        if kind == "AI":
            iv["Scale"] = ("LREAL", "1.0")
        eo["CNF"] = ["QO", "IN"]
        ov["IN"] = vtype
    b = Basic(f"IO_Route{kind}", f"Backend router for IO_{kind}: 0 simulated, 1 GPIO, 2 Modbus",
              ei, eo, iv, ov, folder="IO/Base")
    b.state("START")
    b.state("Init", "GQI := Backend = 1;\nMQI := Backend = 2;", "INIT_IO")
    b.state("Ready", "QO := (Backend = 0) OR ((Backend = 1) AND QO_G) OR ((Backend = 2) AND QO_M);", "INITO")
    b.trans("START", "Init", "INIT")
    b.trans("Init", "START", "1")
    b.trans("START", "Ready", "IO_READY")
    b.trans("Ready", "START", "1")
    if kind == "DO":
        b.state("Req", "Value := OUT;")
        b.state("ReqG", None, "REQ_G")
        b.state("ReqM", None, "REQ_M")
        b.state("Sim", "QO := TRUE;", "CNF")
        b.trans("START", "Req", "REQ")
        b.trans("Req", "ReqG", "Backend = 1")
        b.trans("Req", "ReqM", "Backend = 2")
        b.trans("Req", "Sim", "1")
        b.state("DoneG", "QO := QO_G;", "CNF")
        b.state("DoneM", "QO := QO_M;", "CNF")
    else:
        conv = "UINT_TO_LREAL(WORD_TO_UINT({0})) * Scale" if kind == "AI" else "{0}"
        b.state("ReqG", None, "REQ_G")
        b.state("ReqM", None, "REQ_M")
        b.state("Sim", "QO := TRUE;\nIN := SimValue;", "CNF")
        b.trans("START", "ReqG", "REQ[Backend = 1]")
        b.trans("START", "ReqM", "REQ[Backend = 2]")
        b.trans("START", "Sim", "REQ")
        b.state("DoneG", f"QO := QO_G;\nIN := {conv.format('IN_G')};", "CNF")
        b.state("DoneM", f"QO := QO_M;\nIN := {conv.format('IN_M')};", "CNF")
    b.trans("START", "DoneG", "CNF_G")
    b.trans("START", "DoneM", "CNF_M")
    for s in ["ReqG", "ReqM", "Sim", "DoneG", "DoneM"]:
        b.trans(s, "START", "1")
    b.write()


def make_io(kind):
    """Generate the IO_DO, IO_DI or IO_AI composite."""
    vtype = {"DO": "BOOL", "DI": "BOOL", "AI": "LREAL"}[kind]
    gpio = {"DO": STD["QX"], "DI": STD["IX"], "AI": STD["IW"]}[kind]
    client = STD["CLIENT_1_0"] if kind == "DO" else STD["CLIENT_0_1"]
    iv = {"Backend": "USINT", "GpioName": "STRING", "ModbusId": "WSTRING"}
    ev_in = {"INIT": (["Backend", "GpioName", "ModbusId"], "EInit")}
    ev_out = {"INITO": (["QO"], "EInit")}
    ov = {"QO": "BOOL"}
    if kind == "DO":
        ev_in["REQ"] = ["OUT"]
        iv["OUT"] = "BOOL"
        ev_out["CNF"] = ["QO"]
    else:
        ev_in["REQ"] = ["SimValue"] + (["Scale"] if kind == "AI" else [])
        iv["SimValue"] = vtype
        if kind == "AI":
            iv["Scale"] = ("LREAL", "1.0")
        ev_out["CNF"] = ["QO", "IN"]
        ov["IN"] = vtype
    c = Composite(f"IO_{kind}", f"{'Digital output' if kind == 'DO' else 'Digital input' if kind == 'DI' else 'Analog input'}"
                  f" primitive; Backend 0 simulated, 1 GPIO ({gpio.split('::')[-1]} + GPIOChip handle), 2 Modbus CLIENT",
                  ev_in, ev_out, iv, ov, folder="IO")
    c.fb("Route", q(f"IO_Route{kind}"))
    c.fb("Gpio", gpio)
    c.fb("Bus", client)
    c.ev("INIT", "Route.INIT")
    c.ev("Route.INIT_IO", "Gpio.INIT")
    c.ev("Gpio.INITO", "Bus.INIT")
    c.ev("Bus.INITO", "Route.IO_READY")
    c.ev("Route.INITO", "INITO")
    c.ev("REQ", "Route.REQ")
    c.ev("Route.REQ_G", "Gpio.REQ")
    c.ev("Route.REQ_M", "Bus.REQ")
    c.ev("Gpio.CNF", "Route.CNF_G")
    c.ev("Bus.CNF", "Route.CNF_M")
    c.ev("Route.CNF", "CNF")
    c.da("Backend", "Route.Backend")
    c.da("GpioName", "Gpio.PARAMS")
    c.da("ModbusId", "Bus.ID")
    c.da("Route.GQI", "Gpio.QI")
    c.da("Route.MQI", "Bus.QI")
    c.da("Gpio.QO", "Route.QO_G")
    c.da("Bus.QO", "Route.QO_M")
    c.da("Route.QO", "QO")
    if kind == "DO":
        c.da("OUT", "Route.OUT")
        c.da("Route.Value", "Gpio.OUT", "Bus.SD_1")
    else:
        c.da("SimValue", "Route.SimValue")
        if kind == "AI":
            c.da("Scale", "Route.Scale")
        c.da("Gpio.IN", "Route.IN_G")
        c.da("Bus.RD_1", "Route.IN_M")
        c.da("Route.IN", "IN")
    c.write()


# ---------------------------------------------------------------------------------------------
# OPC UA facades: one Server FB per method, a mux serialising calls, PUBLISH for status
# ---------------------------------------------------------------------------------------------
def make_ids(name, comment, ids, folder):
    """ids: {output var: [literal or ('root',) parts]} -> WSTRING IDs computed at INIT."""
    lines = []
    for var, parts in ids.items():
        expr = None
        for p in parts:
            term = "UaRoot" if p is ROOT_TOKEN else wstr(p)
            expr = term if expr is None else f"CONCAT({expr}, {term})"
        lines.append(f"{var} := {expr};")
    Simple(name, comment, {"INIT": (["UaRoot"], "EInit")}, {"INITO": (list(ids), "EInit")},
           {"UaRoot": "WSTRING"}, {v: "WSTRING" for v in ids},
           {"INIT": ("\n".join(lines), "INITO")}, folder=folder).write()


ROOT_TOKEN = object()


def method_id(sub):
    """ID parts of an OPC UA method below UaRoot."""
    return ["opc_ua[CREATE_METHOD;", ROOT_TOKEN, sub + "]"]


def publish_id(subs):
    """ID parts of a local OPC UA write of several variables."""
    parts = ["opc_ua[WRITE;"]
    for i, s in enumerate(subs):
        parts += [ROOT_TOKEN, s + (";" if i < len(subs) - 1 else "]")]
    return parts


def make_mux(name, methods, targets, folder):
    """methods: [(method, target, code, [(arg, type)])]; targets: {target: [arg names on CMD]}.

    FORTE serialises OPC UA method calls, so a single pending slot is sufficient.
    """
    ei, iv, eo, ov = {}, {}, {}, {"Requester": "UDINT", "Accepted": "BOOL", "ErrorID": "UINT"}
    for m, t, code, args in methods:
        ei["IND_" + m] = ["Req_" + m] + [f"{m}_{a}" for a, _ in args]
        iv["Req_" + m] = "UDINT"
        iv.update({f"{m}_{a}": ty for a, ty in args})
        eo["RSP_" + m] = ["Accepted", "ErrorID"]
    for t, targs in targets.items():
        ei[t + "_ACK"] = []
        ei[t + "_REJ"] = [t + "_Err"]
        iv[t + "_Err"] = ("UINT", str(ERRORS["NotPermitted"]))
        eo[t + "_CMD"] = ["Requester", t + "_Code"] + [f"{t}_{a}" for a, _ in targs]
        ov[t + "_Code"] = "USINT"
        ov.update({f"{t}_{a}": ty for a, ty in targs})
    b = Basic(name, "Serialises OPC UA method calls onto command events and routes the accept/reject "
                    "answer back to the calling method's RSP", ei, eo, iv, ov, {"Pending": "USINT"}, folder=folder)
    b.state("START")
    for i, (m, t, code, args) in enumerate(methods, 1):
        copy = "".join(f"\n{t}_{a} := {m}_{a};" for a, _ in args)
        b.state("Call_" + m, f"Requester := Req_{m};\n{t}_Code := {code};{copy}\nPending := {i};", t + "_CMD")
        b.trans("START", "Call_" + m, "IND_" + m)
        b.trans("Call_" + m, "START", "1")
    for t in targets:
        b.state("Ack_" + t, "Accepted := TRUE;\nErrorID := 0;")
        b.state("Rej_" + t, f"Accepted := FALSE;\nErrorID := {t}_Err;")
        b.trans("START", "Ack_" + t, f"{t}_ACK[Pending <> 0]")
        b.trans("START", "Rej_" + t, f"{t}_REJ[Pending <> 0]")
    for i, (m, t, code, args) in enumerate(methods, 1):
        b.state("Rsp_" + m, "Pending := 0;", "RSP_" + m)
        b.trans("Ack_" + t, "Rsp_" + m, f"Pending = {i}")
        b.trans("Rej_" + t, "Rsp_" + m, f"Pending = {i}")
        b.trans("Rsp_" + m, "START", "1")
    for t in targets:
        b.trans("Ack_" + t, "START", "1")
        b.trans("Rej_" + t, "START", "1")
    b.write()


def make_skill_facade():
    """Generate the OPC UA facade of a skill."""
    methods = [(m, "S", c, [(p, "LREAL") for p in PARAMS] if m == "Start" else [])
               for m, c in SKILL_COMMANDS.items()]
    make_mux("UA_SkillMux", methods, {"S": [(p, "LREAL") for p in PARAMS]}, "OPCUA/Base")
    pubs = ["/State", "/ErrorID"] + [f"/{p}" for p in PARAMS]
    make_ids("UA_SkillIds", "OPC UA node IDs of one skill facade, below UaRoot",
             {**{f"Id_{m}": method_id("/" + m) for m in SKILL_COMMANDS}, "IdPub": publish_id(pubs)}, "OPCUA/Base")
    c = Composite("UA_SkillFacade",
                  "OPC UA object of one skill: one method per PackML command (answered synchronously with "
                  "Accepted/ErrorID) and published State, ErrorID and latched parameters",
                  {"INIT": (["UaRoot", "UaEnable"], "EInit"), "PUB": ["State", "ErrorID"] + PARAMS,
                   "M_ACK": [], "M_REJ": ["MErr"]},
                  {"INITO": ([], "EInit"), "MCMD": ["Requester", "MCode"] + ["MP" + p[1] for p in PARAMS]},
                  {"UaRoot": "WSTRING", "UaEnable": "BOOL", "State": "USINT", "ErrorID": "UINT",
                   **{p: "LREAL" for p in PARAMS}, "MErr": "UINT"},
                  {"Requester": "UDINT", "MCode": "USINT", **{"MP" + p[1]: "LREAL" for p in PARAMS}},
                  folder="OPCUA")
    c.fb("Ids", q("UA_SkillIds"))
    c.fb("Calls", q("UA_SkillMux"))
    chain = ["Ids"]
    for m in SKILL_COMMANDS:
        rds = 1 + (len(PARAMS) if m == "Start" else 0)
        c.fb("Srv_" + m, server(2, rds))
        chain.append("Srv_" + m)
        c.da("UaEnable", f"Srv_{m}.QI")
        c.da(f"Ids.Id_{m}", f"Srv_{m}.ID")
        c.ev(f"Srv_{m}.IND", f"Calls.IND_{m}")
        c.ev(f"Calls.RSP_{m}", f"Srv_{m}.RSP")
        c.da(f"Srv_{m}.RD_1", f"Calls.Req_{m}")
        if m == "Start":
            for i, p in enumerate(PARAMS, 2):
                c.da(f"Srv_{m}.RD_{i}", f"Calls.Start_{p}")
        c.da("Calls.Accepted", f"Srv_{m}.SD_1")
        c.da("Calls.ErrorID", f"Srv_{m}.SD_2")
    c.fb("Publisher", publish(len(pubs)))
    chain.append("Publisher")
    c.ev("INIT", "Ids.INIT")
    for a, z in zip(chain, chain[1:]):
        c.ev(a + ".INITO", z + ".INIT")
    c.ev("Publisher.INITO", "INITO")
    c.da("UaRoot", "Ids.UaRoot")
    c.da("UaEnable", "Publisher.QI")
    c.da("Ids.IdPub", "Publisher.ID")
    c.ev("PUB", "Publisher.REQ")
    for i, v in enumerate(["State", "ErrorID"] + PARAMS, 1):
        c.da(v, f"Publisher.SD_{i}")
    c.ev("Calls.S_CMD", "MCMD")
    c.ev("M_ACK", "Calls.S_ACK")
    c.ev("M_REJ", "Calls.S_REJ")
    c.da("MErr", "Calls.S_Err")
    c.da("Calls.Requester", "Requester")
    c.da("Calls.S_Code", "MCode")
    for p in PARAMS:
        c.da(f"Calls.S_{p}", "MP" + p[1])
    c.write()


def make_unit_facade():
    """Generate the OPC UA facade of the unit and occupation."""
    methods = [(m, "U", c, [("Mode", "USINT")] if m == "Reset" else []) for m, c in UNIT_COMMANDS.items()]
    methods += [(m, "O", c, []) for m, c in OCC_COMMANDS.items()]
    make_mux("UA_UnitMux", methods, {"U": [("Mode", "USINT")], "O": []}, "OPCUA/Base")
    pubs = ["/Unit/State", "/Unit/Mode", "/Occupation/State", "/Occupation/Owner"]
    ids = {f"Id_{m}": method_id(("/Unit/" if t == "U" else "/Occupation/") + m) for m, t, _, _ in methods}
    make_ids("UA_UnitIds", "OPC UA node IDs of the unit facade, below UaRoot",
             {**ids, "IdPub": publish_id(pubs)}, "OPCUA/Base")
    c = Composite("UNIT_Facade",
                  "OPC UA object of the unit (composite skill): PackML unit commands, occupation "
                  "commands, published unit/occupation state. Replaces the former FC_ControlPort",
                  {"INIT": (["UaRoot", "UaEnable"], "EInit"), "U_ACK": [], "U_REJ": ["U_Err"],
                   "O_ACK": [], "O_REJ": ["O_Err"], "PUB": ["UnitState", "UnitMode", "OccState", "Owner"]},
                  {"INITO": ([], "EInit"), "U_CMD": ["Requester", "U_Code", "U_Mode"],
                   "O_CMD": ["Requester", "O_Code"]},
                  {"UaRoot": "WSTRING", "UaEnable": "BOOL", "U_Err": ("UINT", str(ERRORS["NotReady"])),
                   "O_Err": ("UINT", str(ERRORS["NotPermitted"])), "UnitState": "USINT", "UnitMode": "USINT",
                   "OccState": "USINT", "Owner": "UDINT"},
                  {"Requester": "UDINT", "U_Code": "USINT", "U_Mode": "USINT", "O_Code": "USINT"},
                  folder="OPCUA")
    c.fb("Ids", q("UA_UnitIds"))
    c.fb("Calls", q("UA_UnitMux"))
    chain = ["Ids"]
    for m, t, code, args in methods:
        c.fb("Srv_" + m, server(2, 1 + len(args)))
        chain.append("Srv_" + m)
        c.da("UaEnable", f"Srv_{m}.QI")
        c.da(f"Ids.Id_{m}", f"Srv_{m}.ID")
        c.ev(f"Srv_{m}.IND", f"Calls.IND_{m}")
        c.ev(f"Calls.RSP_{m}", f"Srv_{m}.RSP")
        c.da(f"Srv_{m}.RD_1", f"Calls.Req_{m}")
        for i, (a, _) in enumerate(args, 2):
            c.da(f"Srv_{m}.RD_{i}", f"Calls.{m}_{a}")
        c.da("Calls.Accepted", f"Srv_{m}.SD_1")
        c.da("Calls.ErrorID", f"Srv_{m}.SD_2")
    c.fb("Publisher", publish(len(pubs)))
    chain.append("Publisher")
    c.ev("INIT", "Ids.INIT")
    for a, z in zip(chain, chain[1:]):
        c.ev(a + ".INITO", z + ".INIT")
    c.ev("Publisher.INITO", "INITO")
    c.da("UaRoot", "Ids.UaRoot")
    c.da("UaEnable", "Publisher.QI")
    c.da("Ids.IdPub", "Publisher.ID")
    c.ev("PUB", "Publisher.REQ")
    for i, v in enumerate(["UnitState", "UnitMode", "OccState", "Owner"], 1):
        c.da(v, f"Publisher.SD_{i}")
    for t in ["U", "O"]:
        c.ev(f"Calls.{t}_CMD", f"{t}_CMD")
        c.ev(f"{t}_ACK", f"Calls.{t}_ACK")
        c.ev(f"{t}_REJ", f"Calls.{t}_REJ")
        c.da(f"{t}_Err", f"Calls.{t}_Err")
        c.da(f"Calls.{t}_Code", f"{t}_Code")
    c.da("Calls.U_Mode", "U_Mode")
    c.da("Calls.Requester", "Requester")
    c.write()


# ---------------------------------------------------------------------------------------------
# Skill composites
# ---------------------------------------------------------------------------------------------
SKILL_UNIT_STAT = ["UnitRunning", "UnitQuiescent", "UnitState", "Mode", "Owner", "RemoteAllowed"]


def skill_interface():
    """Uniform interface shared by all skill composites."""
    ei = {"INIT": (["UaRoot", "UaEnable", "IoBackend", "DoGpio", "DoModbus", "Timeout"], "EInit"),
          "CALL": PARAMS, "UNIT_CTL": ["ControlCode"], "UNIT_STAT": SKILL_UNIT_STAT, "SAMPLE": ["Cell"],
          "STAT_IN": ["BusyIn", "HeldIn", "RunIn"]}
    eo = {"INITO": ([], "EInit"), "DONE": [], "FAILED": ["CallError"],
          "STAT_OUT": ["BusyOut", "HeldOut", "RunOut", "State", "SkillError", "Drive"]}
    iv = {"UaRoot": "WSTRING", "UaEnable": "BOOL", "IoBackend": "USINT", "DoGpio": "STRING",
          "DoModbus": "WSTRING", "Timeout": ("TIME", "T#10s"), **{p: "LREAL" for p in PARAMS},
          "ControlCode": "USINT", "UnitRunning": "BOOL", "UnitQuiescent": "BOOL", "UnitState": "USINT",
          "Mode": "USINT", "Owner": "UDINT", "RemoteAllowed": "BOOL", "Cell": CELL_TYPE,
          "BusyIn": "BOOL", "HeldIn": ("BOOL", "TRUE"), "RunIn": ("BOOL", "TRUE")}
    ov = {"CallError": "UINT", "BusyOut": "BOOL", "HeldOut": "BOOL", "RunOut": "BOOL",
          "State": ("USINT", "4"), "SkillError": "UINT", "Drive": "BOOL"}
    return ei, eo, iv, ov


def make_skill(name, s):
    """Generate the contract block and composite SK_<name> of one skill."""
    make_skill_logic(name, s)
    ei, eo, iv, ov = skill_interface()
    params = "; ".join(f"{p} = {d}" for p, d in s.get("params", {}).items()) or "none"
    c = Composite("SK_" + name,
                  f"Atomic skill {name} (parameters: {params}); owns its actuator output; uniform skill "
                  "interface: CALL/DONE/FAILED, unit control, cell sample, status chain, OPC UA facade",
                  ei, eo, iv, ov, folder="Skills")
    c.fb("Gate", q("SKILL_Gate"))
    c.fb("Pml", q("SKILL_PackML"))
    c.fb("Logic", q("SL_" + name))
    c.fb("Wd", STD["E_DELAY"])
    c.fb("Chain", q("SKILL_Chain"))
    c.fb("Ua", q("UA_SkillFacade"))
    c.fb("Out", q("IO_DO"))
    c.ev("INIT", "Ua.INIT")
    c.ev("Ua.INITO", "Out.INIT")
    c.ev("Out.INITO", "INITO")
    c.da("UaRoot", "Ua.UaRoot")
    c.da("UaEnable", "Ua.UaEnable")
    c.da("IoBackend", "Out.Backend")
    c.da("DoGpio", "Out.GpioName")
    c.da("DoModbus", "Out.ModbusId")
    c.da("Timeout", "Wd.DT")
    # Command sources into the gate.
    c.ev("CALL", "Gate.CALL")
    c.ev("UNIT_CTL", "Gate.UNIT_CTL")
    c.ev("UNIT_STAT", "Gate.UNIT_STAT")
    c.ev("Ua.MCMD", "Gate.MCMD")
    for v in PARAMS + ["ControlCode"] + SKILL_UNIT_STAT:
        c.da(v, "Gate." + v)
    c.da("Ua.Requester", "Gate.Requester")
    c.da("Ua.MCode", "Gate.MCode")
    for p in PARAMS:
        c.da(f"Ua.MP{p[1]}", f"Gate.M{p}")
    # Gate -> state machine; starts pass through the contract's Requires check.
    c.ev("Gate.CMD", "Pml.CMD")
    c.ev("Gate.START", "Logic.CHECK")
    c.ev("Logic.CHECKED", "Pml.CMD")
    c.da("Gate.Command", "Pml.Command")
    for p in PARAMS:
        c.da(f"Gate.PO{p[1]}", f"Logic.{p}")
    c.da("Logic.RequiresOK", "Pml.RequiresOK")
    c.ev("Gate.DONE", "DONE")
    c.ev("Gate.FAILED", "FAILED")
    c.da("Gate.CallError", "CallError")
    c.ev("Gate.M_ACK", "Ua.M_ACK")
    c.ev("Gate.M_REJ", "Ua.M_REJ")
    c.da("Gate.MErr", "Ua.MErr")
    # Contract evaluation on every cell sample.
    c.ev("SAMPLE", "Logic.EVAL")
    c.da("Cell", "Logic.Cell")
    c.ev("Logic.COND", "Pml.COND")
    c.da("Logic.EnsuresOK", "Pml.EnsuresOK")
    c.da("Logic.InvariantOK", "Pml.InvariantOK")
    c.ev("Pml.LATCH", "Logic.LATCH")
    c.ev("Pml.REJECTED", "Gate.REJ")
    # Watchdog.
    c.ev("Pml.WD_START", "Wd.START")
    c.ev("Pml.WD_STOP", "Wd.STOP")
    c.ev("Wd.EO", "Pml.TIMEOUT")
    # State changes: gate handshake, status chain, OPC UA publish, actuator output.
    c.ev("Pml.CNF", "Gate.TRACK", "Chain.REQ", "Ua.PUB", "Out.REQ")
    c.ev("Logic.LATCHED", "Ua.PUB")
    c.da("Pml.State", "Gate.State", "Chain.State", "Ua.State", "State")
    c.da("Pml.ErrorID", "Gate.SkillError", "Ua.ErrorID", "SkillError")
    c.da("Pml.Active", "Out.OUT", "Drive")
    for p in PARAMS:
        c.da(f"Logic.{p}L", f"Ua.{p}")
    c.ev("STAT_IN", "Chain.REQ")
    c.ev("Gate.POKE", "Chain.REQ")
    for v in ["BusyIn", "HeldIn", "RunIn"]:
        c.da(v, "Chain." + v)
    c.ev("Chain.CNF", "STAT_OUT")
    for v in ["BusyOut", "HeldOut", "RunOut"]:
        c.da("Chain." + v, v)
    c.write()


# ---------------------------------------------------------------------------------------------
# Procedure patterns: one instance per BPMN element in PROC; counts, conditions and durations
# are parameters, so product changes that only alter them are WRITE-only.
# ---------------------------------------------------------------------------------------------
def make_patterns():
    """Generate P_Call, P_Loop, P_Choice, P_Fork, P_Join and P_Wait."""
    calls = ["CP" + p[1] for p in PARAMS]
    b = Basic("P_Call", "Calls one atomic skill: latches P1..P4 on EI, continues on DONE (EO) or FAILED (ERR); "
                        "ignores completions it did not request",
              {"EI": PARAMS, "DONE": [], "FAILED": ["CallError"], "RESET": []},
              {"CALL": calls, "EO": [], "ERR": ["Error"]},
              {**{p: "LREAL" for p in PARAMS}, "CallError": "UINT"},
              {**{c: "LREAL" for c in calls}, "Error": "UINT"}, {"Busy": "BOOL"}, folder="Procedure")
    b.state("START")
    b.state("Call", "\n".join(f"{c} := {p};" for c, p in zip(calls, PARAMS)) + "\nBusy := TRUE;\nError := 0;", "CALL")
    b.state("Done", "Busy := FALSE;", "EO")
    b.state("Fail", "Busy := FALSE;\nError := CallError;", "ERR")
    b.state("Reset", "Busy := FALSE;")
    b.trans("START", "Call", "EI")
    b.trans("START", "Done", "DONE[Busy]")
    b.trans("START", "Fail", "FAILED[Busy]")
    b.trans("START", "Reset", "RESET")
    for st in ["Call", "Done", "Fail", "Reset"]:
        b.trans(st, "START", "1")
    b.write()

    b = Basic("P_Loop", "Runs its body Count times (0 skips it): BODY starts an iteration, NEXT reports its end",
              {"EI": ["Count"], "NEXT": [], "RESET": []}, {"BODY": ["Iteration"], "EO": ["Iteration"]},
              {"Count": ("UINT", "1")}, {"Iteration": "UINT"}, folder="Procedure")
    b.state("START")
    b.state("Init", "Iteration := 0;")
    b.state("Check")
    b.state("Body", "Iteration := Iteration + 1;", "BODY")
    b.state("Leave", None, "EO")
    b.state("Reset", "Iteration := 0;")
    b.trans("START", "Init", "EI")
    b.trans("START", "Check", "NEXT")
    b.trans("START", "Reset", "RESET")
    b.trans("Init", "Check", "1")
    b.trans("Check", "Body", "Iteration < Count")
    b.trans("Check", "Leave", "1")
    for st in ["Body", "Leave", "Reset"]:
        b.trans(st, "START", "1")
    b.write()

    b = Basic("P_Choice", "Exclusive gateway: EO_TRUE if the Cond parameter is TRUE, else EO_FALSE",
              {"EI": ["Cond"]}, {"EO_TRUE": [], "EO_FALSE": []}, {"Cond": "BOOL"}, folder="Procedure")
    b.state("START")
    b.state("Yes", None, "EO_TRUE")
    b.state("No", None, "EO_FALSE")
    b.trans("START", "Yes", "EI[Cond]")
    b.trans("START", "No", "EI")
    b.trans("Yes", "START", "1")
    b.trans("No", "START", "1")
    b.write()

    branches = [str(i) for i in range(1, 5)]
    b = Basic("P_Fork", "Parallel gateway split: EI starts up to four branches at once",
              {"EI": []}, {f"EO{i}": [] for i in branches}, folder="Procedure")
    b.state("START")
    b.state("Fork", None, "EO1", [f"EO{i}" for i in branches[1:]])
    b.trans("START", "Fork", "EI")
    b.trans("Fork", "START", "1")
    b.write()

    b = Basic("P_Join", "Parallel gateway join: EO once the first N branch inputs have all arrived",
              {**{f"EI{i}": ["N"] for i in branches}, "RESET": []}, {"EO": []}, {"N": ("USINT", "2")}, {},
              {**{f"A{i}": "BOOL" for i in branches}, "Arrived": "USINT"}, folder="Procedure")
    clear = "\n".join(f"A{i} := FALSE;" for i in branches)
    b.state("START")
    b.state("Check", "Arrived := 0;\n" + "\n".join(f"IF A{i} THEN Arrived := Arrived + 1; END_IF;" for i in branches))
    b.state("Out", clear, "EO")
    b.state("Reset", clear)
    for i in branches:
        b.state(f"Mark{i}", f"A{i} := TRUE;")
        b.trans("START", f"Mark{i}", f"EI{i}")
        b.trans(f"Mark{i}", "Check", "1")
    b.trans("Check", "Out", "Arrived >= N")
    b.trans("Check", "START", "1")
    b.trans("Out", "START", "1")
    b.trans("START", "Reset", "RESET")
    b.trans("Reset", "START", "1")
    b.write()

    c = Composite("P_Wait", "Timer event: EO after DT; RESET cancels", {"EI": ["DT"], "RESET": []}, {"EO": []},
                  {"DT": ("TIME", "T#1s")}, {}, folder="Procedure")
    c.fb("Delay", STD["E_DELAY"])
    c.ev("EI", "Delay.START")
    c.ev("RESET", "Delay.STOP")
    c.ev("Delay.EO", "EO")
    c.da("DT", "Delay.DT")
    c.write()


# ---------------------------------------------------------------------------------------------
# Unit layer
# ---------------------------------------------------------------------------------------------
def make_observer():
    """Generate the state-observer basic FB."""
    b = Basic("FC_Observer", "State observer: one coherent Cell snapshot; invalid or unsafe states inhibit skills",
              {"SAMPLE": list(SENSORS)}, {"CNF": ["Cell", "Safe"] + ["O_" + k for k in CELL], "UNSAFE": ["Safe"]},
              SENSORS, {"Cell": CELL_TYPE, "Safe": "BOOL", **{"O_" + k: t for k, t in CELL.items()}},
              folder="Unit/Base")
    b.state("START")
    code = "\n".join(f"O_{k} := {k};" for k in SENSORS)
    code += "\nO_Valid := (FilledMl >= 0.0) AND NOT (NeedleUp AND NeedleDown);\nO_Safe := O_Valid AND DoorClosed;"
    code += "\n" + "\n".join(f"Cell.{k} := O_{k};" for k in CELL) + "\nSafe := O_Safe;"
    b.state("Observe", code, "CNF")
    b.state("Unsafe", output="UNSAFE")
    b.trans("START", "Observe", "SAMPLE")
    b.trans("Observe", "Unsafe", "NOT O_Safe")
    b.trans("Observe", "START", "1")
    b.trans("Unsafe", "START", "1")
    b.write()


def make_unit_observer():
    """Generate the observer composite with sensor IO and publishing."""
    pubs = [f"/State/{k}" for k in CELL]
    make_ids("UA_ObserverIds", "OPC UA node IDs of the published state variables, below UaRoot",
             {"IdPub": publish_id(pubs)}, "OPCUA/Base")
    iv = {"UaRoot": "WSTRING", "UaEnable": "BOOL", "IoBackend": "USINT", "CycleTime": ("TIME", "T#100ms"),
          "FilledScale": ("LREAL", "0.01")}
    for k in SENSORS:
        iv[k + "_Gpio"] = "STRING"
        iv[k + "_Modbus"] = "WSTRING"
    for k, t in SENSORS.items():
        iv["Sim_" + k] = t
    c = Composite("UNIT_Observer",
                  "Owns all cell sensors (shared by several skills): periodic sampling through IO primitives, "
                  "state observer, published state variables (AID/Operational data)",
                  {"INIT": ([k for k in iv if not k.startswith("Sim_")], "EInit"),
                   "SIM": [k for k in iv if k.startswith("Sim_")]},
                  {"INITO": ([], "EInit"), "SAMPLE": ["Cell", "Safe"], "UNSAFE": ["Safe"]},
                  iv, {"Cell": CELL_TYPE, "Safe": "BOOL"}, folder="Unit")
    c.fb("Ids", q("UA_ObserverIds"))
    chain = ["Ids"]
    for k, t in SENSORS.items():
        kind = "AI" if t == "LREAL" else "DI"
        c.fb("In_" + k, q("IO_" + kind))
        chain.append("In_" + k)
        c.da("IoBackend", f"In_{k}.Backend")
        c.da(k + "_Gpio", f"In_{k}.GpioName")
        c.da(k + "_Modbus", f"In_{k}.ModbusId")
        c.da("Sim_" + k, f"In_{k}.SimValue")
        if kind == "AI":
            c.da("FilledScale", f"In_{k}.Scale")
    c.fb("Publisher", publish(len(pubs)))
    chain.append("Publisher")
    c.fb("Obs", q("FC_Observer"))
    c.fb("Cycle", STD["E_CYCLE"])
    c.ev("INIT", "Ids.INIT")
    for a, z in zip(chain, chain[1:]):
        c.ev(a + ".INITO", z + ".INIT")
    c.ev("Publisher.INITO", "INITO", "Cycle.START")
    c.da("UaRoot", "Ids.UaRoot")
    c.da("UaEnable", "Publisher.QI")
    c.da("Ids.IdPub", "Publisher.ID")
    c.da("CycleTime", "Cycle.DT")
    sensors = list(SENSORS)
    c.ev("Cycle.EO", f"In_{sensors[0]}.REQ")
    for a, z in zip(sensors, sensors[1:]):
        c.ev(f"In_{a}.CNF", f"In_{z}.REQ")
    c.ev(f"In_{sensors[-1]}.CNF", "Obs.SAMPLE")
    for k in SENSORS:
        c.da(f"In_{k}.IN", "Obs." + k)
    c.ev("Obs.CNF", "SAMPLE", "Publisher.REQ")
    c.ev("Obs.UNSAFE", "UNSAFE")
    c.da("Obs.Cell", "Cell")
    c.da("Obs.Safe", "Safe")
    for i, k in enumerate(CELL, 1):
        c.da("Obs.O_" + k, f"Publisher.SD_{i}")
    c.write()


def make_occupation():
    """Generate the occupation state machine."""
    b = Basic("FC_Occupation", "Free / Occupied / Priority / Local; trusted operator boundary; release/override only when quiescent",
              {"CMD": ["Command", "Requester", "Quiescent"]},
              {"CNF": ["State", "Owner", "RemoteAllowed"], "REJECTED": []},
              {"Command": "USINT", "Requester": "UDINT", "Quiescent": "BOOL"},
              {"State": "USINT", "Owner": "UDINT", "RemoteAllowed": "BOOL"}, folder="Unit")
    for n, s in enumerate(["Free", "Occupied", "PriorityMode", "Local"]):
        code = f"State := {n};\nRemoteAllowed := {'TRUE' if s in ['Occupied', 'PriorityMode'] else 'FALSE'};"
        code += "" if s in ["Occupied", "PriorityMode"] else "\nOwner := 0;"
        b.state(s, code, "CNF")
    b.state("Acquire", "Owner := Requester;")
    b.state("CaptureOverride", "Owner := Requester;")
    b.trans("Free", "Acquire", "CMD[(Command = 1) AND (Requester <> 0) AND Quiescent]")
    b.trans("Occupied", "Free", "CMD[(Command = 2) AND (Requester = Owner) AND Quiescent]")
    b.trans("PriorityMode", "Free", "CMD[(Command = 2) AND (Requester = Owner) AND Quiescent]")
    b.trans("Local", "Free", "CMD[(Command = 5) AND Quiescent]")
    for s in ["Free", "Occupied", "PriorityMode", "Local"]:
        b.trans(s, "Local", "CMD[(Command = 3) AND Quiescent]")
        b.trans(s, "CaptureOverride", "CMD[(Command = 4) AND (Requester <> 0) AND Quiescent]")
        b.state("Reject" + s, output="REJECTED")
        b.trans(s, "Reject" + s, "CMD")
        b.trans("Reject" + s, s, "1")
    b.trans("Acquire", "Occupied", "1")
    b.trans("CaptureOverride", "PriorityMode", "1")
    b.write()


def make_unit():
    """Generate the unit PackML state machine with command acknowledges."""
    iv = {"Command": "USINT", "RequestedMode": "USINT", "Requester": "UDINT", "Owner": "UDINT",
          "RemoteAllowed": "BOOL", "Safe": "BOOL", "Busy": "BOOL", "HeldAll": ("BOOL", "TRUE"),
          "RunAll": ("BOOL", "TRUE"), "ProcedureReady": "BOOL"}
    ov = {"State": ("USINT", "2"), "Quiescent": ("BOOL", "TRUE"), "Running": "BOOL", "Mode": "USINT",
          "ControlCode": "USINT", "ProcedureCommand": "USINT"}
    b = Basic("FC_Unit", "Unit PackML state machine; only PROC may declare procedure completion; skills "
                         "acknowledge hold/stop through the equipment-module status chain",
              {"CMD": list(iv), "STATUS": ["Busy", "HeldAll", "RunAll"], "UNSAFE": ["Safe"], "PROC_DONE": [],
               "FAULT": [], "RECOVERABLE": []},
              {"CNF": ["State", "Quiescent", "Running", "Mode"], "CONTROL": ["ControlCode"],
               "PROC_CMD": ["ProcedureCommand"], "CMD_ACK": [], "CMD_REJ": []}, iv, ov, folder="Unit")
    stable = ["Stopped", "Idle", "Execute", "Complete", "Held", "Suspended", "Aborted"]
    control = {"Resetting": 1, "Holding": 3, "Unholding": 4, "Stopping": 5, "Aborting": 6, "Clearing": 7,
               "Suspending": 3, "Unsuspending": 4}
    for s in ["Stopped"] + [s for s in STATES if s != "Stopped"]:
        code = (f"State := {STATES[s]};\nRunning := {'TRUE' if s == 'Execute' else 'FALSE'};\n"
                f"Quiescent := {'NOT Busy' if s in QUIESCENT else 'FALSE'};")
        if s == "Resetting":
            code += "\nMode := RequestedMode;"
        if s in control:
            code += (f"\nControlCode := {control[s]};\nProcedureCommand := "
                     f"{8 if s == 'Suspending' else 9 if s == 'Unsuspending' else control[s]};")
        if s == "Starting":
            code += "\nProcedureCommand := 2;"
        extras = ["CONTROL", "PROC_CMD"] if s in control else ["PROC_CMD"] if s == "Execute" else []
        b.state(s, code, "CNF", extras)
    owned = "RemoteAllowed AND (Requester = Owner) AND (RequestedMode <= 2)"
    cmd = []  # command-triggered transitions get an acknowledge state

    def c(src, dst, cond):
        cmd.append((src, dst, cond))
    for s in ["Stopped", "Idle", "Complete"]:
        c(s, "Resetting", f"CMD[(Command = 1) AND ({owned}) AND NOT Busy]")
    b.trans("Resetting", "Idle", "STATUS[NOT Busy]")
    c("Idle", "Starting", f"CMD[(Command = 2) AND ({owned}) AND Safe AND NOT Busy AND (Mode = 0) AND ProcedureReady]")
    b.trans("Starting", "Execute", "1")
    b.trans("Execute", "Completing", "PROC_DONE")
    b.trans("Completing", "Complete", "1")
    c("Execute", "Holding", f"CMD[(Command = 3) AND ({owned})]")
    b.trans("Execute", "Holding", "RECOVERABLE")
    b.trans("Holding", "Held", "STATUS[HeldAll]")
    c("Held", "Unholding", f"CMD[(Command = 4) AND ({owned}) AND Safe]")
    b.trans("Unholding", "Execute", "STATUS[(Mode = 0) AND RunAll]")
    b.trans("Unholding", "Idle", "STATUS[(Mode <> 0) AND RunAll]")
    for s in ["Idle", "Stopped", "Complete"]:
        c(s, "Holding", f"CMD[(Command = 3) AND ({owned}) AND Busy AND (Mode <> 0)]")
    c("Execute", "Suspending", f"CMD[(Command = 8) AND ({owned})]")
    b.trans("Suspending", "Suspended", "STATUS[HeldAll]")
    c("Suspended", "Unsuspending", f"CMD[(Command = 9) AND ({owned}) AND Safe]")
    b.trans("Unsuspending", "Execute", "STATUS[RunAll]")
    for s in stable + ["Holding", "Unholding", "Suspending", "Unsuspending", "Resetting", "Stopping"]:
        if s != "Aborted":
            c(s, "Aborting", "CMD[Command = 6]")
            b.trans(s, "Aborting", "UNSAFE")
            if s in PROCEDURE_ACTIVE:  # an interrupted call while stopping is not a fault
                b.trans(s, "Aborting", "FAULT")
        if s not in ["Stopped", "Aborted", "Stopping"]:
            c(s, "Stopping", "CMD[Command = 5]")
    c("Stopped", "Stopping", "CMD[(Command = 5) AND Busy]")
    b.trans("Stopping", "Stopped", "STATUS[NOT Busy]")
    b.trans("Aborting", "Aborted", "STATUS[NOT Busy]")
    c("Aborted", "Clearing", f"CMD[(Command = 7) AND ({owned}) AND Safe]")
    b.trans("Clearing", "Stopped", "STATUS[NOT Busy]")
    for s in QUIESCENT:
        b.state("Update" + s, "Quiescent := NOT Busy;", "CNF")
        b.trans(s, "Update" + s, "STATUS")
        b.trans("Update" + s, s, "1")
    for i, (src, dst, cond) in enumerate(cmd):
        ack = f"Ack{i}_{dst}"
        b.state(ack, output="CMD_ACK")
        b.trans(src, ack, cond)
        b.trans(ack, dst, "1")
    # Unmatched commands are rejected so the OPC UA method gets an answer.
    for s in STATES:
        b.state("Rej" + s, output="CMD_REJ")
        b.trans(s, "Rej" + s, "CMD")
        b.trans("Rej" + s, s, "1")
    b.write()


def make_facade():
    """Generate the procedure facade."""
    b = Basic("FC_ProcedureFacade", "Fixed procedure boundary; unavailable until composition is installed; never invents completion",
              {"CONFIG": ["Installed", "Quiescent"], "CMD": ["Command"], "FINISHED": [], "FAILED": []},
              {"CNF": ["Ready"], "START": [], "RESET": [], "EXEC": ["CommandOut"], "DONE": [], "FAULT": []},
              {"Installed": "BOOL", "Quiescent": "BOOL", "Command": "USINT"}, {"Ready": "BOOL", "CommandOut": "USINT"},
              folder="Unit")
    b.state("START")
    b.state("Configure", "Ready := Installed;", "CNF")
    b.state("Forward", "CommandOut := Command;")
    b.state("Start", output="START")
    b.state("Reset", output="RESET")
    b.state("Exec", output="EXEC")
    b.trans("Forward", "Start", "Command = 2")
    b.trans("Forward", "Reset", "Command = 1")
    b.trans("Forward", "Exec", "1")
    for st in ["Start", "Reset", "Exec"]:
        b.trans(st, "START", "1")
    b.state("Done", output="DONE")
    b.state("Fault", output="FAULT")
    for s, ev in [("Configure", "CONFIG"), ("Forward", "CMD"), ("Done", "FINISHED"), ("Fault", "FAILED")]:
        b.trans("START", s, ev + "[Quiescent]" if ev == "CONFIG" else ev)
        if s != "Forward":
            b.trans(s, "START", "1")
    b.write()


# ---------------------------------------------------------------------------------------------
# System: fixed unit part, EM_Filler (skills, changeable online), PROC (procedure, changeable online)
# ---------------------------------------------------------------------------------------------
def subapp(net, name, x, y, comment, ei, eo, iv, ov):
    """Add an untyped subapplication; return it and its inner network."""
    sa = elem(net, "SubApp", Name=name, x=x, y=y, Comment=comment)
    interface(sa, ei, eo, iv, ov)
    return sa, elem(sa, "SubAppNetwork")


def connections(net, events, data):
    """Add event and data connection lists to a network."""
    ec, dc = elem(net, "EventConnections"), elem(net, "DataConnections")
    for s, d in events:
        elem(ec, "Connection", Source=s, Destination=d)
    for s, d in data:
        elem(dc, "Connection", Source=s, Destination=d)


def fb(net, name, typ, x, y, **params):
    """Add an FB instance with parameters to a network."""
    f = elem(net, "FB", Name=name, Type=typ, x=x, y=y)
    for p, v in params.items():
        elem(f, "Parameter", Name=p, Value=v)


DEMO_UA_ROOT = "/Objects/Demo"
DEVICE = ("FORTE_PC", "localhost:61499")


def make_demo_types():
    """Generate DEMO_Plant (plant simulation) and DEMO_Operator (automatic operator)."""
    drives = {"Drive" + k: "BOOL" for k in SKILLS}
    outs = {k: t for k, t in SENSORS.items()}
    b = Basic("DEMO_Plant", "Filling-cell plant model for demos: needle travel, dosing, stoppering and inspection "
                            "driven by the skills' Drive outputs; counts MoveDown/MoveUp shoot-through",
              {"INIT": ["StartDown"], "TICK": list(drives) + ["TravelTicks", "FillPerTick", "ActTicks"], "NEW_VIAL": []},
              {"CNF": list(outs) + ["ShootThrough"]},
              {**drives, "TravelTicks": ("UINT", "10"), "FillPerTick": ("LREAL", "0.02"), "ActTicks": ("UINT", "10"),
               "StartDown": "BOOL"},
              {**outs, "ShootThrough": "UINT"},
              {"Position": "UINT", "StopTicks": "UINT", "InspTicks": "UINT"}, folder="Demo")
    update = "\nNeedleUp := Position = 0;\nNeedleDown := Position >= TravelTicks;"
    b.state("START")
    b.state("Init", "Position := 0;\nIF StartDown THEN Position := TravelTicks; END_IF;\nVialPresent := TRUE;\n"
                    "DoorClosed := TRUE;\nFilledMl := 0.0;\nStoppered := FALSE;\nChecked := FALSE;" + update, "CNF")
    b.state("Advance", "IF DriveMoveDown AND DriveMoveUp THEN ShootThrough := ShootThrough + 1;\n"
                    "ELSIF DriveMoveDown AND (Position < TravelTicks) THEN Position := Position + 1;\n"
                    "ELSIF DriveMoveUp AND (Position > 0) THEN Position := Position - 1;\nEND_IF;" + update + "\n"
                    "IF DriveDose AND NeedleDown THEN FilledMl := FilledMl + FillPerTick; END_IF;\n"
                    "IF DriveStopper THEN StopTicks := StopTicks + 1; ELSE StopTicks := 0; END_IF;\n"
                    "IF StopTicks >= ActTicks THEN Stoppered := TRUE; END_IF;\n"
                    "IF DriveInspect THEN InspTicks := InspTicks + 1; ELSE InspTicks := 0; END_IF;\n"
                    "IF InspTicks >= ActTicks THEN Checked := TRUE; END_IF;", "CNF")
    b.state("Vial", "VialPresent := TRUE;\nFilledMl := 0.0;\nStoppered := FALSE;\nChecked := FALSE;", "CNF")
    for st, ev in [("Init", "INIT"), ("Advance", "TICK"), ("Vial", "NEW_VIAL")]:
        b.trans("START", st, ev)
        b.trans(st, "START", "1")
    b.write()

    b = Basic("DEMO_Operator", "Automatic operator for demos: occupy, reset in Production, start, wait for Complete, "
                               "new vial, pause, repeat while Enable; clears the unit after an abort",
              {"START": ["Enable", "Pause"], "UNIT": ["UnitState"], "REJ": [], "TIMER": ["Enable"]},
              {"O_CMD": ["Requester", "O_Code"], "U_CMD": ["Requester", "U_Code", "U_Mode"], "NEW_VIAL": [],
               "WAIT": ["Delay"], "CNF": ["Phase", "Cycles"]},
              {"UnitState": "USINT", "Enable": ("BOOL", "TRUE"), "Pause": ("TIME", "T#2s")},
              {"Requester": ("UDINT", "1"), "O_Code": "USINT", "U_Code": "USINT", "U_Mode": "USINT",
               "Delay": "TIME", "Phase": "USINT", "Cycles": "UINT"}, folder="Demo")
    b.state("Off", "Phase := 0;", "CNF")
    b.state("Begin", "Phase := 1;\nDelay := T#1s;", "WAIT", ["CNF"])
    b.state("Settle")
    b.state("Occupy", "O_Code := 1;", "O_CMD")
    b.state("Reset", "U_Code := 1;\nU_Mode := 0;\nPhase := 2;", "U_CMD", ["CNF"])
    b.state("WaitIdle")
    b.state("Start", "U_Code := 2;\nPhase := 3;", "U_CMD", ["CNF"])
    b.state("WaitDone")
    b.state("Done", "Cycles := Cycles + 1;\nDelay := Pause;\nPhase := 4;", "NEW_VIAL", ["WAIT", "CNF"])
    b.state("Rest")
    b.state("Clear", "U_Code := 7;\nPhase := 5;", "U_CMD", ["CNF"])
    b.state("WaitStopped")
    b.state("Retry", "Delay := T#1s;", "WAIT")
    b.trans("Off", "Begin", "START")
    b.trans("Begin", "Settle", "1")
    b.trans("Settle", "Occupy", "TIMER")
    b.trans("Occupy", "Reset", "1")
    b.trans("Reset", "WaitIdle", "1")
    b.trans("WaitIdle", "Start", "UNIT[UnitState = 4]")
    b.trans("WaitIdle", "Clear", "UNIT[UnitState = 9]")
    b.trans("WaitIdle", "Retry", "REJ")
    b.trans("Start", "WaitDone", "1")
    b.trans("WaitDone", "Done", "UNIT[UnitState = 17]")
    b.trans("WaitDone", "Clear", "UNIT[UnitState = 9]")
    b.trans("WaitDone", "Retry", "REJ")
    b.trans("Done", "Rest", "1")
    b.trans("Rest", "Reset", "TIMER[Enable]")
    b.trans("Rest", "Off", "TIMER")
    b.trans("Clear", "WaitStopped", "1")
    b.trans("WaitStopped", "Reset", "UNIT[UnitState = 2]")
    b.trans("WaitStopped", "Retry", "REJ")
    b.trans("Retry", "Settle", "1")
    b.write()


def cell_application(root, name, comment, ua_root, demo):
    """FillingCell-style application: fixed unit, EM_Filler, PROC; ``demo`` adds plant, operator and a procedure."""
    app = elem(root, "Application", Name=name, Comment=comment)
    net = elem(app, "SubAppNetwork")
    fb(net, "Boot", STD["E_RESTART"], 100, 100)
    # FORTE 3.3 serves OPC UA for one resource per process only, so demo resources run without it.
    ua_enable = "FALSE" if demo else "TRUE"
    obs_params = {"UaRoot": wstr(ua_root), "UaEnable": ua_enable, "IoBackend": "0"}
    if demo:
        obs_params["CycleTime"] = "T#50ms"
    else:
        for k, (line, addr) in SENSOR_IO.items():
            obs_params[k + "_Gpio"] = f"'FC_{k}'" if line is not None else "''"
            obs_params[k + "_Modbus"] = wstr(modbus_read(addr))
        # Safe simulated start state (IoBackend 0): needle up, vial present, door closed.
        obs_params.update(Sim_NeedleUp="TRUE", Sim_VialPresent="TRUE", Sim_DoorClosed="TRUE")
    fb(net, "Observer", q("UNIT_Observer"), 100, 1400, **obs_params)
    if not demo:
        fb(net, "UaFacade", q("UNIT_Facade"), 100, 500, UaRoot=wstr(ua_root), UaEnable="TRUE")
    fb(net, "Occupation", q("FC_Occupation"), 1500, 100)
    fb(net, "Unit", q("FC_Unit"), 1500, 700)
    fb(net, "Facade", q("FC_ProcedureFacade"), 2600, 100, **({"Installed": "TRUE"} if demo else {}))

    call_ei = {f"CALL_{s}": [f"{p}_{s}" for p in PARAMS] for s in SKILLS}
    call_eo = {f"DONE_{s}": [] for s in SKILLS}
    call_eo.update({f"FAILED_{s}": [f"CallError_{s}"] for s in SKILLS})
    call_iv = {f"{p}_{s}": "LREAL" for s in SKILLS for p in PARAMS}
    call_ov = {f"CallError_{s}": "UINT" for s in SKILLS}
    em, emnet = subapp(net, "EM_Filler", 3600, 700,
                       "Equipment module: one composite per skill, chained for status; instances and chain "
                       "may be changed online while the unit is quiescent",
                       {"INIT": [], "UNIT_CTL": ["ControlCode"], "UNIT_STAT": SKILL_UNIT_STAT, "SAMPLE": ["Cell"],
                        **call_ei},
                       {"INITO": [], "STAT_OUT": ["Busy", "HeldAll", "RunAll"], **call_eo},
                       {"ControlCode": "USINT", "UnitRunning": "BOOL", "UnitQuiescent": "BOOL", "UnitState": "USINT",
                        "Mode": "USINT", "Owner": "UDINT", "RemoteAllowed": "BOOL", "Cell": CELL_TYPE, **call_iv},
                       {"Busy": "BOOL", "HeldAll": "BOOL", "RunAll": "BOOL", **call_ov,
                        **{f"Drive_{s}": "BOOL" for s in SKILLS}})
    names = list(SKILLS)
    for i, s in enumerate(names):
        line, addr = ACTUATOR_IO[s]
        io = {} if demo else {"DoGpio": f"'FC_{s}'", "DoModbus": wstr(modbus_write(addr))}
        fb(emnet, s, q("SK_" + s), 300 + i * 1500, 300, UaRoot=wstr(f"{ua_root}/Skills/{s}"), UaEnable=ua_enable,
           IoBackend="0", **io)
    ev, da = [("INIT", names[0] + ".INIT")], []
    for a, z in zip(names, names[1:]):
        ev += [(a + ".INITO", z + ".INIT"), (a + ".STAT_OUT", z + ".STAT_IN")]
        da += [(f"{a}.{o}", f"{z}.{i}") for o, i in [("BusyOut", "BusyIn"), ("HeldOut", "HeldIn"), ("RunOut", "RunIn")]]
    ev += [(names[-1] + ".INITO", "INITO"), (names[-1] + ".STAT_OUT", "STAT_OUT")]
    da += [(f"{names[-1]}.{o}", i) for o, i in [("BusyOut", "Busy"), ("HeldOut", "HeldAll"), ("RunOut", "RunAll")]]
    for s in names:
        ev += [("UNIT_CTL", s + ".UNIT_CTL"), ("UNIT_STAT", s + ".UNIT_STAT"), ("SAMPLE", s + ".SAMPLE"),
               (f"CALL_{s}", s + ".CALL"), (s + ".DONE", f"DONE_{s}"), (s + ".FAILED", f"FAILED_{s}")]
        da += [("ControlCode", s + ".ControlCode"), ("Cell", s + ".Cell"), (s + ".CallError", f"CallError_{s}"),
               (s + ".Drive", f"Drive_{s}")]
        da += [(v, f"{s}.{v}") for v in SKILL_UNIT_STAT]
        da += [(f"{p}_{s}", f"{s}.{p}") for p in PARAMS]
    connections(emnet, ev, da)

    proc, procnet = subapp(net, "PROC", 2600, 1400,
                           "Demo procedure: MoveDown, Dose x2 (P_Loop), MoveUp, Stopper, Inspect" if demo else
                           "INTENTIONALLY EMPTY: generated procedure (P_* pattern instances) calls skills via "
                           "CALL_*/DONE_*/FAILED_*",
                           {"START": [], "RESET": [], "CMD": ["Command"], **{f"DONE_{s}": [] for s in SKILLS},
                            **{f"FAILED_{s}": [f"CallError_{s}"] for s in SKILLS}},
                           {"FINISHED": [], "FAILED": [], **call_ei},
                           {"Command": "USINT", **call_ov}, {**call_iv})
    if demo:
        demo_procedure(procnet)

    events = [("Boot.COLD", "Observer.INIT"), ("Boot.WARM", "Observer.INIT"),
              ("Unit.CNF", "EM_Filler.UNIT_STAT"), ("Occupation.CNF", "EM_Filler.UNIT_STAT"),
              ("Unit.CONTROL", "EM_Filler.UNIT_CTL"), ("EM_Filler.STAT_OUT", "Unit.STATUS"),
              ("Observer.SAMPLE", "EM_Filler.SAMPLE"), ("Observer.UNSAFE", "Unit.UNSAFE"),
              ("Unit.PROC_CMD", "Facade.CMD"), ("Facade.EXEC", "PROC.CMD"),
              ("Facade.START", "PROC.START"), ("Facade.RESET", "PROC.RESET"), ("PROC.FINISHED", "Facade.FINISHED"),
              ("PROC.FAILED", "Facade.FAILED"), ("Facade.DONE", "Unit.PROC_DONE"), ("Facade.FAULT", "Unit.FAULT")]
    data = [("Occupation.Owner", "Unit.Owner"), ("Occupation.RemoteAllowed", "Unit.RemoteAllowed"),
            ("Occupation.Owner", "EM_Filler.Owner"), ("Occupation.RemoteAllowed", "EM_Filler.RemoteAllowed"),
            ("Unit.Running", "EM_Filler.UnitRunning"), ("Unit.Quiescent", "EM_Filler.UnitQuiescent"),
            ("Unit.State", "EM_Filler.UnitState"), ("Unit.Mode", "EM_Filler.Mode"),
            ("Unit.ControlCode", "EM_Filler.ControlCode"),
            ("Unit.Quiescent", "Occupation.Quiescent"), ("Unit.Quiescent", "Facade.Quiescent"),
            ("EM_Filler.Busy", "Unit.Busy"), ("EM_Filler.HeldAll", "Unit.HeldAll"), ("EM_Filler.RunAll", "Unit.RunAll"),
            ("Observer.Cell", "EM_Filler.Cell"), ("Observer.Safe", "Unit.Safe"),
            ("Unit.ProcedureCommand", "Facade.Command"), ("Facade.CommandOut", "PROC.Command"),
            ("Facade.Ready", "Unit.ProcedureReady")]
    for s in SKILLS:
        events += [(f"PROC.CALL_{s}", f"EM_Filler.CALL_{s}"), (f"EM_Filler.DONE_{s}", f"PROC.DONE_{s}"),
                   (f"EM_Filler.FAILED_{s}", f"PROC.FAILED_{s}")]
        data += [(f"PROC.{p}_{s}", f"EM_Filler.{p}_{s}") for p in PARAMS]
        data += [(f"EM_Filler.CallError_{s}", f"PROC.CallError_{s}")]
    if demo:
        fb(net, "Plant", q("DEMO_Plant"), 100, 2600)
        fb(net, "PlantClock", STD["E_CYCLE"], 100, 3400, DT="T#20ms")
        fb(net, "Operator", q("DEMO_Operator"), 4800, 100)
        fb(net, "OpDelay", STD["E_DELAY"], 4800, 900)
        events += [("Boot.COLD", "Plant.INIT"), ("Boot.WARM", "Plant.INIT"), ("Boot.COLD", "PlantClock.START"),
                   ("Boot.WARM", "PlantClock.START"), ("PlantClock.EO", "Plant.TICK"), ("Plant.CNF", "Observer.SIM"),
                   ("Observer.INITO", "EM_Filler.INIT"), ("EM_Filler.INITO", "Facade.CONFIG"),
                   ("Facade.CNF", "Operator.START"), ("Operator.O_CMD", "Occupation.CMD"),
                   ("Operator.U_CMD", "Unit.CMD"), ("Operator.NEW_VIAL", "Plant.NEW_VIAL"),
                   ("Operator.WAIT", "OpDelay.START"), ("OpDelay.EO", "Operator.TIMER"),
                   ("Unit.CNF", "Operator.UNIT"), ("Unit.CMD_REJ", "Operator.REJ")]
        data += [("Operator.Requester", "Unit.Requester"), ("Operator.Requester", "Occupation.Requester"),
                 ("Operator.U_Code", "Unit.Command"), ("Operator.U_Mode", "Unit.RequestedMode"),
                 ("Operator.O_Code", "Occupation.Command"), ("Unit.State", "Operator.UnitState"),
                 ("Operator.Delay", "OpDelay.DT")]
        data += [(f"Plant.{k}", f"Observer.Sim_{k}") for k in SENSORS]
        data += [(f"EM_Filler.Drive_{s}", f"Plant.Drive{s}") for s in SKILLS]
    else:
        events += [("Observer.INITO", "UaFacade.INIT"), ("UaFacade.INITO", "EM_Filler.INIT"),
                   ("UaFacade.U_CMD", "Unit.CMD"), ("UaFacade.O_CMD", "Occupation.CMD"),
                   ("Unit.CMD_ACK", "UaFacade.U_ACK"), ("Unit.CMD_REJ", "UaFacade.U_REJ"),
                   ("Occupation.CNF", "UaFacade.O_ACK"), ("Occupation.REJECTED", "UaFacade.O_REJ"),
                   ("Unit.CNF", "UaFacade.PUB"), ("Occupation.CNF", "UaFacade.PUB")]
        data += [("UaFacade.Requester", "Unit.Requester"), ("UaFacade.Requester", "Occupation.Requester"),
                 ("UaFacade.U_Code", "Unit.Command"), ("UaFacade.U_Mode", "Unit.RequestedMode"),
                 ("UaFacade.O_Code", "Occupation.Command"),
                 ("Unit.State", "UaFacade.UnitState"), ("Unit.Mode", "UaFacade.UnitMode"),
                 ("Occupation.State", "UaFacade.OccState"), ("Occupation.Owner", "UaFacade.Owner")]
    connections(net, events, data)
    return app


def demo_procedure(net):
    """Hand-built PROC network: MoveDown, Dose inside a two-cycle P_Loop, MoveUp, Stopper, Inspect."""
    order = ["MoveDown", "Dose", "MoveUp", "Stopper", "Inspect"]
    for i, s in enumerate(order):
        fb(net, s, q("P_Call"), 400 + i * 1600, 300, **({"P1": "0.3"} if s == "Dose" else {}))
    fb(net, "DoseLoop", q("P_Loop"), 2000, 1400, Count="2")
    ev = [("START", "MoveDown.EI"), ("MoveDown.EO", "DoseLoop.EI"), ("DoseLoop.BODY", "Dose.EI"),
          ("Dose.EO", "DoseLoop.NEXT"), ("DoseLoop.EO", "MoveUp.EI"), ("MoveUp.EO", "Stopper.EI"),
          ("Stopper.EO", "Inspect.EI"), ("Inspect.EO", "FINISHED"), ("RESET", "DoseLoop.RESET")]
    da = [("Dose.CP1", "P1_Dose")]
    for s in order:
        ev += [(f"{s}.CALL", f"CALL_{s}"), (f"DONE_{s}", f"{s}.DONE"), (f"FAILED_{s}", f"{s}.FAILED"),
               (f"{s}.ERR", "FAILED"), ("RESET", f"{s}.RESET")]
        da += [(f"CallError_{s}", f"{s}.CallError")]
    connections(net, ev, da)


def bench_application(root):
    """SkillBench: one SK_Dose called every 2 s against the plant model; DONE/FAILED counted."""
    app = elem(root, "Application", Name="SkillBench",
               Comment="Demo: SK_Dose is called periodically with P1 = 0.3 mL; watch Dose.State, Plant.FilledMl, "
                       "Done.CV and Failed.CV in the IDE monitoring")
    net = elem(app, "SubAppNetwork")
    fb(net, "Boot", STD["E_RESTART"], 100, 100)
    fb(net, "Plant", q("DEMO_Plant"), 100, 900, StartDown="TRUE")
    fb(net, "PlantClock", STD["E_CYCLE"], 100, 1700, DT="T#20ms")
    fb(net, "Observer", q("UNIT_Observer"), 1400, 900, UaRoot=wstr(f"{DEMO_UA_ROOT}/Bench"), UaEnable="FALSE",
       IoBackend="0", CycleTime="T#50ms")
    fb(net, "Dose", q("SK_Dose"), 2800, 500, UaRoot=wstr(f"{DEMO_UA_ROOT}/Bench/Dose"), UaEnable="FALSE",
       IoBackend="0", Timeout="T#5s", UnitRunning="TRUE", P1="0.3")
    fb(net, "Caller", STD["E_CYCLE"], 1400, 100, DT="T#2s")
    fb(net, "Done", STD["E_CTU"], 4200, 300)
    fb(net, "Failed", STD["E_CTU"], 4200, 900)
    events = [("Boot.COLD", "Plant.INIT"), ("Boot.WARM", "Plant.INIT"), ("Boot.COLD", "PlantClock.START"),
              ("Boot.WARM", "PlantClock.START"), ("Boot.COLD", "Observer.INIT"), ("Boot.WARM", "Observer.INIT"),
              ("PlantClock.EO", "Plant.TICK"), ("Plant.CNF", "Observer.SIM"), ("Observer.INITO", "Dose.INIT"),
              ("Dose.INITO", "Dose.UNIT_STAT"), ("Dose.INITO", "Caller.START"), ("Observer.SAMPLE", "Dose.SAMPLE"),
              ("Caller.EO", "Dose.CALL"), ("Dose.DONE", "Done.CU"), ("Dose.DONE", "Plant.NEW_VIAL"),
              ("Dose.FAILED", "Failed.CU")]
    data = [(f"Plant.{k}", f"Observer.Sim_{k}") for k in SENSORS]
    data += [("Observer.Cell", "Dose.Cell"), ("Dose.Drive", "Plant.DriveDose")]
    connections(net, events, data)
    return app


def pattern_application(root):
    """PatternDemo: fork/join, wait, loop and choice driven by a 3 s clock, with counters."""
    app = elem(root, "Application", Name="PatternDemo",
               Comment="Demo of the procedure patterns: every 3 s a fork waits 0.3 s and 0.8 s, the join starts a "
                       "3-iteration loop, then a choice alternates; watch the Ctu* counters")
    net = elem(app, "SubAppNetwork")
    fb(net, "Boot", STD["E_RESTART"], 100, 100)
    fb(net, "Clock", STD["E_CYCLE"], 100, 700, DT="T#3s")
    fb(net, "Fork", q("P_Fork"), 1200, 700)
    fb(net, "WaitA", q("P_Wait"), 2300, 300, DT="T#300ms")
    fb(net, "WaitB", q("P_Wait"), 2300, 1100, DT="T#800ms")
    fb(net, "Join", q("P_Join"), 3400, 700, N="2")
    fb(net, "Loop", q("P_Loop"), 4500, 700, Count="3")
    fb(net, "WaitC", q("P_Wait"), 4500, 1600, DT="T#200ms")
    fb(net, "Toggle", STD["E_T_FF"], 5600, 700)
    fb(net, "Choice", q("P_Choice"), 6700, 700)
    for i, c in enumerate(["CtuJoin", "CtuBody", "CtuTrue", "CtuFalse"]):
        fb(net, c, STD["E_CTU"], 7800, 300 + i * 700)
    events = [("Boot.COLD", "Clock.START"), ("Boot.WARM", "Clock.START"), ("Clock.EO", "Fork.EI"),
              ("Fork.EO1", "WaitA.EI"), ("Fork.EO2", "WaitB.EI"), ("WaitA.EO", "Join.EI1"), ("WaitB.EO", "Join.EI2"),
              ("Join.EO", "CtuJoin.CU"), ("Join.EO", "Loop.EI"), ("Loop.BODY", "WaitC.EI"), ("Loop.BODY", "CtuBody.CU"),
              ("WaitC.EO", "Loop.NEXT"), ("Loop.EO", "Toggle.CLK"), ("Toggle.EO", "Choice.EI"),
              ("Choice.EO_TRUE", "CtuTrue.CU"), ("Choice.EO_FALSE", "CtuFalse.CU")]
    connections(net, events, [("Toggle.Q", "Choice.Cond")])
    return app


def pi_application(root):
    """PiIoConfig: GPIOChip line configuration for a Raspberry Pi (not mapped)."""
    pi = elem(root, "Application", Name="PiIoConfig",
              Comment="GPIOChip line configuration for a Raspberry Pi; handle names match IX/QX PARAMS in FillingCell. "
                      "Map it together with FillingCell (IoBackend = 1) onto a Pi device")
    pnet = elem(pi, "SubAppNetwork")
    fb(pnet, "Boot", STD["E_RESTART"], 100, 100)
    lines = [(f"FC_{k}", line, 0) for k, (line, _) in SENSOR_IO.items() if line is not None]
    lines += [(f"FC_{s}", line, 1) for s, (line, _) in ACTUATOR_IO.items()]
    for i, (name, line, mode) in enumerate(lines):
        fb(pnet, name, STD["GPIOChip"], 600 + (i % 4) * 900, 100 + (i // 4) * 700, QI="TRUE", VALUE=wstr(name),
           ChipNumber="0", LineNumber=str(line), ReadWriteMode=str(mode))
    pev = [("Boot.COLD", lines[0][0] + ".INIT"), ("Boot.WARM", lines[0][0] + ".INIT")]
    pev += [(a[0] + ".INITO", z[0] + ".INIT") for a, z in zip(lines, lines[1:])]
    connections(pnet, pev, [])


def map_to_resource(device, resource, app, mappings):
    """Map every top-level element of ``app`` to a new resource of ``device`` (copies it, adds Mapping)."""
    res = elem(device, "Resource", Name=resource, Type=STD["EMB_RES"], x=0, y=0)
    network = elem(res, "FBNetwork")
    app_name = app.get("Name")
    for child in app.find("SubAppNetwork"):
        network.append(copy.deepcopy(child))
        if child.tag in ("FB", "SubApp"):
            mappings.append((f"{app_name}.{child.get('Name')}",
                             f"{device.get('Name')}.{resource}.{child.get('Name')}"))


def make_system():
    """Generate the applications and map the runnable ones to resources of one FORTE device."""
    root = ET.Element("System", Name="FillingCellFixed",
                      Comment="FillingCell (production, OPC UA driven), FillingCellDemo (self-running), SkillBench "
                              "and PatternDemo run on one FORTE_PC device; PiIoConfig is for a Raspberry Pi")
    elem(root, "Identification", Standard="61499-2")
    apps = [
        (cell_application(root, "FillingCell",
                          "Production cell driven over OPC UA (/Objects/FillingCell/Filler). IoBackend 0 = simulated "
                          "(force Observer.Sim_*), 1 = GPIO (add PiIoConfig), 2 = Modbus (4diac/tools/cell_sim.py)",
                          UA_ROOT, demo=False), "RES"),
        (cell_application(root, "FillingCellDemo",
                          "Self-running demo: plant model and automatic operator cycle the whole cell through the "
                          "PROC procedure; watch Operator.Cycles, Unit.State, Plant.* in the IDE monitoring (no OPC UA: "
                          "FORTE 3.3 serves OPC UA for one resource only, used by FillingCell)",
                          f"{DEMO_UA_ROOT}/Filler", demo=True), "DEMO"),
        (bench_application(root), "BENCH"),
        (pattern_application(root), "PATTERNS"),
    ]
    pi_application(root)
    name, manager = DEVICE
    device = elem(root, "Device", Name=name, Type=STD["FORTE_PC"], x=1000, y=1000)
    elem(device, "Parameter", Name="MGR_ID", Value=wstr(manager))
    elem(device, "Attribute", Name="Profile", Type="STRING", Value="HOLOBLOC", Comment="device profile")
    mappings = []
    for app, resource in apps:
        map_to_resource(device, resource, app, mappings)
    for src, dst in mappings:
        elem(root, "Mapping", From=src, To=dst)
    save(root, ROOT / "FillingCellFixed.sys")


# ---------------------------------------------------------------------------------------------
# Project files
# ---------------------------------------------------------------------------------------------
def project():
    """Write .project, .buildpath, settings and MANIFEST.MF."""
    root = ET.Element("projectDescription")
    elem(root, "name").text = "FillingCellFixed"
    elem(root, "comment").text = "Filling-cell skill library and fixed unit; PROC intentionally empty"
    elem(root, "projects")
    build = elem(root, "buildSpec")
    for builder in ["org.eclipse.fordiac.ide.library.builder", "org.eclipse.xtext.ui.shared.xtextBuilder",
                    "org.eclipse.fordiac.ide.export.builder"]:
        command = elem(build, "buildCommand")
        elem(command, "name").text = builder
        elem(command, "arguments")
    natures = elem(root, "natures")
    for nature in ["org.eclipse.fordiac.ide.systemmanagement.FordiacNature", "org.eclipse.xtext.ui.shared.xtextNature"]:
        elem(natures, "nature").text = nature
    save(root, ROOT / ".project")
    buildpath = ET.Element("buildpath:buildpath", {"xmlns:buildpath": "http://www.eclipse.org/4diac/xml/buildpath.xsd"})
    elem(buildpath, "sourceFolder", name="Type Library")
    save(buildpath, ROOT / ".buildpath")
    # The IDE's library manager walks these folders on every build; they stay empty because the
    # standard types this project uses are vendored under Type Library/Std.
    for folder in ["Standard Libraries", "External Libraries"]:
        (ROOT / folder).mkdir(exist_ok=True)
        (ROOT / folder / ".gitkeep").write_text("", encoding="utf-8")
    settings = ROOT / ".settings"
    settings.mkdir(exist_ok=True)
    (settings / "org.eclipse.core.resources.prefs").write_text("eclipse.preferences.version=1\nencoding/<project>=UTF-8\n", encoding="utf-8")
    manifest = ET.Element("Manifest", {"xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                                       "xsi:noNamespaceSchemaLocation": "platform:/resource/org.eclipse.fordiac.ide.library.model/model/library.xsd",
                                       "Scope": "Project"})
    elem(manifest, "Dependencies")
    product = elem(manifest, "Product", Name="FillingCellFixed", SymbolicName="fillingcell", Comment="Filling-cell skill library")
    elem(product, "VersionInfo", Version="2.0.0", Author="Project contributors", Date="2026-09-27")
    save(manifest, ROOT / "MANIFEST.MF")


def copy_std_types():
    """Copy the vendored standard type declarations into the project."""
    for src in sorted(STDTYPES.glob("*/*.*")):
        rel = Path("Std") / src.parent.name / src.name
        (TYPES / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, TYPES / rel)
        pkg = ET.parse(src).getroot().find("CompilerInfo")
        name = (pkg.get("packageName") + "::" if pkg is not None else "") + src.stem
        MANIFEST.append((name, "Standard", rel.as_posix(), False))


def main():
    """Regenerate the whole project."""
    if TYPES.exists():
        shutil.rmtree(TYPES)
    project()
    copy_std_types()
    make_cell_state()
    make_packml()
    make_gate()
    make_chain()
    for kind in ["DO", "DI", "AI"]:
        make_io_route(kind)
        make_io(kind)
    make_skill_facade()
    make_unit_facade()
    for name, s in SKILLS.items():
        make_skill(name, s)
    make_observer()
    make_unit_observer()
    make_occupation()
    make_unit()
    make_facade()
    make_patterns()
    make_demo_types()
    for sds, rds in sorted(SERVERS):
        GenericComm(sds, rds).write()
    make_system()
    (ROOT.parent / "tools" / "types-manifest.json").write_text(json.dumps(
        [{"type": n, "kind": k, "file": f, "exported": e} for n, k, f, e in MANIFEST], indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
