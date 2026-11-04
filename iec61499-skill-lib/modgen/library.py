"""Module-independent types (package ``modlib``): IO primitives, occupation, module state manager and
the skill state machine shared by every skill primitive and module level skill.

Device-local channels (FORTE's ``loc[...]`` layer) connect the blocks without wiring, so skills
added online need no connections to the module level or the equipment:

``<Module>/owner`` (+ ``/query``)  occupation owner (WSTRING)
``<Module>/state`` (+ ``/query``)  module PackML state (USINT)
``<Module>/activity``              +1 when a skill starts running, -1 when it ends (INT)
``<Module>/<Equipment>/cmd``       (Holder, Release, output values...) to the equipment
``<Module>/<Equipment>/release``   (Holder): all outputs off and the equipment free again
``<Module>/<Equipment>/state``     (inputs..., Holder) from the equipment
"""
from __future__ import annotations

from .fbxml import STD, Adapter, Basic, Composite, Project, Simple

LIB = "modlib"
# Error codes returned by OPC UA methods and skills.
ERRORS = {"PreconditionViolated": 1, "InvariantViolated": 2, "Timeout": 3, "NotReady": 4,
          "NotPermitted": 5, "Busy": 6, "Interrupted": 7, "OutOfRange": 8}
# Module PackML states (ISA-TR88 numbering) used by the module state manager.
STATES = {"Clearing": 1, "Stopped": 2, "Starting": 3, "Idle": 4, "Execute": 6, "Stopping": 7, "Aborting": 8,
          "Aborted": 9, "Resetting": 15}
# Skill states (every skill primitive and module level skill).
SKILL_STATES = {"Idle": 0, "Running": 1, "Stopping": 2, "Succeeded": 3, "Failed": 4, "Aborted": 5}


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

# The address of an IO point says where it is, in the notation of FORTE's own IDs:
#   gpio[<chip>:<line>]       a Raspberry Pi's GPIO line, set up by the IO block itself (a GPIOChip
#                             inside it); flags after the line: :pull_up or :pull_down, :active_low
#   pwm[<chip>:<channel>:<period ns>]   a PWM channel, set up likewise (a PWMChip); a fourth field
#                             is the sysfs folder when it is not /sys/class/pwm
#   modbus[...]               a Modbus CLIENT's ID
#   sim                       simulated
#   any other name            a local IO handle set up elsewhere, as IX and QX take it in PARAMS
# Empty: not connected, the point reports QO = FALSE. Where FORTE has no GPIO (Windows), GPIOChip
# and PWMChip are stand-ins (runtime/forte-patches/0003) and a gpio or pwm point reports QO = FALSE.
ADDRESSING = ("Address: 'gpio[chip:line(:pull_up|:pull_down)(:active_low)]' or 'pwm[chip:channel:period_ns]' a "
              "Raspberry Pi's line, set up here; 'modbus[...]' a Modbus CLIENT ID; 'sim' simulated; another name "
              "a local IO handle set up elsewhere (IX/QX PARAMS); empty: not connected (QO = FALSE)")
# GPIOChip's bias numbering in FORTE 3.3.0 (its interface comment says otherwise).
BIAS = {"none": 0, "pull_up": 2, "pull_down": 3}


TEMP = """VAR_TEMP
  Field : STRING;
  Length : INT;
  Cut : INT;
  Pos : INT;
  Digit : INT;
  Number : UDINT;
END_VAR
"""


def take(target: str, convert: str) -> str:
    """ST: the number at the front of Field (up to ':' or ']') into ``target``, and Field after it.
    FORTE 3.3 has no STRING_TO_UINT: the digits are found one by one. FIND and LEN give ANY_INT,
    which the IDE only lets into arithmetic through a variable of a type."""
    return f"""  Cut := FIND(Field, ':');
  IF Cut = 0 THEN
    Cut := FIND(Field, ']');
  END_IF;
  Number := 0;
  FOR Digit := 1 TO Cut - 1 DO
    Pos := FIND('0123456789', MID(Field, 1, Digit));
    Number := Number * 10 + INT_TO_UDINT(Pos - 1);
  END_FOR;
  {target} := {convert}(Number);
  Length := LEN(Field);
  Field := MID(Field, Length - Cut, Cut + 1);
"""


def route(kind: str) -> str:
    """ST of IO_Route<kind>'s INIT: the backend and, for a line set up here, its settings."""
    lines = ""
    if kind in ("DI", "DO"):
        lines = ("""ELSIF LEFT(Address, 5) = 'gpio[' THEN
  Backend := 1;
  IoName := Address;
  LineQI := TRUE;
  LineName := STRING_TO_WSTRING(Address);
  Length := LEN(Address);
  Field := MID(Address, Length - 5, 6);
""" + take("ChipNo", "UDINT_TO_UINT") + take("LineNo", "UDINT_TO_UINT") + f"""  IF FIND(Address, ':pull_up') > 0 THEN
    LineBias := {BIAS['pull_up']};
  ELSIF FIND(Address, ':pull_down') > 0 THEN
    LineBias := {BIAS['pull_down']};
  ELSE
    LineBias := {BIAS['none']};
  END_IF;
  LineLow := FIND(Address, ':active_low') > 0;
""")
    elif kind == "AO":
        lines = ("""ELSIF LEFT(Address, 4) = 'pwm[' THEN
  Backend := 1;
  IoName := Address;
  LineQI := TRUE;
  LineName := STRING_TO_WSTRING(Address);
  Length := LEN(Address);
  Field := MID(Address, Length - 4, 5);
""" + take("ChipNo", "UDINT_TO_UINT") + take("LineNo", "UDINT_TO_UINT") + take("Period", "") + """  Length := LEN(Field);
  IF Length > 0 THEN
    Root := STRING_TO_WSTRING(LEFT(Field, Length - 1));
  END_IF;
""")
    reset = "LineQI := FALSE;\n" if lines else ""
    return (TEMP if lines else "") + f"""Backend := 3;
{reset}IF Address = 'sim' THEN
  Backend := 0;
ELSIF LEFT(Address, 7) = 'modbus[' THEN
  Backend := 2;
  ModbusId := STRING_TO_WSTRING(Address);
{lines}ELSIF LEN(Address) > 0 THEN
  Backend := 1;
  IoName := Address;
END_IF;
GQI := Backend = 1;
MQI := Backend = 2;"""


