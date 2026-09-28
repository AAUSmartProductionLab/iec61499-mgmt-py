"""Unit-independent types: IO primitives, session-based occupation and the unit state manager.

Device-local channels (FORTE's ``loc[...]`` layer) carry the occupation owner to every block
that accepts OPC UA commands, and equipment state and commands between equipment and skills.
A channel may have many publishers and subscribers, so blocks added online need no wiring
for them. Channel names are ``<Unit>/owner``, ``<Unit>/owner/query``, ``<Unit>/<Equipment>/state``
and ``<Unit>/<Equipment>/cmd``.
"""
from __future__ import annotations

from .fbxml import STD, Basic, Composite, Project, Simple

LIB = "unitlib"
# Error codes returned by OPC UA methods and skills.
ERRORS = {"PreconditionViolated": 1, "InvariantViolated": 2, "Timeout": 3, "NotReady": 4,
          "NotPermitted": 5, "Busy": 6, "Interrupted": 7, "OutOfRange": 8}
# Unit PackML states (ISA-TR88 numbering) used so far.
STATES = {"Clearing": 1, "Stopped": 2, "Starting": 3, "Idle": 4, "Execute": 6, "Aborting": 8, "Aborted": 9,
          "Resetting": 15, "Completing": 16, "Complete": 17}
# Skill (behaviour-tree node) states.
SKILL_STATES = {"Idle": 0, "Running": 1, "Succeeded": 2, "Failed": 3}


def q(name):
    """Qualify a library type name."""
    return f"{LIB}::{name}"


def cat(*terms):
    """Nested ST CONCAT of WSTRING terms (FORTE's CONCAT is safest with two arguments)."""
    expr = terms[0]
    for t in terms[1:]:
        expr = f"CONCAT({expr}, {t})"
    return expr


def lit(text):
    """WSTRING literal."""
    return '"' + text + '"'


def loc(unit_var, *parts):
    """ST expression of a device-local channel ID below the unit."""
    return cat(lit("loc["), unit_var, lit("/" + "/".join(parts) + "]") if parts else lit("]"))


