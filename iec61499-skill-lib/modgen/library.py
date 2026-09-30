"""Module-independent types (package ``modlib``): IO primitives, occupation, module state manager and
the skill state machine shared by every skill primitive and module level skill.

Device-local channels (FORTE's ``loc[...]`` layer) connect the blocks without wiring, so skills
added online need no connections to the module level or the equipment:

``<Module>/owner`` (+ ``/query``)  occupation owner (WSTRING)
``<Module>/state`` (+ ``/query``)  module PackML state (USINT)
``<Module>/activity``              +1 when a skill starts running, -1 when it ends (INT)
``<Module>/<Equipment>/cmd``       (Holder, Command, Arg, Release) to the equipment
``<Module>/<Equipment>/state``     (inputs..., Holder) from the equipment
"""
from __future__ import annotations

from .fbxml import STD, Basic, Composite, Project, Simple

LIB = "modlib"
# Error codes returned by OPC UA methods and skills.
ERRORS = {"PreconditionViolated": 1, "InvariantViolated": 2, "Timeout": 3, "NotReady": 4,
          "NotPermitted": 5, "Busy": 6, "Interrupted": 7, "OutOfRange": 8}
# Module PackML states (ISA-TR88 numbering) used by the module state manager.
STATES = {"Clearing": 1, "Stopped": 2, "Starting": 3, "Idle": 4, "Execute": 6, "Stopping": 7, "Aborting": 8,
          "Aborted": 9, "Resetting": 15}
# Skill states (every skill primitive and module level skill).
SKILL_STATES = {"Idle": 0, "Running": 1, "Stopping": 2, "Succeeded": 3, "Failed": 4, "Aborted": 5}
KEEP = 255  # equipment command that changes no output (release only)


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


def loc(module_var, *parts):
    """ST expression of a device-local channel ID below the module."""
    return cat(lit("loc["), module_var, lit("/" + "/".join(parts) + "]") if parts else lit("]"))


def ua(kind, *terms):
    """ST expression of an OPC UA ID (``opc_ua[<kind>;<path>]``) from WSTRING terms."""
    return cat(lit(f"opc_ua[{kind};"), *terms, lit("]"))


# --------------------------------------------------------------------------------------------
# IO primitives
# --------------------------------------------------------------------------------------------