def make_io(p: Project):
    """IO_DO, IO_DI, IO_AI, IO_AO: one IO point, reached where its address says (``ADDRESSING``)."""
    for kind in ["DO", "DI", "AI", "AO"]:
        output = kind in ("DO", "AO")
        vtype = {"DO": "BOOL", "DI": "BOOL", "AI": "LREAL", "AO": "LREAL"}[kind]
        raw = {"DO": "BOOL", "DI": "BOOL", "AI": "WORD", "AO": "WORD"}[kind]
        ei = {"INIT": ["Address"], "IO_READY": ["QO_G", "QO_M"], "CNF_G": ["QO_G"], "CNF_M": ["QO_M"]}
        iv = {"Address": "STRING", "QO_G": "BOOL", "QO_M": "BOOL"}
        eo = {"INIT_IO": ["GQI", "MQI", "IoName", "ModbusId"], "INITO": ["QO"], "REQ_G": [], "REQ_M": [], "CNF": ["QO"]}
        ov = {"GQI": "BOOL", "MQI": "BOOL", "IoName": "STRING", "ModbusId": "WSTRING", "QO": "BOOL"}
        internal = {"Backend": "USINT"}            # 0 simulated, 1 local IO handle, 2 Modbus, 3 not connected
        line = {"DI": STD["GPIOChip"], "DO": STD["GPIOChip"], "AO": STD["PWMChip"]}.get(kind)
        if line:                                   # the line or channel the block sets up itself
            settings = {"LineQI": "BOOL", "LineName": "WSTRING", "ChipNo": "UINT", "LineNo": "UINT"}
            settings.update({"Period": "UDINT", "Root": "WSTRING"} if kind == "AO" else {"LineBias": "UINT", "LineLow": "BOOL"})
            eo["INIT_IO"] += list(settings)
            ov.update(settings)
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
        if kind == "AO":
            internal["Raw"] = "LREAL"
        b = Basic(p, LIB, f"IO_Route{kind}", f"Backend router for IO_{kind}; {ADDRESSING}",
                  ei, eo, iv, ov, internal, folder="IO/Base")
        b.state("START")
        b.state("Init", route(kind), "INIT_IO")
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
            b.state("None", "QO := FALSE;", "CNF")
            b.trans("START", "Req", "REQ")
            b.trans("Req", "ReqG", "Backend = 1")
            b.trans("Req", "ReqM", "Backend = 2")
            b.trans("Req", "None", "Backend = 3")
            b.trans("Req", "Sim", "1")
            b.state("DoneG", "QO := QO_G;", "CNF")
            b.state("DoneM", "QO := QO_M;")
        else:
            b.state("ReqM", None, "REQ_M")
            conv = "UINT_TO_LREAL(WORD_TO_UINT({0})) * Scale" if kind == "AI" else "{0}"
            b.state("Sim", "QO := TRUE;\nIN := SimValue;", "CNF")
            b.state("None", "QO := FALSE;", "CNF")
            b.trans("START", "ReqG", "REQ[Backend = 1]")
            b.trans("START", "ReqM", "REQ[Backend = 2]")
            b.trans("START", "None", "REQ[Backend = 3]")
            b.trans("START", "Sim", "REQ")
            b.state("DoneG", f"QO := QO_G;\nIN := {conv.format('IN_G')};", "CNF")
            b.state("DoneM", f"QO := QO_M;\nIN := {conv.format('IN_M')};", "CNF")
        b.trans("START", "DoneG", "CNF_G")
        b.trans("START", "DoneM", "CNF_M")
        for s in ["ReqG", "ReqM", "Sim", "None", "DoneG", "DoneM"]:
            b.trans(s, "START", "1")
        b.write()

        local = {"DO": STD["QX"], "DI": STD["IX"], "AI": STD["IW"], "AO": STD["QW"]}[kind]
        client = STD["CLIENT_1_0"] if output else STD["CLIENT_0_1"]
        iv = {"Address": "STRING"}
        ev_in = {"INIT": (["Address"], "EInit")}
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
        c = Composite(p, LIB, f"IO_{kind}", f"{label}; {ADDRESSING.replace('IX/QX', local.split('::')[-1])}",
                      ev_in, ev_out, iv, ov, folder="IO")
        c.spacing = 6000                          # GPIOChip and PWMChip are wide blocks
        c.fb("Route", q(f"IO_Route{kind}"))
        if line:
            c.fb("Line", line, **({} if kind == "AO" else {"ReadWriteMode": "1" if output else "0"}))
        c.fb("Local", local)
        c.fb("Bus", client)
        c.ev("INIT", "Route.INIT")
        if line:                                   # the line exists before the IX/QX binds to it
            c.ev("Route.INIT_IO", "Line.INIT")
            c.ev("Line.INITO", "Local.INIT")
            pins = {"LineQI": "QI", "LineName": "VALUE", "ChipNo": "ChipNumber"}
            pins.update({"LineNo": "Channel", "Period": "PeriodNs", "Root": "SysfsRoot"} if kind == "AO"
                        else {"LineNo": "LineNumber", "LineBias": "BiasMode", "LineLow": "ActiveLow"})
            for setting, pin in pins.items():
                c.da(f"Route.{setting}", f"Line.{pin}")
        else:
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
        c.da("Address", "Route.Address")
        c.da("Route.IoName", "Local.PARAMS")
        c.da("Route.ModbusId", "Bus.ID")
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
              {"OCCUPY_REQ": ["OccupySession"], "RELEASE_REQ": ["ReleaseSession"], "QUERY_REQ": []},
              {"OCCUPY_RSP": ["Accepted", "ErrorID"], "RELEASE_RSP": ["Accepted", "ErrorID"],
               "CHG": ["Owner", "Occupied"]},
              {"OccupySession": "WSTRING", "ReleaseSession": "WSTRING"},
              {"Accepted": "BOOL", "ErrorID": "UINT", "Owner": "WSTRING", "Occupied": "BOOL"}, folder="Module/Base")
    b.state("START")
    b.state("Occupy", 'IF (OccupySession <> "") AND ((Owner = "") OR (Owner = OccupySession)) THEN\n'
                      "  Owner := OccupySession;\n  Occupied := TRUE;\n  Accepted := TRUE;\n  ErrorID := 0;\n"
                      f"ELSE\n  Accepted := FALSE;\n  ErrorID := {e};\nEND_IF;", "OCCUPY_RSP", ["CHG"])
    b.state("Release", 'IF (Owner <> "") AND (Owner = ReleaseSession) THEN\n'
                       '  Owner := "";\n  Occupied := FALSE;\n  Accepted := TRUE;\n  ErrorID := 0;\n'
                       f"ELSE\n  Accepted := FALSE;\n  ErrorID := {e};\nEND_IF;", "RELEASE_RSP", ["CHG"])
    b.state("Query", None, "CHG")
    for s, ev in [("Occupy", "OCCUPY_REQ"), ("Release", "RELEASE_REQ"), ("Query", "QUERY_REQ")]:
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
        c.ev(f"{m}.IND", f"Logic.{m.upper()}_REQ")
        c.da(f"{m}.RD_1", f"Logic.{m}Session")
        c.ev(f"Logic.{m.upper()}_RSP", f"{m}.RSP")
        c.da("Logic.Accepted", f"{m}.SD_1")
        c.da("Logic.ErrorID", f"{m}.SD_2")
    c.ev("SubQuery.IND", "Logic.QUERY_REQ")
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
# Wait states: name -> the PackML state they publish (a command is decided on it, in MOD_StateGate).
MODULE_WAIT = {"Stopped": "Stopped", "ResettingW": "Resetting", "Idle": "Idle", "Execute": "Execute",
               "StoppingW": "Stopping", "StopProcW": "Stopping", "Aborted": "Aborted"}


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

    # The gate: who may command the module, and in which state (decided on the state Logic publishes).
    gate_ei = {f"{m.upper()}_REQ": [f"{m}Session"] for m in MODULE_COMMANDS}
    gate_ei.update({"OWNER_CHG": ["Owner"], "STATE_CHG": ["State"]})
    gate_eo = {f"{m.upper()}_RSP": ["Accepted", "ErrorID"] for m in MODULE_COMMANDS}
    gate_eo.update({f"GO_{m.upper()}": [] for m in MODULE_COMMANDS})
    g = Basic(p, LIB, "MOD_StateGate",
              "Decides the module commands Reset/Start/Stop/Abort/Clear: only from the occupation owner (5 "
              "NotPermitted) and only in a state PackML allows them in (4 NotReady); passes an accepted one on "
              "to MOD_StateLogic", gate_ei, gate_eo,
              {**{f"{m}Session": "WSTRING" for m in MODULE_COMMANDS}, "Owner": "WSTRING",
               "State": ("USINT", str(STATES["Stopped"]))},
              {"Accepted": "BOOL", "ErrorID": "UINT"}, {"Owned": "BOOL"}, folder="Module/Base")
    g.state("Wait")
    for m, (valid, _) in MODULE_COMMANDS.items():
        states = sorted({STATES[MODULE_WAIT[v]] for v in valid})
        allowed = " OR ".join(f"(State = {n})" for n in states)
        g.state("Chk" + m, f'Owned := ({m}Session = Owner) AND (Owner <> "");\n'
                           f"Accepted := Owned AND ({allowed});\n"
                           f"IF NOT Owned THEN\n  ErrorID := {ERRORS['NotPermitted']};\n"
                           f"ELSIF NOT Accepted THEN\n  ErrorID := {ERRORS['NotReady']};\nELSE\n  ErrorID := 0;\nEND_IF;",
                f"{m.upper()}_RSP")
        g.state("Go" + m, None, f"GO_{m.upper()}")
    for m in MODULE_COMMANDS:
        g.trans("Wait", "Chk" + m, f"{m.upper()}_REQ")
        g.trans("Chk" + m, "Go" + m, "Accepted")
        g.trans("Chk" + m, "Wait", "1")
        g.trans("Go" + m, "Wait", "1")
    g.write()

    ei = {m.upper(): [] for m in MODULE_COMMANDS}
    ei.update({"ACT": ["AllIdle"], "RESETTING_DONE": [], "RESETTING_FAILED": [], "STOPPING_DONE": [],
               "STOPPING_FAILED": [], "STOP_TIMEOUT": []})
    eo = {"CNF": ["State"], "RUN_RESETTING": [], "RUN_STOPPING": [], "WD_START": [], "WD_STOP": []}
    b = Basic(p, LIB, "MOD_StateLogic",
              "PackML module state machine: RESET, START, STOP, ABORT, CLEAR (decided by MOD_StateGate); runs the "
              "Resetting and Stopping procedures; Stopping waits until no skill is active",
              ei, eo, {"AllIdle": ("BOOL", "TRUE")}, {"State": ("USINT", str(STATES["Stopped"]))},
              folder="Module/Base")
    s = STATES
    b.state("Stopped", f"State := {s['Stopped']};", "CNF")   # initial state
    b.state("Resetting", f"State := {s['Resetting']};", "CNF", ["RUN_RESETTING"])
    b.state("ResettingW")
    b.state("Idle", f"State := {s['Idle']};", "CNF")
    b.state("Starting", f"State := {s['Starting']};", "CNF")
    b.state("Execute", f"State := {s['Execute']};", "CNF")
    b.state("Stopping", f"State := {s['Stopping']};", "CNF", ["WD_START"])
    b.state("StoppingW")
    b.state("StopProc", None, "WD_STOP", ["RUN_STOPPING"])
    b.state("StopProcW")
    b.state("Aborting", f"State := {s['Aborting']};", "CNF", ["WD_STOP"])
    b.state("Aborted", f"State := {s['Aborted']};", "CNF")
    b.state("Clearing", f"State := {s['Clearing']};", "CNF")
    for m, (valid, target) in MODULE_COMMANDS.items():
        for w in valid:
            b.trans(w, target, m.upper())
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
    c.fb("Gate", q("MOD_StateGate"))
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
    c.ev("Owner.CHG", "Gate.OWNER_CHG")
    c.da("Owner.Owner", "Gate.Owner")
    for m in servers:
        c.da(f"Ids.Id{m}", f"{m}.ID")
        c.ev(f"{m}.IND", f"Gate.{m.upper()}_REQ")
        c.da(f"{m}.RD_1", f"Gate.{m}Session")
        c.ev(f"Gate.{m.upper()}_RSP", f"{m}.RSP")
        c.da("Gate.Accepted", f"{m}.SD_1")
        c.da("Gate.ErrorID", f"{m}.SD_2")
        c.ev(f"Gate.GO_{m.upper()}", f"Logic.{m.upper()}")
    c.da("Ids.IdPub", "PubUa.ID")
    c.da("Ids.IdState", "PubState.ID")
    c.da("Ids.IdQuery", "SubQuery.ID")
    c.da("Ids.IdAct", "SubAct.ID")
    c.ev("Logic.CNF", "PubUa.REQ", "PubState.REQ", "Gate.STATE_CHG")
    c.ev("SubQuery.IND", "PubState.REQ")
    c.da("Logic.State", "PubUa.SD_1", "PubState.SD_1", "Gate.State")
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