def make_io(p: Project):
    """IO_DO, IO_DI, IO_AI: backend 0 simulated, 1 GPIO (IX/QX/IW), 2 Modbus CLIENT."""
    for kind in ["DO", "DI", "AI"]:
        vtype = {"DO": "BOOL", "DI": "BOOL", "AI": "LREAL"}[kind]
        raw = {"DO": "BOOL", "DI": "BOOL", "AI": "WORD"}[kind]
        ei = {"INIT": ["Backend"], "IO_READY": ["QO_G", "QO_M"], "CNF_G": ["QO_G"], "CNF_M": ["QO_M"]}
        iv = {"Backend": "USINT", "QO_G": "BOOL", "QO_M": "BOOL"}
        eo = {"INIT_IO": ["GQI", "MQI"], "INITO": ["QO"], "REQ_G": [], "REQ_M": [], "CNF": ["QO"]}
        ov = {"GQI": "BOOL", "MQI": "BOOL", "QO": "BOOL"}
        if kind == "DO":
            ei["REQ"], iv["OUT"] = ["OUT"], "BOOL"
            eo["REQ_G"] = eo["REQ_M"] = ["Value"]
            ov["Value"] = "BOOL"
        else:
            ei["REQ"] = ["SimValue"] + (["Scale"] if kind == "AI" else [])
            ei["CNF_G"], ei["CNF_M"] = ["QO_G", "IN_G"], ["QO_M", "IN_M"]
            iv.update({"SimValue": vtype, "IN_G": raw, "IN_M": raw})
            if kind == "AI":
                iv["Scale"] = ("LREAL", "1.0")
            eo["CNF"] = ["QO", "IN"]
            ov["IN"] = vtype
        b = Basic(p, LIB, f"IO_Route{kind}", f"Backend router for IO_{kind}: 0 simulated, 1 GPIO, 2 Modbus",
                  ei, eo, iv, ov, folder="IO/Base")
        b.state("START")
        b.state("Init", "GQI := Backend = 1;\nMQI := Backend = 2;", "INIT_IO")
        b.state("Ready", "QO := (Backend = 0) OR ((Backend = 1) AND QO_G) OR ((Backend = 2) AND QO_M);", "INITO")
        b.trans("START", "Init", "INIT")
        b.trans("Init", "START", "1")
        b.trans("START", "Ready", "IO_READY")
        b.trans("Ready", "START", "1")
        b.state("ReqG", None, "REQ_G")
        if kind == "DO":
            # A FORTE CLIENT confirms only when data comes back, and a write-only Modbus
            # CLIENT_1_0 receives nothing: confirm once the write is sent, ignore any CNF_M.
            b.state("ReqM", "QO := QO_M;", "REQ_M", ["CNF"])
            b.state("Req", "Value := OUT;")
            b.state("Sim", "QO := TRUE;", "CNF")
            b.trans("START", "Req", "REQ")
            b.trans("Req", "ReqG", "Backend = 1")
            b.trans("Req", "ReqM", "Backend = 2")
            b.trans("Req", "Sim", "1")
            b.state("DoneG", "QO := QO_G;", "CNF")
            b.state("DoneM", "QO := QO_M;")
        else:
            b.state("ReqM", None, "REQ_M")
            conv = "UINT_TO_LREAL(WORD_TO_UINT({0})) * Scale" if kind == "AI" else "{0}"
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

        gpio = {"DO": STD["QX"], "DI": STD["IX"], "AI": STD["IW"]}[kind]
        client = STD["CLIENT_1_0"] if kind == "DO" else STD["CLIENT_0_1"]
        iv = {"Backend": "USINT", "GpioName": "STRING", "ModbusId": "WSTRING"}
        ev_in = {"INIT": (["Backend", "GpioName", "ModbusId"], "EInit")}
        ev_out = {"INITO": (["QO"], "EInit")}
        ov = {"QO": "BOOL"}
        if kind == "DO":
            ev_in["REQ"], iv["OUT"], ev_out["CNF"] = ["OUT"], "BOOL", ["QO"]
        else:
            ev_in["REQ"] = ["SimValue"] + (["Scale"] if kind == "AI" else [])
            iv["SimValue"] = vtype
            if kind == "AI":
                iv["Scale"] = ("LREAL", "1.0")
            ev_out["CNF"], ov["IN"] = ["QO", "IN"], vtype
        label = {"DO": "Digital output", "DI": "Digital input", "AI": "Analog input"}[kind]
        c = Composite(p, LIB, f"IO_{kind}", f"{label} primitive; Backend 0 simulated, 1 GPIO "
                      f"({gpio.split('::')[-1]} + GPIOChip handle), 2 Modbus CLIENT", ev_in, ev_out, iv, ov, folder="IO")
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


def make_owner_view(p: Project):
    """UNIT_OwnerView: local copy of the occupation owner for blocks that accept OPC UA commands."""
    # The subscriber's ANY output must end on a typed FB input: FORTE types a generic comm pin
    # only from such a connection, not from a composite interface pin (INIT fails: INVALID_ID).
    Simple(p, LIB, "UNIT_OwnerLatch", "Local channel IDs of the occupation owner and its refresh query; "
           "types and forwards the received owner",
           {"INIT": (["Unit"], "EInit"), "REQ": ["Received"]}, {"INITO": (["IdOwner", "IdQuery"], "EInit"),
                                                               "CNF": ["Owner"]},
           {"Unit": "WSTRING", "Received": "WSTRING"}, {"IdOwner": "WSTRING", "IdQuery": "WSTRING", "Owner": "WSTRING"},
           {"INIT": (f"IdOwner := {loc('Unit', 'owner')};\nIdQuery := {loc('Unit', 'owner', 'query')};", "INITO"),
            "REQ": ("Owner := Received;", "CNF")}, folder="Unit/Base").write()
    c = Composite(p, LIB, "UNIT_OwnerView",
                  "Subscribes to the unit's occupation owner (local channel) and asks for the current owner at INIT",
                  {"INIT": (["Unit"], "EInit")}, {"INITO": ([], "EInit"), "CHG": ["Owner"]},
                  {"Unit": "WSTRING"}, {"Owner": "WSTRING"}, folder="Unit/Base")
    c.fb("Latch", q("UNIT_OwnerLatch"))
    c.fb("OwnerSub", p.subscribe(1), QI="TRUE")
    c.fb("Query", p.publish(0), QI="TRUE")
    c.chain("INIT", ["Latch", "OwnerSub", "Query"], ["Query.REQ", "INITO"])
    c.da("Unit", "Latch.Unit")
    c.da("Latch.IdOwner", "OwnerSub.ID")
    c.da("Latch.IdQuery", "Query.ID")
    c.ev("OwnerSub.IND", "Latch.REQ")
    c.da("OwnerSub.RD_1", "Latch.Received")
    c.ev("Latch.CNF", "CHG")
    c.da("Latch.Owner", "Owner")
    c.write()