def make_io(p: Project):
    """IO_DO, IO_DI, IO_AI, IO_AO: backend 0 simulated, 1 local IO handle (GPIO line, PWM channel), 2 Modbus."""
    for kind in ["DO", "DI", "AI", "AO"]:
        output = kind in ("DO", "AO")
        vtype = {"DO": "BOOL", "DI": "BOOL", "AI": "LREAL", "AO": "LREAL"}[kind]
        raw = {"DO": "BOOL", "DI": "BOOL", "AI": "WORD", "AO": "WORD"}[kind]
        ei = {"INIT": ["Backend"], "IO_READY": ["QO_G", "QO_M"], "CNF_G": ["QO_G"], "CNF_M": ["QO_M"]}
        iv = {"Backend": "USINT", "QO_G": "BOOL", "QO_M": "BOOL"}
        eo = {"INIT_IO": ["GQI", "MQI"], "INITO": ["QO"], "REQ_G": [], "REQ_M": [], "CNF": ["QO"]}
        ov = {"GQI": "BOOL", "MQI": "BOOL", "QO": "BOOL"}
        if output:
            ei["REQ"], iv["OUT"] = ["OUT"], vtype
            if kind == "AO":
                ei["REQ"] += ["EN", "Gain", "Bias"]
                iv.update({"EN": "BOOL", "Gain": ("LREAL", "1.0"), "Bias": "LREAL"})
            eo["REQ_G"] = eo["REQ_M"] = ["Value"]
            ov["Value"] = raw
        else:
            ei["REQ"] = ["SimValue"] + (["Scale"] if kind == "AI" else [])
            ei["CNF_G"], ei["CNF_M"] = ["QO_G", "IN_G"], ["QO_M", "IN_M"]
            iv.update({"SimValue": vtype, "IN_G": raw, "IN_M": raw})
            if kind == "AI":
                iv["Scale"] = ("LREAL", "1.0")
            eo["CNF"] = ["QO", "IN"]
            ov["IN"] = vtype
        b = Basic(p, LIB, f"IO_Route{kind}", f"Backend router for IO_{kind}: 0 simulated, 1 local IO handle, 2 Modbus",
                  ei, eo, iv, ov, {"Raw": "LREAL"} if kind == "AO" else None, folder="IO/Base")
        b.state("START")
        b.state("Init", "GQI := Backend = 1;\nMQI := Backend = 2;", "INIT_IO")
        b.state("Ready", "QO := (Backend = 0) OR ((Backend = 1) AND QO_G) OR ((Backend = 2) AND QO_M);", "INITO")
        b.trans("START", "Init", "INIT")
        b.trans("Init", "START", "1")
        b.trans("START", "Ready", "IO_READY")
        b.trans("Ready", "START", "1")
        b.state("ReqG", None, "REQ_G")
        if output:
            # A FORTE CLIENT confirms only when data comes back, and a write-only Modbus
            # CLIENT_1_0 receives nothing: confirm once the write is sent, ignore any CNF_M.
            b.state("ReqM", "QO := QO_M;", "REQ_M", ["CNF"])
            if kind == "AO":
                # Off (EN = FALSE) is a raw 0 (no PWM pulses), not the value 0 (a servo would move to 0°).
                # Clamped with IF: FORTE 3.3.0's func_LIMIT.h does not include func_MIN/func_MAX.
                b.state("Req", "IF EN THEN\n  Raw := Bias + OUT * Gain;\n  IF Raw < 0.0 THEN\n    Raw := 0.0;\n"
                               "  ELSIF Raw > 65535.0 THEN\n    Raw := 65535.0;\n  END_IF;\n"
                               "  Value := UINT_TO_WORD(LREAL_TO_UINT(Raw));\nELSE\n  Value := WORD#0;\nEND_IF;")
            else:
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

        local = {"DO": STD["QX"], "DI": STD["IX"], "AI": STD["IW"], "AO": STD["QW"]}[kind]
        client = STD["CLIENT_1_0"] if output else STD["CLIENT_0_1"]
        iv = {"Backend": "USINT", "IoName": "STRING", "ModbusId": "WSTRING"}
        ev_in = {"INIT": (["Backend", "IoName", "ModbusId"], "EInit")}
        ev_out = {"INITO": (["QO"], "EInit")}
        ov = {"QO": "BOOL"}
        if output:
            ev_in["REQ"], iv["OUT"], ev_out["CNF"] = ["OUT"], vtype, ["QO"]
            if kind == "AO":
                ev_in["REQ"] += ["EN", "Gain", "Bias"]
                iv.update({"EN": "BOOL", "Gain": ("LREAL", "1.0"), "Bias": "LREAL"})
        else:
            ev_in["REQ"] = ["SimValue"] + (["Scale"] if kind == "AI" else [])
            iv["SimValue"] = vtype
            if kind == "AI":
                iv["Scale"] = ("LREAL", "1.0")
            ev_out["CNF"], ov["IN"] = ["QO", "IN"], vtype
        label = {"DO": "Digital output", "DI": "Digital input", "AI": "Analog input",
                 "AO": "Analog output (raw = Bias + OUT * Gain, 0..65535; EN = FALSE writes 0)"}[kind]
        c = Composite(p, LIB, f"IO_{kind}", f"{label}; Backend 0 simulated, 1 local IO handle "
                      f"({local.split('::')[-1]}, e.g. GPIOChip or PWM channel), 2 Modbus CLIENT",
                      ev_in, ev_out, iv, ov, folder="IO")
        c.fb("Route", q(f"IO_Route{kind}"))
        c.fb("Local", local)
        c.fb("Bus", client)
        c.ev("INIT", "Route.INIT")
        c.ev("Route.INIT_IO", "Local.INIT")
        c.ev("Local.INITO", "Bus.INIT")
        c.ev("Bus.INITO", "Route.IO_READY")
        c.ev("Route.INITO", "INITO")
        c.ev("REQ", "Route.REQ")
        c.ev("Route.REQ_G", "Local.REQ")
        c.ev("Route.REQ_M", "Bus.REQ")
        c.ev("Local.CNF", "Route.CNF_G")
        c.ev("Bus.CNF", "Route.CNF_M")
        c.ev("Route.CNF", "CNF")
        c.da("Backend", "Route.Backend")
        c.da("IoName", "Local.PARAMS")
        c.da("ModbusId", "Bus.ID")
        c.da("Route.GQI", "Local.QI")
        c.da("Route.MQI", "Bus.QI")
        c.da("Local.QO", "Route.QO_G")
        c.da("Bus.QO", "Route.QO_M")
        c.da("Route.QO", "QO")
        if output:
            c.da("OUT", "Route.OUT")
            if kind == "AO":
                for v in ["EN", "Gain", "Bias"]:
                    c.da(v, "Route." + v)
            c.da("Route.Value", "Local.OUT", "Bus.SD_1")
        else:
            c.da("SimValue", "Route.SimValue")
            if kind == "AI":
                c.da("Scale", "Route.Scale")
            c.da("Local.IN", "Route.IN_G")
            c.da("Bus.RD_1", "Route.IN_M")
            c.da("Route.IN", "IN")
        c.write()