# Wait states of SKILL_Control: name -> the skill state it publishes.
SKILL_WAIT = {"Idle": "Idle", "Running": "Running", "Stopping": "Stopping", "StopProc": "Stopping",
              "Succeeded": "Succeeded", "Failed": "Failed", "Aborted": "Aborted"}
READY = ["Idle", "Succeeded", "Failed"]
# How long a skill shows Succeeded before it returns to Idle by itself.
SUCCEEDED_FOR = "T#1500ms"


def make_skill_gate(p: Project):
    """SKILL_Gate: in front of SKILL_Control, decides a client's command and passes on the parent's.

    A call of Start, Stop, Abort or Reset over OPC UA is answered at once with [Accepted,
    ResponseError]: only the module's owner may call (5 NotPermitted); Start only with the module in
    Execute (4 NotReady), the skill neither running (6 Busy) nor aborted (4), its parameters in range
    (8 OutOfRange) and its equipment free (6); Stop only while it runs, Abort unless it is aborted, Reset
    only when it is (4). An accepted call goes on as the same command a parent gives (GO_START with
    ByClient, GO_HALT, GO_ABORT, GO_RESET); a parent's command goes on unchecked. The module commands
    the skill too: its Aborting or Aborted aborts it, its Stopping halts a skill a client started, and its
    Clearing or Stopped resets an aborted one. The skill state it decides on is the one SKILL_Control
    publishes (SKILL_CHG).
    """
    e, s = ERRORS, SKILL_STATES
    reqs = {"START": ["Session", "ParamsInRange", "EquipmentFree"], "STOP": ["StopSession"],
            "ABORT": ["AbortSession"], "RESET": ["ResetSession"]}
    ei = {**{f"{k}_REQ": v for k, v in reqs.items()}, "OWNER_CHG": ["Owner"], "MOD_CHG": ["ModuleState"],
          "SKILL_CHG": ["State"], "START": [], "HALT": [], "ABORT": [], "RESET": []}
    eo = {**{f"{k}_RSP": ["Accepted", "ResponseError"] for k in reqs}, "GO_START": ["ByClient"], "GO_HALT": [],
          "GO_ABORT": [], "GO_RESET": []}
    iv = {"Session": "WSTRING", "ParamsInRange": "BOOL", "EquipmentFree": "BOOL", "StopSession": "WSTRING",
          "AbortSession": "WSTRING", "ResetSession": "WSTRING", "Owner": "WSTRING", "ModuleState": "USINT",
          "State": "USINT"}
    ov = {"Accepted": "BOOL", "ResponseError": "UINT", "ByClient": "BOOL"}
    b = Basic(p, LIB, "SKILL_Gate",
              "Decides a client's Start/Stop/Abort/Reset (owner only; Start only in module Execute, not running, "
              "parameters in range, equipment free) and passes accepted ones and a parent's on as GO_START, "
              "GO_HALT, GO_ABORT, GO_RESET to SKILL_Control", ei, eo, iv, ov, {"Owned": "BOOL"}, folder="Skills/Base")
    owned = 'Owned := ({0} = Owner) AND (Owner <> "");\n'
    running, stopping, aborted = s["Running"], s["Stopping"], s["Aborted"]
    b.state("Wait")
    b.state("ChkStart", owned.format("Session") + "Accepted := FALSE;\n"
            f"IF NOT Owned THEN\n  ResponseError := {e['NotPermitted']};\n"
            f"ELSIF ModuleState <> {STATES['Execute']} THEN\n  ResponseError := {e['NotReady']};\n"
            f"ELSIF (State = {running}) OR (State = {stopping}) THEN\n  ResponseError := {e['Busy']};\n"
            f"ELSIF State = {aborted} THEN\n  ResponseError := {e['NotReady']};\n"
            f"ELSIF NOT ParamsInRange THEN\n  ResponseError := {e['OutOfRange']};\n"
            f"ELSIF NOT EquipmentFree THEN\n  ResponseError := {e['Busy']};\n"
            "ELSE\n  Accepted := TRUE;\n  ResponseError := 0;\nEND_IF;", "START_RSP")
    valid = {"Stop": f"State = {running}", "Abort": f"State <> {aborted}", "Reset": f"State = {aborted}"}
    session = {"Stop": "StopSession", "Abort": "AbortSession", "Reset": "ResetSession"}
    for m, ok in valid.items():
        b.state("Chk" + m, owned.format(session[m]) + f"Accepted := Owned AND ({ok});\n"
                f"IF NOT Owned THEN\n  ResponseError := {e['NotPermitted']};\n"
                f"ELSIF NOT Accepted THEN\n  ResponseError := {e['NotReady']};\nELSE\n  ResponseError := 0;\nEND_IF;",
                f"{m.upper()}_RSP")
    b.state("ClientStart", "ByClient := TRUE;", "GO_START")
    b.state("ParentStart", "ByClient := FALSE;", "GO_START")
    for cmd in ("Halt", "Abort", "Reset"):
        b.state(f"Go{cmd}", None, f"GO_{cmd.upper()}")
    for m in ("Start", "Stop", "Abort", "Reset"):
        b.trans("Wait", f"Chk{m}", f"{m.upper()}_REQ")
    b.trans("Wait", "ParentStart", "START")
    for cmd in ("Halt", "Abort", "Reset"):
        b.trans("Wait", f"Go{cmd}", cmd.upper())
    # What the module's state means for the skill. Aborting is followed at once by Aborted, and Clearing
    # by Stopped, and a subscriber may see only the latter (a local channel keeps the latest value).
    b.trans("Wait", "GoAbort", f"MOD_CHG[((ModuleState = {STATES['Aborting']}) OR (ModuleState = {STATES['Aborted']}))"
            f" AND (State <> {aborted})]")
    # Only a skill the occupant started stops itself when the module stops. One started by a parent
    # is halted by it; a step of the Stopping procedure must run exactly then.
    b.trans("Wait", "GoHalt", f"MOD_CHG[(ModuleState = {STATES['Stopping']}) AND (State = {running}) AND ByClient]")
    b.trans("Wait", "GoReset", f"MOD_CHG[((ModuleState = {STATES['Clearing']}) OR (ModuleState = {STATES['Stopped']}))"
            f" AND (State = {aborted})]")
    for chk, go in [("ChkStart", "ClientStart"), ("ChkStop", "GoHalt"), ("ChkAbort", "GoAbort"), ("ChkReset", "GoReset")]:
        b.trans(chk, go, "Accepted")
        b.trans(chk, "Wait", "1")
    for go in ("ClientStart", "ParentStart", "GoHalt", "GoAbort", "GoReset"):
        b.trans(go, "Wait", "1")
    b.write()