def make_occupation(p: Project):
    """UNIT_Occupation: Occupy/Release by session ID over OPC UA; owner on a local channel."""
    root = cat("UaRoot", lit("/Occupation/"))
    Simple(p, LIB, "UNIT_OccupationIds", "OPC UA and local channel IDs of the occupation",
           {"INIT": (["Unit", "UaRoot"], "EInit")},
           {"INITO": (["IdOccupy", "IdRelease", "IdPub", "IdOwner", "IdQuery"], "EInit")},
           {"Unit": "WSTRING", "UaRoot": "WSTRING"},
           {"IdOccupy": "WSTRING", "IdRelease": "WSTRING", "IdPub": "WSTRING", "IdOwner": "WSTRING",
            "IdQuery": "WSTRING"},
           {"INIT": (f"IdOccupy := {cat(lit('opc_ua[CREATE_METHOD;'), root, lit('Occupy]'))};\n"
                     f"IdRelease := {cat(lit('opc_ua[CREATE_METHOD;'), root, lit('Release]'))};\n"
                     f"IdPub := {cat(lit('opc_ua[WRITE;'), root, lit('Occupied]'))};\n"
                     f"IdOwner := {loc('Unit', 'owner')};\nIdQuery := {loc('Unit', 'owner', 'query')};", "INITO")},
           folder="Unit/Base").write()
    e = ERRORS["NotPermitted"]
    b = Basic(p, LIB, "UNIT_OccupationLogic",
              "Occupation by session ID: Occupy when free (or again by the owner), Release only by the owner",
              {"OCCUPY": ["S_Occupy"], "RELEASE": ["S_Release"], "QUERY": []},
              {"RSP_OCCUPY": ["Accepted", "ErrorID"], "RSP_RELEASE": ["Accepted", "ErrorID"],
               "CHG": ["Owner", "Occupied"]},
              {"S_Occupy": "WSTRING", "S_Release": "WSTRING"},
              {"Accepted": "BOOL", "ErrorID": "UINT", "Owner": "WSTRING", "Occupied": "BOOL"}, folder="Unit/Base")
    b.state("START")
    b.state("Occupy", 'IF (S_Occupy <> "") AND ((Owner = "") OR (Owner = S_Occupy)) THEN\n'
                      "  Owner := S_Occupy;\n  Occupied := TRUE;\n  Accepted := TRUE;\n  ErrorID := 0;\n"
                      f"ELSE\n  Accepted := FALSE;\n  ErrorID := {e};\nEND_IF;", "RSP_OCCUPY", ["CHG"])
    b.state("Release", 'IF (Owner <> "") AND (Owner = S_Release) THEN\n'
                       '  Owner := "";\n  Occupied := FALSE;\n  Accepted := TRUE;\n  ErrorID := 0;\n'
                       f"ELSE\n  Accepted := FALSE;\n  ErrorID := {e};\nEND_IF;", "RSP_RELEASE", ["CHG"])
    b.state("Query", None, "CHG")
    for s, ev in [("Occupy", "OCCUPY"), ("Release", "RELEASE"), ("Query", "QUERY")]:
        b.trans("START", s, ev)
        b.trans(s, "START", "1")
    b.write()

    c = Composite(p, LIB, "UNIT_Occupation",
                  "Unit occupation: OPC UA methods Occupy(Session) and Release(Session) answer [Accepted, ErrorID]; "
                  "publishes Occupied (never the session ID) and shares the owner on a local channel",
                  {"INIT": (["Unit", "UaRoot", "UaEnable"], "EInit")}, {"INITO": ([], "EInit")},
                  {"Unit": "WSTRING", "UaRoot": "WSTRING", "UaEnable": "BOOL"}, {}, folder="Unit")
    c.fb("Ids", q("UNIT_OccupationIds"))
    c.fb("Occupy", p.server(2, 1))
    c.fb("Release", p.server(2, 1))
    c.fb("Logic", q("UNIT_OccupationLogic"))
    c.fb("PubOwner", p.publish(1), QI="TRUE")
    c.fb("SubQuery", p.subscribe(0), QI="TRUE")
    c.fb("PubUa", p.publish(1))
    c.chain("INIT", ["Ids", "Occupy", "Release", "PubOwner", "SubQuery", "PubUa"], ["PubUa.REQ", "INITO"])
    c.da("Unit", "Ids.Unit")
    c.da("UaRoot", "Ids.UaRoot")
    c.da("UaEnable", "Occupy.QI", "Release.QI", "PubUa.QI")
    c.da("Ids.IdOccupy", "Occupy.ID")
    c.da("Ids.IdRelease", "Release.ID")
    c.da("Ids.IdPub", "PubUa.ID")
    c.da("Ids.IdOwner", "PubOwner.ID")
    c.da("Ids.IdQuery", "SubQuery.ID")
    for m in ["Occupy", "Release"]:
        c.ev(f"{m}.IND", f"Logic.{m.upper()}")
        c.da(f"{m}.RD_1", f"Logic.S_{m}")
        c.ev(f"Logic.RSP_{m.upper()}", f"{m}.RSP")
        c.da("Logic.Accepted", f"{m}.SD_1")
        c.da("Logic.ErrorID", f"{m}.SD_2")
    c.ev("SubQuery.IND", "Logic.QUERY")
    c.ev("Logic.CHG", "PubOwner.REQ", "PubUa.REQ")
    c.da("Logic.Owner", "PubOwner.SD_1")
    c.da("Logic.Occupied", "PubUa.SD_1")
    c.write()