# --------------------------------------------------------------------------------------------
# Views on the module level channels
# --------------------------------------------------------------------------------------------

def make_view(p: Project, name: str, channel: str, var: str, vtype: str, what: str):
    """MOD_<name>View: subscribes to ``<Module>/<channel>`` and asks for the current value at INIT.

    The subscriber's ANY output must end on a typed FB input: FORTE types a generic comm pin only
    from such a connection, not from a composite interface pin (INIT fails: INVALID_ID). Hence the
    latch block.
    """
    Simple(p, LIB, f"MOD_{name}Latch", f"Local channel IDs of the {what} and its refresh query; types and "
           f"forwards the received {what}",
           {"INIT": (["Module"], "EInit"), "REQ": ["Received"]},
           {"INITO": (["IdSub", "IdQuery"], "EInit"), "CNF": [var]},
           {"Module": "WSTRING", "Received": vtype}, {"IdSub": "WSTRING", "IdQuery": "WSTRING", var: vtype},
           {"INIT": (f"IdSub := {loc('Module', channel)};\nIdQuery := {loc('Module', channel, 'query')};", "INITO"),
            "REQ": (f"{var} := Received;", "CNF")}, folder="Module/Base").write()
    c = Composite(p, LIB, f"MOD_{name}View",
                  f"The module's {what} from its local channel; asks for the current value at INIT",
                  {"INIT": (["Module"], "EInit")}, {"INITO": ([], "EInit"), "CHG": [var]},
                  {"Module": "WSTRING"}, {var: vtype}, folder="Module/Base")
    c.fb("Latch", q(f"MOD_{name}Latch"))
    c.fb("Listen", p.subscribe(1), QI="TRUE")
    c.fb("Query", p.publish(0), QI="TRUE")
    c.chain("INIT", ["Latch", "Listen", "Query"], ["Query.REQ", "INITO"])
    c.da("Module", "Latch.Module")
    c.da("Latch.IdSub", "Listen.ID")
    c.da("Latch.IdQuery", "Query.ID")
    c.ev("Listen.IND", "Latch.REQ")
    c.da("Listen.RD_1", "Latch.Received")
    c.ev("Latch.CNF", "CHG")
    c.da(f"Latch.{var}", var)
    c.write()


# --------------------------------------------------------------------------------------------
# Occupation
# --------------------------------------------------------------------------------------------

def make_occupation(p: Project):
    """MOD_Occupation: Occupy/Release by session ID over OPC UA; owner on a local channel."""
    root = cat("UaRoot", lit("/Occupation/"))
    Simple(p, LIB, "MOD_OccupationIds", "OPC UA and local channel IDs of the occupation",
           {"INIT": (["Module", "UaRoot"], "EInit")},
           {"INITO": (["IdOccupy", "IdRelease", "IdPub", "IdOwner", "IdQuery"], "EInit")},
           {"Module": "WSTRING", "UaRoot": "WSTRING"},
           {"IdOccupy": "WSTRING", "IdRelease": "WSTRING", "IdPub": "WSTRING", "IdOwner": "WSTRING",
            "IdQuery": "WSTRING"},
           {"INIT": (f"IdOccupy := {ua('CREATE_METHOD', root, lit('Occupy'))};\n"
                     f"IdRelease := {ua('CREATE_METHOD', root, lit('Release'))};\n"
                     f"IdPub := {ua('WRITE', root, lit('Occupied'))};\n"
                     f"IdOwner := {loc('Module', 'owner')};\nIdQuery := {loc('Module', 'owner', 'query')};", "INITO")},
           folder="Module/Base").write()
    e = ERRORS["NotPermitted"]
    b = Basic(p, LIB, "MOD_OccupationLogic",
              "Occupation by session ID: Occupy when free (or again by the owner), Release only by the owner",
              {"OCCUPY": ["S_Occupy"], "RELEASE": ["S_Release"], "QUERY": []},
              {"RSP_OCCUPY": ["Accepted", "ErrorID"], "RSP_RELEASE": ["Accepted", "ErrorID"],
               "CHG": ["Owner", "Occupied"]},
              {"S_Occupy": "WSTRING", "S_Release": "WSTRING"},
              {"Accepted": "BOOL", "ErrorID": "UINT", "Owner": "WSTRING", "Occupied": "BOOL"}, folder="Module/Base")
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

    c = Composite(p, LIB, "MOD_Occupation",
                  "Module occupation: OPC UA methods Occupy(Session) and Release(Session) answer [Accepted, ErrorID]; "
                  "publishes Occupied (never the session ID) and shares the owner on a local channel",
                  {"INIT": (["Module", "UaRoot", "UaEnable"], "EInit")}, {"INITO": ([], "EInit")},
                  {"Module": "WSTRING", "UaRoot": "WSTRING", "UaEnable": "BOOL"}, {}, folder="Module")
    c.fb("Ids", q("MOD_OccupationIds"))
    c.fb("Occupy", p.server(2, 1))
    c.fb("Release", p.server(2, 1))
    c.fb("Logic", q("MOD_OccupationLogic"))
    c.fb("PubOwner", p.publish(1), QI="TRUE")
    c.fb("SubQuery", p.subscribe(0), QI="TRUE")
    c.fb("PubUa", p.publish(1))
    c.chain("INIT", ["Ids", "Occupy", "Release", "PubOwner", "SubQuery", "PubUa"], ["PubUa.REQ", "INITO"])
    c.da("Module", "Ids.Module")
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