def make_skill_control(p: Project):
    """SKILL_Control: the state machine every skill shares (primitive or module level skill).

    Idle/Succeeded/Failed -START-> Running -> Succeeded | Failed(ErrorID); Succeeded returns to Idle
    by itself after SUCCEEDED_FOR (TO_IDLE_START -> TO_IDLE). HALT -> Stopping: the execution is
    halted, then the stop procedure runs (RUN_STOPPING -> STOPPING_DONE) -> Failed(Interrupted).
    ABORT -> Aborted (outputs off at once); RESET -> Idle (RESET_SEQ passes it on to children). Who
    commands it (a client, the parent, the module's state) is decided in front of it, in SKILL_Gate:
    here a command is the same whoever gives it. Every start and end is counted on the module's
    activity channel (ACT +1/-1).
    """
    e, s = ERRORS, SKILL_STATES
    ei = {"INIT": (["Module", "UaRoot", "UaPath"], "EInit"), "START": ["ByClient"], "HALT": [], "ABORT": [],
          "RESET": [], "EXECUTE_DONE": [], "EXECUTE_FAILED": ["ExecuteError"],
          "STOPPING_DONE": [], "TO_IDLE": []}
    eo = {"INITO": (["StartMethodId", "StopMethodId", "AbortMethodId", "ResetMethodId", "StateId", "ActivityId",
                     "ReleaseId"], "EInit"),
          "PUB": ["State", "ErrorID"], "RUN": ["CalledByClient"], "HALT_SEQ": [], "ABORT_SEQ": [], "RESET_SEQ": [],
          "RUN_STOPPING": [], "SUCCESS": [], "FAILURE": ["ErrorID"], "RELEASE": [], "ACT": ["ActivityDelta"],
          "TO_IDLE_START": [], "TO_IDLE_STOP": []}
    iv = {"Module": "WSTRING", "UaRoot": "WSTRING", "UaPath": "WSTRING", "ByClient": "BOOL", "ExecuteError": "UINT"}
    ov = {"StartMethodId": "WSTRING", "StopMethodId": "WSTRING", "AbortMethodId": "WSTRING", "ResetMethodId": "WSTRING",
          "StateId": "WSTRING", "ActivityId": "WSTRING", "ReleaseId": "WSTRING", "State": "USINT", "ErrorID": "UINT",
          "ActivityDelta": "INT", "CalledByClient": "BOOL"}
    b = Basic(p, LIB, "SKILL_Control",
              "Skill state machine: START, HALT, ABORT, RESET (a client's already decided by SKILL_Gate); Idle 0, "
              "Running 1, Stopping 2, Succeeded 3, Failed 4, Aborted 5; RUN starts the execution (CalledByClient: "
              "with the Start arguments, else with the parent's values)",
              ei, eo, iv, ov, {"Active": "BOOL"}, folder="Skills/Base")
    base = cat("UaRoot", "UaPath")
    b.state("START")
    b.state("Init", "\n".join([f"StartMethodId := {ua('CREATE_METHOD', base, lit('/Start'))};",
                               f"StopMethodId := {ua('CREATE_METHOD', base, lit('/Stop'))};",
                               f"AbortMethodId := {ua('CREATE_METHOD', base, lit('/Abort'))};",
                               f"ResetMethodId := {ua('CREATE_METHOD', base, lit('/Reset'))};",
                               f"StateId := {ua('WRITE', base, lit('/State;'), base, lit('/ErrorID'))};",
                               f"ActivityId := {loc('Module', 'activity')};",
                               f"ReleaseId := {loc('Module', 'release')};"]), "INITO")
    for w, state in SKILL_WAIT.items():
        b.state(w, f"State := {s[state]};", "PUB", ["TO_IDLE_START"] if w == "Succeeded" else ())
    # Entry actions; a start stops the timer of a Succeeded it leaves.
    b.state("Go", "Active := TRUE;\nActivityDelta := 1;\nErrorID := 0;\nCalledByClient := ByClient;", "ACT",
            ["TO_IDLE_STOP", "RUN"])
    b.state("Halt", None, "HALT_SEQ")
    b.state("RunStop", None, "RUN_STOPPING")
    # Every end of a run is announced (RELEASE): a module level skill then gives up all it holds.
    b.state("Succeed", "Active := FALSE;\nActivityDelta := -1;\nErrorID := 0;", "ACT", ["RELEASE", "SUCCESS"])
    b.state("Fail", "Active := FALSE;\nActivityDelta := -1;\nErrorID := ExecuteError;", "ACT", ["RELEASE", "FAILURE"])
    b.state("Interrupted", f"Active := FALSE;\nActivityDelta := -1;\nErrorID := {e['Interrupted']};", "ACT",
            ["RELEASE", "FAILURE"])
    b.state("AbortChk")
    b.state("AbortActive", f"Active := FALSE;\nActivityDelta := -1;\nErrorID := {e['Interrupted']};", "ABORT_SEQ",
            ["ACT", "RELEASE"])
    b.state("AbortIdle", None, "ABORT_SEQ")
    b.state("StartRefused", f"ErrorID := {e['NotReady']};", "FAILURE")
    b.state("ResetOk", None, "RESET_SEQ")
    b.trans("START", "Init", "INIT")
    b.trans("Init", "Idle", "1")
    for w in READY:
        b.trans(w, "Go", "START")
    b.trans("Aborted", "StartRefused", "START")
    b.trans("StartRefused", "Aborted", "1")
    b.trans("Running", "Succeed", "EXECUTE_DONE")
    b.trans("Running", "Fail", "EXECUTE_FAILED")
    b.trans("Running", "Halt", "HALT")
    b.trans("Stopping", "RunStop", "EXECUTE_DONE")
    b.trans("Stopping", "RunStop", "EXECUTE_FAILED")
    b.trans("StopProc", "Interrupted", "STOPPING_DONE")
    for w in [x for x in SKILL_WAIT if x != "Aborted"]:
        b.trans(w, "AbortChk", "ABORT")
    b.trans("Aborted", "ResetOk", "RESET")
    b.trans("ResetOk", "Idle", "1")
    b.trans("Go", "Running", "1")
    b.trans("Halt", "Stopping", "1")
    b.trans("RunStop", "StopProc", "1")
    b.trans("Succeed", "Succeeded", "1")
    b.trans("Succeeded", "Idle", "TO_IDLE")
    b.trans("Fail", "Failed", "1")
    b.trans("Interrupted", "Failed", "1")
    b.trans("AbortChk", "AbortActive", "Active")
    b.trans("AbortChk", "AbortIdle", "1")
    b.trans("AbortActive", "Aborted", "1")
    b.trans("AbortIdle", "Aborted", "1")
    b.write()


    Simple(p, LIB, "SKILL_FailMerge", "Merges two failure events with their error codes into one",
           {"FAIL_1": ["Error1"], "FAIL_2": ["Error2"]}, {"FAIL": ["Error"]},
           {"Error1": "UINT", "Error2": "UINT"}, {"Error": "UINT"},
           {"FAIL_1": ("Error := Error1;", "FAIL"), "FAIL_2": ("Error := Error2;", "FAIL")}, folder="Skills").write()