# Unit commands so far: name -> (states it is valid in, state it leads to).
UNIT_COMMANDS = {"Reset": (["Stopped", "Complete"], "Resetting"), "Start": (["Idle"], "Starting"),
                 "Clear": (["Aborted"], "Clearing")}
STABLE = ["Stopped", "Idle", "Execute", "Complete", "Aborted"]


def make_state_manager(p: Project):
    """UNIT_StateManager: reduced PackML unit machine; runs the Execute procedure; owner-only commands."""
    root = cat("UaRoot", lit("/Unit/"))
    ids = {f"Id{m}": cat(lit("opc_ua[CREATE_METHOD;"), root, lit(m + "]")) for m in UNIT_COMMANDS}
    ids["IdPub"] = cat(lit("opc_ua[WRITE;"), root, lit("State]"))
    Simple(p, LIB, "UNIT_StateIds", "OPC UA IDs of the unit commands and state",
           {"INIT": (["UaRoot"], "EInit")}, {"INITO": (list(ids), "EInit")},
           {"UaRoot": "WSTRING"}, {k: "WSTRING" for k in ids},
           {"INIT": ("\n".join(f"{k} := {v};" for k, v in ids.items()), "INITO")}, folder="Unit/Base").write()

    ei = {f"CMD_{m.upper()}": [f"S_{m}"] for m in UNIT_COMMANDS}
    ei.update({"OWNER_CHG": ["Owner"], "EXECUTE_DONE": [], "EXECUTE_FAILED": []})
    eo = {f"RSP_{m.upper()}": ["Accepted", "ErrorID"] for m in UNIT_COMMANDS}
    eo.update({"CNF": ["State"], "EXECUTE": []})
    b = Basic(p, LIB, "UNIT_StateLogic",
              "Reduced PackML unit state machine: Reset/Start/Clear only from the occupation owner and only in a "
              "valid state; Execute runs the procedure until it reports DONE (Complete) or FAILED (Aborted)",
              ei, eo, {**{f"S_{m}": "WSTRING" for m in UNIT_COMMANDS}, "Owner": "WSTRING"},
              {"State": ("USINT", str(STATES["Stopped"])), "Accepted": "BOOL", "ErrorID": "UINT"},
              {"Owned": "BOOL"}, folder="Unit/Base")
    for s in ["Stopped", "Resetting", "Idle", "Starting", "Execute", "Completing", "Complete", "Aborting",
              "Aborted", "Clearing"]:
        b.state(s, f"State := {STATES[s]};", "CNF", ["EXECUTE"] if s == "Starting" else [])
    for m, (valid, target) in UNIT_COMMANDS.items():
        allowed = " OR ".join(f"(State = {STATES[v]})" for v in valid)
        b.state("Chk" + m, f'Owned := (S_{m} = Owner) AND (Owner <> "");\n'
                           f"Accepted := Owned AND ({allowed});\n"
                           f"IF NOT Owned THEN\n  ErrorID := {ERRORS['NotPermitted']};\n"
                           f"ELSIF NOT Accepted THEN\n  ErrorID := {ERRORS['NotReady']};\nELSE\n  ErrorID := 0;\nEND_IF;",
                f"RSP_{m.upper()}")
        for s in STABLE:
            b.trans(s, "Chk" + m, f"CMD_{m.upper()}")
        b.trans("Chk" + m, target, "Accepted")
        # A refused command returns to the state it came from (re-entering only republishes State).
        for s in STABLE:
            b.trans("Chk" + m, s, f"State = {STATES[s]}")
    b.trans("Resetting", "Idle", "1")
    b.trans("Starting", "Execute", "1")
    b.trans("Execute", "Completing", "EXECUTE_DONE")
    b.trans("Execute", "Aborting", "EXECUTE_FAILED")
    b.trans("Completing", "Complete", "1")
    b.trans("Aborting", "Aborted", "1")
    b.trans("Clearing", "Stopped", "1")
    b.write()

    c = Composite(p, LIB, "UNIT_StateManager",
                  "Unit state manager: OPC UA methods Reset/Start/Clear(Session) answer [Accepted, ErrorID]; "
                  "publishes the PackML State; EXECUTE starts the Execute procedure",
                  {"INIT": (["Unit", "UaRoot", "UaEnable"], "EInit"), "EXECUTE_DONE": [], "EXECUTE_FAILED": []},
                  {"INITO": ([], "EInit"), "EXECUTE": []},
                  {"Unit": "WSTRING", "UaRoot": "WSTRING", "UaEnable": "BOOL"}, {}, folder="Unit")
    c.fb("Ids", q("UNIT_StateIds"))
    c.fb("Owner", q("UNIT_OwnerView"))
    servers = list(UNIT_COMMANDS)
    for m in servers:
        c.fb(m, p.server(2, 1))
    c.fb("Logic", q("UNIT_StateLogic"))
    c.fb("PubUa", p.publish(1))
    c.chain("INIT", ["Ids", "Owner", *servers, "PubUa"], ["PubUa.REQ", "INITO"])
    c.da("UaRoot", "Ids.UaRoot")
    c.da("Unit", "Owner.Unit")
    c.da("UaEnable", *[f"{m}.QI" for m in servers], "PubUa.QI")
    c.ev("Owner.CHG", "Logic.OWNER_CHG")
    c.da("Owner.Owner", "Logic.Owner")
    for m in servers:
        c.da(f"Ids.Id{m}", f"{m}.ID")
        c.ev(f"{m}.IND", f"Logic.CMD_{m.upper()}")
        c.da(f"{m}.RD_1", f"Logic.S_{m}")
        c.ev(f"Logic.RSP_{m.upper()}", f"{m}.RSP")
        c.da("Logic.Accepted", f"{m}.SD_1")
        c.da("Logic.ErrorID", f"{m}.SD_2")
    c.da("Ids.IdPub", "PubUa.ID")
    c.ev("Logic.CNF", "PubUa.REQ")
    c.da("Logic.State", "PubUa.SD_1")
    c.ev("Logic.EXECUTE", "EXECUTE")
    c.ev("EXECUTE_DONE", "Logic.EXECUTE_DONE")
    c.ev("EXECUTE_FAILED", "Logic.EXECUTE_FAILED")
    c.write()


def make_library(p: Project):
    """Write every unit-independent type."""
    make_io(p)
    make_owner_view(p)
    make_occupation(p)
    make_state_manager(p)