# --------------------------------------------------------------------------------------------
# Module state manager
# --------------------------------------------------------------------------------------------

# Module commands: name -> (wait states it is valid in, entry state it leads to).
MODULE_COMMANDS = {"Reset": (["Stopped"], "Resetting"), "Start": (["Idle"], "Starting"),
                   "Stop": (["ResettingW", "Idle", "Execute"], "Stopping"),
                   "Abort": (["Stopped", "ResettingW", "Idle", "Execute", "StoppingW", "StopProcW"], "Aborting"),
                   "Clear": (["Aborted"], "Clearing")}
# Wait states: name -> (published PackML state, index kept in Here to return after a refused command).
MODULE_WAIT = {"Stopped": ("Stopped", 0), "ResettingW": ("Resetting", 1), "Idle": ("Idle", 2),
               "Execute": ("Execute", 3), "StoppingW": ("Stopping", 4), "StopProcW": ("Stopping", 5),
               "Aborted": ("Aborted", 6)}


def make_state_manager(p: Project):
    """MOD_StateManager: the module's PackML state machine, the governing layer above all skills.

    Stopped -Reset-> Resetting {Resetting procedure} -> Idle -Start-> Starting -> Execute, where the
    module stays while the occupant runs skills. Stop -> Stopping: the state is published, running
    skills stop themselves; when no skill is active any more the Stopping procedure runs -> Stopped
    (no end within StopTimeout -> Aborting). Abort -> Aborting: skills and equipment switch off at
    once -> Aborted -Clear-> Clearing -> Stopped.
    """
    root = cat("UaRoot", lit("/Module/"))
    ids = {f"Id{m}": ua("CREATE_METHOD", root, lit(m)) for m in MODULE_COMMANDS}
    ids["IdPub"] = ua("WRITE", root, lit("State"))
    ids["IdState"] = loc("Module", "state")
    ids["IdQuery"] = loc("Module", "state", "query")
    ids["IdAct"] = loc("Module", "activity")
    Simple(p, LIB, "MOD_StateIds", "OPC UA and local channel IDs of the module state manager",
           {"INIT": (["Module", "UaRoot"], "EInit")}, {"INITO": (list(ids), "EInit")},
           {"Module": "WSTRING", "UaRoot": "WSTRING"}, {k: "WSTRING" for k in ids},
           {"INIT": ("\n".join(f"{k} := {v};" for k, v in ids.items()), "INITO")}, folder="Module/Base").write()
    Simple(p, LIB, "MOD_ActivityCount", "Number of running skills from the +1/-1 activity channel",
           {"ACT": ["Delta"]}, {"CHG": ["Active", "AllIdle"]},
           {"Delta": "INT"}, {"Active": "INT", "AllIdle": ("BOOL", "TRUE")},
           {"ACT": ("Active := Active + Delta;\nIF Active < 0 THEN\n  Active := 0;\nEND_IF;\nAllIdle := Active = 0;",
                    "CHG")}, folder="Module/Base").write()

    ei = {f"CMD_{m.upper()}": [f"S_{m}"] for m in MODULE_COMMANDS}
    ei.update({"OWNER_CHG": ["Owner"], "ACT": ["AllIdle"], "RESETTING_DONE": [], "RESETTING_FAILED": [],
               "STOPPING_DONE": [], "STOPPING_FAILED": [], "STOP_TIMEOUT": []})
    eo = {f"RSP_{m.upper()}": ["Accepted", "ErrorID"] for m in MODULE_COMMANDS}
    eo.update({"CNF": ["State"], "RUN_RESETTING": [], "RUN_STOPPING": [], "WD_START": [], "WD_STOP": []})
    b = Basic(p, LIB, "MOD_StateLogic",
              "PackML module state machine: commands only from the occupation owner and only where PackML allows "
              "them; runs the Resetting and Stopping procedures; Stopping waits until no skill is active",
              ei, eo, {**{f"S_{m}": "WSTRING" for m in MODULE_COMMANDS}, "Owner": "WSTRING",
                       "AllIdle": ("BOOL", "TRUE")},
              {"State": ("USINT", str(STATES["Stopped"])), "Accepted": "BOOL", "ErrorID": "UINT"},
              {"Owned": "BOOL", "Here": "USINT"}, folder="Module/Base")
    s = STATES
    b.state("Stopped", f"State := {s['Stopped']};\nHere := 0;", "CNF")   # initial state
    b.state("Resetting", f"State := {s['Resetting']};", "CNF", ["RUN_RESETTING"])
    b.state("ResettingW", "Here := 1;")
    b.state("Idle", f"State := {s['Idle']};\nHere := 2;", "CNF")
    b.state("Starting", f"State := {s['Starting']};", "CNF")
    b.state("Execute", f"State := {s['Execute']};\nHere := 3;", "CNF")
    b.state("Stopping", f"State := {s['Stopping']};", "CNF", ["WD_START"])
    b.state("StoppingW", "Here := 4;")
    b.state("StopProc", None, "WD_STOP", ["RUN_STOPPING"])
    b.state("StopProcW", "Here := 5;")
    b.state("Aborting", f"State := {s['Aborting']};", "CNF", ["WD_STOP"])
    b.state("Aborted", f"State := {s['Aborted']};\nHere := 6;", "CNF")
    b.state("Clearing", f"State := {s['Clearing']};", "CNF")
    for m, (valid, target) in MODULE_COMMANDS.items():
        allowed = " OR ".join(f"(Here = {MODULE_WAIT[v][1]})" for v in valid)
        b.state("Chk" + m, f'Owned := (S_{m} = Owner) AND (Owner <> "");\n'
                           f"Accepted := Owned AND ({allowed});\n"
                           f"IF NOT Owned THEN\n  ErrorID := {ERRORS['NotPermitted']};\n"
                           f"ELSIF NOT Accepted THEN\n  ErrorID := {ERRORS['NotReady']};\nELSE\n  ErrorID := 0;\nEND_IF;",
                f"RSP_{m.upper()}")
        for w in MODULE_WAIT:
            b.trans(w, "Chk" + m, f"CMD_{m.upper()}")
        b.trans("Chk" + m, target, "Accepted")
        for w, (_, here) in MODULE_WAIT.items():
            b.trans("Chk" + m, w, f"Here = {here}")
    b.trans("Resetting", "ResettingW", "1")
    b.trans("ResettingW", "Idle", "RESETTING_DONE")
    b.trans("ResettingW", "Aborting", "RESETTING_FAILED")
    b.trans("Starting", "Execute", "1")
    b.trans("Stopping", "StoppingW", "1")
    b.trans("StoppingW", "StopProc", "AllIdle")         # also at once when nothing runs
    b.trans("StoppingW", "Aborting", "STOP_TIMEOUT")
    b.trans("StopProc", "StopProcW", "1")
    b.trans("StopProcW", "Stopped", "STOPPING_DONE")
    b.trans("StopProcW", "Aborting", "STOPPING_FAILED")
    b.trans("Aborting", "Aborted", "1")
    b.trans("Clearing", "Stopped", "1")
    b.write()

    c = Composite(p, LIB, "MOD_StateManager",
                  "Module state manager: OPC UA methods Reset/Start/Stop/Abort/Clear(Session) answer [Accepted, ErrorID]; "
                  "publishes the PackML State over OPC UA and on the module's state channel; RUN_RESETTING and "
                  "RUN_STOPPING start the procedures, which answer with *_DONE or *_FAILED",
                  {"INIT": (["Module", "UaRoot", "UaEnable", "StopTimeout"], "EInit"), "RESETTING_DONE": [],
                   "RESETTING_FAILED": [], "STOPPING_DONE": [], "STOPPING_FAILED": []},
                  {"INITO": ([], "EInit"), "RUN_RESETTING": [], "RUN_STOPPING": []},
                  {"Module": "WSTRING", "UaRoot": "WSTRING", "UaEnable": "BOOL", "StopTimeout": ("TIME", "T#10s")},
                  {}, folder="Module")
    c.fb("Ids", q("MOD_StateIds"))
    c.fb("Owner", q("MOD_OwnerView"))
    servers = list(MODULE_COMMANDS)
    for m in servers:
        c.fb(m, p.server(2, 1))
    c.fb("Logic", q("MOD_StateLogic"))
    c.fb("PubUa", p.publish(1))
    c.fb("PubState", p.publish(1), QI="TRUE")
    c.fb("SubQuery", p.subscribe(0), QI="TRUE")
    c.fb("SubAct", p.subscribe(1), QI="TRUE")
    c.fb("Count", q("MOD_ActivityCount"))
    c.fb("Wd", STD["E_DELAY"])
    c.chain("INIT", ["Ids", "Owner", *servers, "PubUa", "PubState", "SubQuery", "SubAct"],
            ["PubUa.REQ", "PubState.REQ", "INITO"])
    c.da("Module", "Ids.Module", "Owner.Module")
    c.da("UaRoot", "Ids.UaRoot")
    c.da("UaEnable", *[f"{m}.QI" for m in servers], "PubUa.QI")
    c.da("StopTimeout", "Wd.DT")
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
    c.da("Ids.IdState", "PubState.ID")
    c.da("Ids.IdQuery", "SubQuery.ID")
    c.da("Ids.IdAct", "SubAct.ID")
    c.ev("Logic.CNF", "PubUa.REQ", "PubState.REQ")
    c.ev("SubQuery.IND", "PubState.REQ")
    c.da("Logic.State", "PubUa.SD_1", "PubState.SD_1")
    c.ev("SubAct.IND", "Count.ACT")
    c.da("SubAct.RD_1", "Count.Delta")
    c.ev("Count.CHG", "Logic.ACT")
    c.da("Count.AllIdle", "Logic.AllIdle")
    c.ev("Logic.WD_START", "Wd.START")
    c.ev("Logic.WD_STOP", "Wd.STOP")
    c.ev("Wd.EO", "Logic.STOP_TIMEOUT")
    c.ev("Logic.RUN_RESETTING", "RUN_RESETTING")
    c.ev("Logic.RUN_STOPPING", "RUN_STOPPING")
    for e in ["RESETTING_DONE", "RESETTING_FAILED", "STOPPING_DONE", "STOPPING_FAILED"]:
        c.ev(e, f"Logic.{e}")
    c.write()