def make_skill_core(p: Project):
    """SKILL_Core: what every skill has regardless of its parameters (primitive or module level skill).

    SKILL_Control with the OPC UA methods Stop, Abort and Reset, the published State and ErrorID,
    the module's owner and state, and the activity count. The Start method takes the skill's
    parameters, so it stays outside (a generic SERVER_2_n): its ID is StartMethodId, its call goes to
    START_REQ with the range check (ParamsInRange) and the equipment check (EquipmentFree), and
    START_RSP answers it. At every end of a run it publishes Holder on the module's release channel
    when ReleaseAll is set (a module level skill: everything it holds is given up).
    """
    iv = {"Module": "WSTRING", "UaRoot": "WSTRING", "UaPath": "WSTRING", "UaEnable": "BOOL", "Methods": "BOOL",
          "Holder": "WSTRING", "ReleaseAll": ("BOOL", "FALSE"),
          "Session": "WSTRING", "ParamsInRange": ("BOOL", "TRUE"), "EquipmentFree": ("BOOL", "TRUE"), "ExecuteError": "UINT"}
    c = Composite(p, LIB, "SKILL_Core",
                  "Skill core: state machine, OPC UA Stop/Abort/Reset(Session) -> [Accepted, ErrorID], State and ErrorID "
                  "published, activity counted; the Start method (with the skill's parameters) is wired to START_REQ "
                  "and START_RSP; RUN starts the execution, SUCCESS or FAILURE(ErrorID) ends it",
                  {"INIT": (["Module", "UaRoot", "UaPath", "UaEnable", "Methods", "Holder", "ReleaseAll"], "EInit"),
                   "START_REQ": ["Session", "ParamsInRange", "EquipmentFree"], "START": [], "HALT": [], "ABORT": [], "RESET": [],
                   "EXECUTE_DONE": [], "EXECUTE_FAILED": ["ExecuteError"], "STOPPING_DONE": []},
                  {"INITO": (["StartMethodId"], "EInit"), "START_RSP": ["Accepted", "StartError"], "RUN": ["CalledByClient"],
                   "HALT_SEQ": [], "ABORT_SEQ": [], "RESET_SEQ": [], "RUN_STOPPING": [], "SUCCESS": [], "FAILURE": ["ErrorID"]},
                  iv, {"StartMethodId": "WSTRING", "Accepted": "BOOL", "StartError": "UINT", "CalledByClient": "BOOL", "State": "USINT",
                       "ErrorID": "UINT"}, folder="Skills")
    c.fb("Gate", q("SKILL_Gate"))
    c.fb("Control", q("SKILL_Control"))
    c.fb("Owner", q("MOD_OwnerView"))
    c.fb("Mode", q("MOD_StateView"))
    # Method blocks are UaStop etc.: IEC names are case-insensitive, so "Stop" clashes with STOP.
    methods = ["Stop", "Abort", "Reset"]
    for m in methods:
        c.fb(f"Ua{m}", p.server(2, 1))
    c.fb("PubState", p.publish(2))
    c.fb("Act", p.publish(1), QI="TRUE")
    c.fb("ToIdle", STD["E_DELAY"], DT=SUCCEEDED_FOR)
    c.fb("PubRelease", p.publish(1))
    c.chain("INIT", ["Control", "Owner", "Mode", *[f"Ua{m}" for m in methods], "PubState", "Act", "PubRelease"],
            ["PubState.REQ", "INITO"])
    c.da("Module", "Control.Module", "Owner.Module", "Mode.Module")
    c.da("UaRoot", "Control.UaRoot")
    c.da("UaPath", "Control.UaPath")
    c.da("Methods", *[f"Ua{m}.QI" for m in methods])
    c.da("UaEnable", "PubState.QI")
    c.da("Control.StartMethodId", "StartMethodId")
    # The gate answers a client's call and passes on what it accepts, and a parent's command.
    c.ev("START_REQ", "Gate.START_REQ")
    for v in ["Session", "ParamsInRange", "EquipmentFree"]:
        c.da(v, f"Gate.{v}")
    c.ev("Gate.START_RSP", "START_RSP")
    c.da("Gate.Accepted", "Accepted", *[f"Ua{m}.SD_1" for m in methods])
    c.da("Gate.ResponseError", "StartError", *[f"Ua{m}.SD_2" for m in methods])
    for m in methods:
        c.da(f"Control.{m}MethodId", f"Ua{m}.ID")
        c.ev(f"Ua{m}.IND", f"Gate.{m.upper()}_REQ")
        c.da(f"Ua{m}.RD_1", f"Gate.{m}Session")
        c.ev(f"Gate.{m.upper()}_RSP", f"Ua{m}.RSP")
    c.ev("Owner.CHG", "Gate.OWNER_CHG")
    c.da("Owner.Owner", "Gate.Owner")
    c.ev("Mode.CHG", "Gate.MOD_CHG")
    c.da("Mode.State", "Gate.ModuleState")
    c.ev("Gate.GO_START", "Control.START")
    c.da("Gate.ByClient", "Control.ByClient")
    for cmd in ["HALT", "ABORT", "RESET"]:
        c.ev(f"Gate.GO_{cmd}", f"Control.{cmd}")
    c.da("Control.StateId", "PubState.ID")
    c.ev("Control.PUB", "PubState.REQ", "Gate.SKILL_CHG")
    c.da("Control.State", "PubState.SD_1", "State", "Gate.State")
    c.da("Control.ErrorID", "PubState.SD_2", "ErrorID")
    c.da("Control.ActivityId", "Act.ID")
    c.ev("Control.ACT", "Act.REQ")
    c.da("Control.ActivityDelta", "Act.SD_1")
    for ev in ["START", "HALT", "ABORT", "RESET"]:
        c.ev(ev, f"Gate.{ev}")
    for ev in ["EXECUTE_DONE", "EXECUTE_FAILED", "STOPPING_DONE"]:
        c.ev(ev, f"Control.{ev}")
    c.da("ExecuteError", "Control.ExecuteError")
    for ev in ["RUN", "HALT_SEQ", "ABORT_SEQ", "RESET_SEQ", "RUN_STOPPING", "SUCCESS", "FAILURE"]:
        c.ev(f"Control.{ev}", ev)
    c.ev("Control.TO_IDLE_START", "ToIdle.START")
    c.ev("Control.TO_IDLE_STOP", "ToIdle.STOP")
    c.ev("ToIdle.EO", "Control.TO_IDLE")
    c.da("Control.CalledByClient", "CalledByClient")
    # The end of a run of a module level skill: everything it holds is given up (all off, free).
    c.da("ReleaseAll", "PubRelease.QI")
    c.da("Control.ReleaseId", "PubRelease.ID")
    c.da("Holder", "PubRelease.SD_1")
    c.ev("Control.RELEASE", "PubRelease.REQ")
    c.group("StateMachine", "The skill's states; in front of them the gate, which decides a client's command; "
            "and when a Succeeded returns to Idle", ["Gate", "Control", "ToIdle"])
    c.group("ModuleViews", "The module's owner and state in, the activity count out", ["Owner", "Mode", "Act"])
    c.group("OpcUa", "The methods Stop, Abort and Reset, and the published State and ErrorID",
            ["UaStop", "UaAbort", "UaReset", "PubState"])
    c.group("Release", "At the end of a run of a module level skill: everything it holds given up",
            ["PubRelease"])
    c.write()


def make_skill_run(p: Project):
    """SKILL_Run: one run of any skill primitive, the same for all of them; what the skill is (its
    contract, ``SC_<Skill>``) comes in as values.

    START (with what the contract says at the start: Pre, Post, Timed, RunTime, Command, Arg,
    StopCommand): refused when Pre does not hold (1 PreconditionViolated); while another holder has the
    equipment, it waits up to 0.5 s for it to let go (else 6 Busy); succeeds at once when Post already
    holds (not for a timed skill); else sends Command with Arg and starts the timer (RunTime). Then, at
    each SAMPLE (Post and Inv on the equipment's newest state): Inv lost -> 2 InvariantViolated; another
    holder -> 6 Busy (Lost); Post -> done; the timer -> done for a timed skill, 3 Timeout for one a sensor
    ends. Every end sends StopCommand (all off for a failure or an abort), giving the equipment up with it
    when ReleaseAfter is set (always on an abort), and reports only once the command has been played
    (PLAYED). Without equipment (no port), CMD is looped back to PLAYED.
    """
    e = ERRORS
    ei = {"START": ["Holder", "ReleaseAfter", "Pre", "Post", "Timed", "RunTime", "Command", "Arg", "StopCommand"],
          "SAMPLE": ["Holder", "Post", "Inv", "EqHolder"], "HALT": [], "ABORT": [], "TIMER": [], "WAIT_OVER": [],
          "PLAYED": []}
    eo = {"DONE": [], "FAILED": ["ErrorID"], "HALTED": ["ErrorID"], "TIMER_START": ["TimerDT"], "TIMER_STOP": [],
          "WAIT_START": [], "WAIT_STOP": [], "CMD": ["C_Holder", "C_Command", "C_Arg", "C_Release"],
          "EQ_FREE": ["EquipmentFree"]}
    iv = {"Holder": "WSTRING", "ReleaseAfter": "BOOL", "Pre": "BOOL", "Post": "BOOL", "Inv": ("BOOL", "TRUE"),
          "Timed": "BOOL", "RunTime": "TIME", "Command": "USINT", "Arg": "LREAL", "StopCommand": "USINT",
          "EqHolder": "WSTRING"}
    ov = {"ErrorID": "UINT", "TimerDT": "TIME", "C_Holder": "WSTRING", "C_Command": "USINT", "C_Arg": "LREAL",
          "C_Release": "BOOL", "EquipmentFree": "BOOL"}
    b = Basic(p, LIB, "SKILL_RunLogic",
              "One run of a skill primitive: Pre, then the equipment free (0.5 s grace), Command until Post or the "
              "timer (Timed), Inv over it, StopCommand at the end, played before the end is reported",
              ei, eo, iv, ov, {"Outcome": "USINT"}, folder="Skills/Base")

    def cmd(code, release="ReleaseAfter"):
        return f"C_Holder := Holder;\nC_Command := {code};\nC_Arg := Arg;\nC_Release := {release};"

    busy = '(EqHolder <> "") AND (EqHolder <> Holder)'
    free = 'EquipmentFree := (EqHolder = "") OR (EqHolder = Holder);'
    b.state("Idle")
    b.state("Check")
    b.state("Reject", f"ErrorID := {e['PreconditionViolated']};", "FAILED")
    b.state("Sample", free, "EQ_FREE")
    b.state("Busy", f"ErrorID := {e['Busy']};", "FAILED", algorithm="Busy")
    # Another holder: wait up to 0.5 s for the equipment's next state (a release in flight, e.g. from
    # the previous step or a skill that just stopped) before failing with Busy.
    b.state("WaitFree", None, "WAIT_START")
    b.state("WaitW")
    b.state("Recheck", None, "WAIT_STOP")
    b.state("AlreadyDone", None, "DONE")
    b.state("Run", cmd("Command", "FALSE") + "\nTimerDT := RunTime;", "CMD", ["TIMER_START"])
    b.state("RunSample", free, "EQ_FREE", algorithm="Sample")
    # A final command may take time (a brake pulse): the run ends when it has been played, and Outcome
    # says how (1 done, 2 failed, 3 halted, 0 aborted: nothing to report).
    b.state("Unsafe", cmd(0) + f"\nErrorID := {e['InvariantViolated']};\nOutcome := 2;", "CMD", ["TIMER_STOP"])
    b.state("Lost", f"ErrorID := {e['Busy']};", "TIMER_STOP", ["FAILED"], algorithm="Busy")
    b.state("Done", cmd("StopCommand") + "\nOutcome := 1;", "CMD", ["TIMER_STOP"])
    b.state("TimedOut", cmd(0) + f"\nErrorID := {e['Timeout']};\nOutcome := 2;", "CMD")
    b.state("Halt", cmd("StopCommand") + f"\nErrorID := {e['Interrupted']};\nOutcome := 3;", "CMD", ["TIMER_STOP"])
    # An abort always gives the equipment up: with the module aborting, the equipment has already freed
    # itself, and a message that kept the holder would take it again for good.
    b.state("Abort", cmd(0, "TRUE") + "\nOutcome := 0;", "CMD", ["TIMER_STOP"])
    b.state("Ending")
    b.state("EndDone", None, "DONE")
    b.state("EndFailed", None, "FAILED")
    b.state("EndHalted", None, "HALTED")
    b.state("Running")
    b.trans("Idle", "Check", "START")
    b.trans("Idle", "Sample", "SAMPLE")
    b.trans("Sample", "Idle", "1")
    b.trans("Check", "Reject", "NOT Pre")
    b.trans("Check", "WaitFree", busy)
    b.trans("WaitFree", "WaitW", "1")
    b.trans("WaitW", "Recheck", f"SAMPLE[NOT ({busy})]")
    b.trans("WaitW", "Busy", "WAIT_OVER")
    b.trans("WaitW", "Idle", "HALT")
    b.trans("WaitW", "Idle", "ABORT")
    b.trans("Recheck", "Check", "1")
    b.trans("Check", "AlreadyDone", "Post AND NOT Timed")   # already there: succeed without driving
    b.trans("Check", "Run", "1")
    b.trans("Run", "Running", "1")
    b.trans("Running", "Unsafe", "SAMPLE[NOT Inv]")
    b.trans("Running", "Lost", f"SAMPLE[{busy}]")
    b.trans("Running", "Done", "SAMPLE[Post AND NOT Timed]")
    b.trans("Running", "Done", "TIMER[Timed]")
    b.trans("Running", "TimedOut", "TIMER")
    b.trans("Running", "RunSample", "SAMPLE")
    b.trans("RunSample", "Running", "1")
    b.trans("Running", "Halt", "HALT")
    b.trans("Running", "Abort", "ABORT")
    for s in ["Reject", "Busy", "Lost", "AlreadyDone"]:
        b.trans(s, "Idle", "1")
    for s in ["Unsafe", "Done", "TimedOut", "Halt", "Abort"]:
        b.trans(s, "Ending", "1")
    b.trans("Ending", "EndDone", "PLAYED[Outcome = 1]")
    b.trans("Ending", "EndFailed", "PLAYED[Outcome = 2]")
    b.trans("Ending", "EndHalted", "PLAYED[Outcome = 3]")
    b.trans("Ending", "Idle", "PLAYED")
    b.trans("Ending", "Abort", "ABORT")
    for s in ["EndDone", "EndFailed", "EndHalted"]:
        b.trans(s, "Idle", "1")
    b.write()

    # The two adapters a primitive's blocks are joined by, each one connection instead of many.
    contract = {"START": ["Pre", "Post", "Timed", "RunTime", "Command", "Arg", "StopCommand"],
                "SAMPLE": ["Post", "Inv", "EqHolder"]}
    Adapter(p, LIB, "AContract",
            "What a skill primitive's contract (SC_, the plug) tells its run (SKILL_Run, the socket): at START what "
            "to do and whether it may start, at SAMPLE whether the newest state of the equipment ends the run",
            {}, contract, {}, {v: iv[v] for vs in contract.values() for v in vs if v in iv} | {"Inv": "BOOL"},
            folder="Skills/Adapters").write()
    equipment = {"SEND": ["Holder", "Command", "Arg", "Release"]}
    Adapter(p, LIB, "AEquipment",
            "What a skill's run (SKILL_Run, the plug) sends its equipment's port (EP_, the socket): SEND a command; "
            "PLAYED comes back when all its phases are out",
            {"PLAYED": []}, equipment, {},
            {"Holder": "WSTRING", "Command": "USINT", "Arg": "LREAL", "Release": "BOOL"}, folder="Skills/Adapters").write()

    # The composite: the logic with its two timers, so a primitive needs no timer of its own; the
    # contract plugs into its socket, its plug goes to the equipment.
    c = Composite(p, LIB, "SKILL_Run",
                  "One run of a skill primitive, the same for every primitive: what the skill is comes in from its "
                  "contract (socket Contract, AContract); the command goes out to the equipment (plug Equipment, "
                  "AEquipment)",
                  {"INIT": (["Holder", "ReleaseAfter"], "EInit"), "HALT": [], "ABORT": []},
                  {"INITO": ([], "EInit"), "DONE": [], "FAILED": ["ErrorID"], "HALTED": ["ErrorID"],
                   "EQ_FREE": ["EquipmentFree"]},
                  {"Holder": "WSTRING", "ReleaseAfter": "BOOL"},
                  {"ErrorID": "UINT", "EquipmentFree": "BOOL"}, folder="Skills")
    c.adapters(sockets={"Contract": q("AContract")}, plugs={"Equipment": q("AEquipment")})
    c.fb("Logic", q("SKILL_RunLogic"))
    c.fb("Timer", STD["E_DELAY"])
    c.fb("WaitT", STD["E_DELAY"], DT="T#500ms")      # how long a run waits for another holder's release
    c.ev("INIT", "INITO")                              # nothing to set up: Holder and ReleaseAfter are kept
    for v in ["Holder", "ReleaseAfter"]:
        c.da(v, f"Logic.{v}")
    for ev in ["HALT", "ABORT"]:
        c.ev(ev, f"Logic.{ev}")
    for ev in contract:
        c.ev(f"Contract.{ev}", f"Logic.{ev}")
    for v in dict.fromkeys(v for vs in contract.values() for v in vs):    # Post comes with both, once
        c.da(f"Contract.{v}", f"Logic.{v}")
    for ev in ["DONE", "FAILED", "HALTED", "EQ_FREE"]:
        c.ev(f"Logic.{ev}", ev)
    c.da("Logic.ErrorID", "ErrorID")
    c.da("Logic.EquipmentFree", "EquipmentFree")
    c.ev("Logic.CMD", "Equipment.SEND")
    for v in ["Holder", "Command", "Arg", "Release"]:
        c.da(f"Logic.C_{v}", f"Equipment.{v}")
    c.ev("Equipment.PLAYED", "Logic.PLAYED")
    c.ev("Logic.TIMER_START", "Timer.START")
    c.da("Logic.TimerDT", "Timer.DT")
    c.ev("Logic.TIMER_STOP", "Timer.STOP")
    c.ev("Timer.EO", "Logic.TIMER")
    c.ev("Logic.WAIT_START", "WaitT.START")
    c.ev("Logic.WAIT_STOP", "WaitT.STOP")
    c.ev("WaitT.EO", "Logic.WAIT_OVER")
    c.group("OneRun", "One run: the contract's values in, the command out, until the end condition or the timer",
            ["Logic", "Timer", "WaitT"], dx=7000, dy=4200)
    c.write()

    # For a primitive without equipment (it only waits): every command is played at once.
    b = Basic(p, LIB, "SKILL_NoEquipment", "Stands in for the equipment of a primitive that has none: answers "
              "every SEND with PLAYED at once", {}, {}, None, None, None, folder="Skills/Base")
    b.adapters(sockets={"Skill": q("AEquipment")})
    b.state("Wait")
    b.state("Played", None, "Skill.PLAYED")
    b.trans("Wait", "Played", "Skill.SEND")
    b.trans("Played", "Wait", "1")
    b.write()