# --------------------------------------------------------------------------------------------
# Skill state machine and helpers
# --------------------------------------------------------------------------------------------

# Wait states of SKILL_Control: name -> (published skill state, Here index).
SKILL_WAIT = {"Idle": ("Idle", 0), "Running": ("Running", 1), "Stopping": ("Stopping", 2),
              "StopProc": ("Stopping", 3), "Succeeded": ("Succeeded", 4), "Failed": ("Failed", 5),
              "Aborted": ("Aborted", 6)}
READY = ["Idle", "Succeeded", "Failed"]


def make_skill_control(p: Project):
    """SKILL_Control: the state machine every skill shares (primitive or module level skill).

    Idle/Succeeded/Failed -Start-> Running -> Succeeded | Failed(ErrorID). Stop, a parent HALT or the
    module entering Stopping -> Stopping: the execution is halted, then the stop procedure runs
    (RUN_STOP -> STOP_DONE) -> Failed(Interrupted). Abort, a parent ABORT or the module entering
    Aborting -> Aborted (outputs off at once); Reset, a parent RESET or the module Clearing -> Idle
    (RESET_O passes it on to children).
    OPC UA commands need the occupation and (Start) the module in Execute; commands from a parent
    are not gated. Every start and end is counted on the module's activity channel (ACT +1/-1).
    """
    e, s = ERRORS, SKILL_STATES
    cmds = {"START": ["S_Start", "InRange", "EqFree"], "STOP": ["S_Stop"], "ABORT": ["S_Abort"], "RESET": ["S_Reset"]}
    ei = {"INIT": (["Module", "UaRoot", "UaPath"], "EInit"),
          **{f"CMD_{k}": v for k, v in cmds.items()},
          "OWNER_CHG": ["Owner"], "MOD_CHG": ["ModState"], "START": [], "HALT": [], "ABORT": [], "RESET": [],
          "EXEC_DONE": [], "EXEC_FAILED": ["ExecError"], "STOP_DONE": []}
    eo = {"INITO": (["IdStart", "IdStop", "IdAbort", "IdReset", "IdPub", "IdAct"], "EInit"),
          **{f"RSP_{k}": ["Accepted", "RspError"] for k in cmds},
          "PUB": ["State", "ErrorID"], "GO_UA": [], "GO_PARENT": [], "HALT_O": [], "ABORT_O": [], "RESET_O": [], "RUN_STOP": [],
          "SUCCESS": [], "FAILURE": ["ErrorID"], "ACT": ["Delta"]}
    iv = {"Module": "WSTRING", "UaRoot": "WSTRING", "UaPath": "WSTRING", "S_Start": "WSTRING", "InRange": "BOOL",
          "EqFree": "BOOL", "S_Stop": "WSTRING", "S_Abort": "WSTRING", "S_Reset": "WSTRING", "Owner": "WSTRING",
          "ModState": "USINT", "ExecError": "UINT"}
    ov = {"IdStart": "WSTRING", "IdStop": "WSTRING", "IdAbort": "WSTRING", "IdReset": "WSTRING", "IdPub": "WSTRING",
          "IdAct": "WSTRING", "Accepted": "BOOL", "RspError": "UINT", "State": "USINT", "ErrorID": "UINT",
          "Delta": "INT"}
    b = Basic(p, LIB, "SKILL_Control",
              "Skill state machine: Start/Stop/Abort/Reset over OPC UA (owner only, Start only in module Execute) "
              "and START/HALT/ABORT from a parent; Idle 0, Running 1, Stopping 2, Succeeded 3, Failed 4, Aborted 5",
              ei, eo, iv, ov, {"Owned": "BOOL", "Here": "USINT", "Active": "BOOL"}, folder="Skills")
    base = cat("UaRoot", "UaPath")
    b.state("START")
    b.state("Init", "\n".join([f"IdStart := {ua('CREATE_METHOD', base, lit('/Start'))};",
                               f"IdStop := {ua('CREATE_METHOD', base, lit('/Stop'))};",
                               f"IdAbort := {ua('CREATE_METHOD', base, lit('/Abort'))};",
                               f"IdReset := {ua('CREATE_METHOD', base, lit('/Reset'))};",
                               f"IdPub := {ua('WRITE', base, lit('/State;'), base, lit('/ErrorID'))};",
                               f"IdAct := {loc('Module', 'activity')};"]), "INITO")
    for w, (state, here) in SKILL_WAIT.items():
        b.state(w, f"State := {s[state]};\nHere := {here};", "PUB")
    # Entry actions.
    b.state("GoUa", "Active := TRUE;\nDelta := 1;\nErrorID := 0;", "ACT", ["GO_UA"])
    b.state("GoParent", "Active := TRUE;\nDelta := 1;\nErrorID := 0;", "ACT", ["GO_PARENT"])
    b.state("Halt", None, "HALT_O")
    b.state("RunStop", None, "RUN_STOP")
    b.state("Succeed", "Active := FALSE;\nDelta := -1;\nErrorID := 0;", "ACT", ["SUCCESS"])
    b.state("Fail", "Active := FALSE;\nDelta := -1;\nErrorID := ExecError;", "ACT", ["FAILURE"])
    b.state("Interrupted", f"Active := FALSE;\nDelta := -1;\nErrorID := {e['Interrupted']};", "ACT", ["FAILURE"])
    b.state("AbortChk")
    b.state("AbortActive", f"Active := FALSE;\nDelta := -1;\nErrorID := {e['Interrupted']};", "ABORT_O", ["ACT"])
    b.state("AbortIdle", None, "ABORT_O")
    b.state("StartRefused", f"ErrorID := {e['NotReady']};", "FAILURE")
    b.state("ResetOk", None, "RESET_O")
    # Command checks: answer the method, then act or return to the wait state (Here).
    owned = 'Owned := (S_{0} = Owner) AND (Owner <> "");\n'
    b.state("ChkStart", owned.format("Start") + "Accepted := FALSE;\n"
            f"IF NOT Owned THEN\n  RspError := {e['NotPermitted']};\n"
            f"ELSIF ModState <> {STATES['Execute']} THEN\n  RspError := {e['NotReady']};\n"
            f"ELSIF (Here = 1) OR (Here = 2) OR (Here = 3) THEN\n  RspError := {e['Busy']};\n"
            f"ELSIF Here = 6 THEN\n  RspError := {e['NotReady']};\n"
            f"ELSIF NOT InRange THEN\n  RspError := {e['OutOfRange']};\n"
            f"ELSIF NOT EqFree THEN\n  RspError := {e['Busy']};\n"
            "ELSE\n  Accepted := TRUE;\n  RspError := 0;\nEND_IF;", "RSP_START")
    for m, valid in [("Stop", "Here = 1"), ("Abort", "Here <> 6"), ("Reset", "Here = 6")]:
        b.state("Chk" + m, owned.format(m) + f"Accepted := Owned AND ({valid});\n"
                f"IF NOT Owned THEN\n  RspError := {e['NotPermitted']};\n"
                f"ELSIF NOT Accepted THEN\n  RspError := {e['NotReady']};\nELSE\n  RspError := 0;\nEND_IF;",
                f"RSP_{m.upper()}")
    b.trans("START", "Init", "INIT")
    b.trans("Init", "Idle", "1")
    for w in SKILL_WAIT:
        for k in cmds:
            b.trans(w, f"Chk{k.capitalize()}", f"CMD_{k}")
    for w in READY:
        b.trans(w, "GoParent", "START")
    b.trans("Aborted", "StartRefused", "START")
    b.trans("StartRefused", "Aborted", "1")
    for w in ["Running"]:
        b.trans(w, "Succeed", "EXEC_DONE")
        b.trans(w, "Fail", "EXEC_FAILED")
        b.trans(w, "Halt", "HALT")
        b.trans(w, "Halt", f"MOD_CHG[ModState = {STATES['Stopping']}]")
    b.trans("Stopping", "RunStop", "EXEC_DONE")
    b.trans("Stopping", "RunStop", "EXEC_FAILED")
    b.trans("StopProc", "Interrupted", "STOP_DONE")
    for w in [x for x in SKILL_WAIT if x != "Aborted"]:
        b.trans(w, "AbortChk", "ABORT")
        # Aborting is followed at once by Aborted, and a subscriber may see only the latter (a
        # local channel keeps the latest value): both mean abort.
        b.trans(w, "AbortChk", f"MOD_CHG[(ModState = {STATES['Aborting']}) OR (ModState = {STATES['Aborted']})]")
    # Likewise Clearing is followed at once by Stopped.
    b.trans("Aborted", "ResetOk", f"MOD_CHG[(ModState = {STATES['Clearing']}) OR (ModState = {STATES['Stopped']})]")
    b.trans("Aborted", "ResetOk", "RESET")
    b.trans("ResetOk", "Idle", "1")
    b.trans("GoUa", "Running", "1")
    b.trans("GoParent", "Running", "1")
    b.trans("Halt", "Stopping", "1")
    b.trans("RunStop", "StopProc", "1")
    b.trans("Succeed", "Succeeded", "1")
    b.trans("Fail", "Failed", "1")
    b.trans("Interrupted", "Failed", "1")
    b.trans("AbortChk", "AbortActive", "Active")
    b.trans("AbortChk", "AbortIdle", "1")
    b.trans("AbortActive", "Aborted", "1")
    b.trans("AbortIdle", "Aborted", "1")
    for chk, target in [("ChkStart", "GoUa"), ("ChkStop", "Halt"), ("ChkAbort", "AbortChk"), ("ChkReset", "ResetOk")]:
        b.trans(chk, target, "Accepted")
        for w, (_, here) in SKILL_WAIT.items():
            b.trans(chk, w, f"Here = {here}")
    b.write()

    Simple(p, LIB, "SKILL_FailMerge", "Merges two failure events with their error codes into one",
           {"FAIL_A": ["ErrA"], "FAIL_B": ["ErrB"]}, {"FAIL": ["Err"]},
           {"ErrA": "UINT", "ErrB": "UINT"}, {"Err": "UINT"},
           {"FAIL_A": ("Err := ErrA;", "FAIL"), "FAIL_B": ("Err := ErrB;", "FAIL")}, folder="Skills").write()
    Simple(p, LIB, "SKILL_Release", "Releases the equipment a module level skill holds after a failure or abort: "
           "(Token, safe command 0, release) for the equipment command channels",
           {"REQ": ["Token"]}, {"CNF": ["Holder", "Command", "Arg", "Release"]},
           {"Token": "WSTRING"}, {"Holder": "WSTRING", "Command": "USINT", "Arg": "LREAL", "Release": "BOOL"},
           {"REQ": ("Holder := Token;\nCommand := 0;\nArg := 0.0;\nRelease := TRUE;", "CNF")},
           folder="Skills").write()


def make_library(p: Project):
    """Write every module-independent type."""
    make_io(p)
    make_view(p, "Owner", "owner", "Owner", "WSTRING", "occupation owner")
    make_view(p, "State", "state", "State", "USINT", "PackML state")
    make_occupation(p)
    make_state_manager(p)
    make_skill_control(p)