# Types a skill parameter can have, with the widest range (the default Lower and Upper; MIN and MAX
# are standard functions, so not usable as names).
PARAM_RANGE = {"LREAL": ("-1.0E308", "1.0E308"), "INT": ("-32768", "32767"), "DINT": ("-2147483648", "2147483647"),
               "UINT": ("0", "65535"), "BOOL": None}


def make_parameters(p: Project):
    """SKILL_Param_<type>: one skill parameter, chained per skill.

    INIT publishes the default (Value := Default); CHECK tests a Start argument Requested against Lower..Upper and
    passes the result of the parameters before it on (PreviousInRange -> AllInRange); LATCH takes the Start
    argument (CalledByClient) or the default, which a parent may have set (a bound parameter)."""
    for typ, bounds in PARAM_RANGE.items():
        check = "AllInRange := PreviousInRange AND (Requested >= Lower) AND (Requested <= Upper);" if bounds else "AllInRange := PreviousInRange;"
        Simple(p, LIB, f"SKILL_Param_{typ}", f"Skill parameter ({typ}): default, range check of a Start argument, "
               "latching for one run", {"INIT": (["Default", *(["Lower", "Upper"] if bounds else [])], "EInit"),
                                       "CHECK": ["Requested", "PreviousInRange"], "LATCH": ["CalledByClient", "Default"]},
               {"INITO": (["Value"], "EInit"), "CHECKED": ["AllInRange"], "LATCHED": ["Value"]},
               {"Default": typ, **({"Lower": (typ, bounds[0]), "Upper": (typ, bounds[1])} if bounds else {}), "Requested": typ,
                "PreviousInRange": ("BOOL", "TRUE"), "CalledByClient": "BOOL"},
               {"Value": typ, "AllInRange": "BOOL"},
               {"INIT": ("Value := Default;", "INITO"), "CHECK": (check, "CHECKED"),
                "LATCH": ("IF CalledByClient THEN\n  Value := Requested;\nELSE\n  Value := Default;\nEND_IF;", "LATCHED")},
               folder="Skills/Parameters").write()


# How a module level skill's steps can run besides one after the other (module rules, rule set 2): the
# branches of a parallel block, a condition deciding between two branches, and where they meet.
JOINS = (2, 3, 4)
OPERATORS = {"eq": "=", "ne": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
CONDITION_TYPES = {"LREAL": tuple(OPERATORS), "BOOL": ("eq", "ne")}


def make_flow(p: Project):
    """SKILL_Join<n>, SKILL_Condition_<type> and SKILL_Merge: the blocks a module level skill's flow is
    made of besides its steps. They have no INIT: like SKILL_FailMerge they hold no resources.

    SKILL_Join<n> ends a parallel block: START (with the block) forgets the last run; DONE_<i> and
    FAILED_<i> report branch i. DONE when every branch is done; on the first failure HALT (to every
    step of the block), then FAILED with that error once every branch has ended.

    SKILL_Condition_<type>: EVAL compares Operand with Expected by Operator (eq, ne, gt, gte, lt,
    lte) and answers YES or NO. SKILL_Merge: either branch of a decision ends in it, EO goes on."""
    for n in JOINS:
        branches = range(1, n + 1)
        b = Basic(p, LIB, f"SKILL_Join{n}", f"Ends a parallel block of {n} branches: DONE when all are done; on the "
                  "first failure HALT to the others, then FAILED with its error once all have ended",
                  {"START": [], **{f"DONE_{i}": [] for i in branches}, **{f"FAILED_{i}": [f"Error{i}"] for i in branches}},
                  {"DONE": [], "FAILED": ["Error"], "HALT": []},
                  {f"Error{i}": "UINT" for i in branches}, {"Error": "UINT"},
                  {**{f"Ended{i}": "BOOL" for i in branches}, "AnyFailed": "BOOL", "First": "UINT"}, folder="Skills/Flow")
        every = " AND ".join(f"Ended{i}" for i in branches)
        b.state("START")
        b.state("Reset", " ".join(f"Ended{i} := FALSE;" for i in branches) + " AnyFailed := FALSE;")
        b.state("Check")
        b.state("Done", None, "DONE")
        b.state("Fail", "Error := First;", "FAILED")
        b.trans("START", "Reset", "START")
        b.trans("Reset", "START", "1")
        for i in branches:
            b.state(f"Done{i}", f"Ended{i} := TRUE;")
            b.state(f"First{i}", f"Ended{i} := TRUE; AnyFailed := TRUE; First := Error{i};", "HALT")
            b.state(f"Later{i}", f"Ended{i} := TRUE;")
            b.trans("START", f"Done{i}", f"DONE_{i}")
            b.trans("START", f"First{i}", f"FAILED_{i}[NOT AnyFailed]")
            b.trans("START", f"Later{i}", f"FAILED_{i}")
            for state in (f"Done{i}", f"First{i}", f"Later{i}"):
                b.trans(state, "Check", "1")
        b.trans("Check", "Done", f"({every}) AND NOT AnyFailed")
        b.trans("Check", "Fail", f"({every}) AND AnyFailed")
        b.trans("Check", "START", "1")
        b.trans("Done", "Reset", "1")
        b.trans("Fail", "Reset", "1")
        b.write()
    for typ, ops in CONDITION_TYPES.items():
        test = " OR ".join(f"((Operator = '{op}') AND (Operand {OPERATORS[op]} Expected))" for op in ops)
        b = Basic(p, LIB, f"SKILL_Condition_{typ}", f"Compares Operand with Expected by Operator ({', '.join(ops)}): "
                  "YES or NO", {"EVAL": ["Operand", "Expected", "Operator"]}, {"YES": [], "NO": []},
                  {"Operand": typ, "Expected": typ, "Operator": ("STRING", "'eq'")}, {}, {"Holds": "BOOL"},
                  folder="Skills/Flow")
        b.state("START")
        b.state("Eval", f"Holds := {test};")
        b.state("Yes", None, "YES")
        b.state("No", None, "NO")
        b.trans("START", "Eval", "EVAL")
        b.trans("Eval", "Yes", "Holds")
        b.trans("Eval", "No", "1")
        b.trans("Yes", "START", "1")
        b.trans("No", "START", "1")
        b.write()
    b = Basic(p, LIB, "SKILL_Merge", "Where the branches of a decision meet: EI1 or EI2 gives EO",
              {"EI1": [], "EI2": []}, {"EO": []}, {}, {}, None, folder="Skills/Flow")
    b.state("START")
    b.state("One", None, "EO")
    b.state("Two", None, "EO")
    b.trans("START", "One", "EI1")
    b.trans("START", "Two", "EI2")
    b.trans("One", "START", "1")
    b.trans("Two", "START", "1")
    b.write()


def make_library(p: Project):
    """Write every module-independent type."""
    make_io(p)
    make_view(p, "Owner", "owner", "Owner", "WSTRING", "occupation owner")
    make_view(p, "State", "state", "State", "USINT", "PackML state")
    make_occupation(p)
    make_state_manager(p)
    make_skill_gate(p)
    make_skill_control(p)
    make_skill_core(p)
    make_skill_run(p)
    make_parameters(p)
    make_flow(p)
