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

    ei = {f"{m.upper()}_REQ": [f"{m}Session"] for m in MODULE_COMMANDS}
    ei.update({"OWNER_CHG": ["Owner"], "ACT": ["AllIdle"], "RESETTING_DONE": [], "RESETTING_FAILED": [],
               "STOPPING_DONE": [], "STOPPING_FAILED": [], "STOP_TIMEOUT": []})
    eo = {f"{m.upper()}_RSP": ["Accepted", "ErrorID"] for m in MODULE_COMMANDS}
    eo.update({"CNF": ["State"], "RUN_RESETTING": [], "RUN_STOPPING": [], "WD_START": [], "WD_STOP": []})
    b = Basic(p, LIB, "MOD_StateLogic",
              "PackML module state machine: commands only from the occupation owner and only where PackML allows "
              "them; runs the Resetting and Stopping procedures; Stopping waits until no skill is active",
              ei, eo, {**{f"{m}Session": "WSTRING" for m in MODULE_COMMANDS}, "Owner": "WSTRING",
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
        b.state("Chk" + m, f'Owned := ({m}Session = Owner) AND (Owner <> "");\n'
                           f"Accepted := Owned AND ({allowed});\n"
                           f"IF NOT Owned THEN\n  ErrorID := {ERRORS['NotPermitted']};\n"
                           f"ELSIF NOT Accepted THEN\n  ErrorID := {ERRORS['NotReady']};\nELSE\n  ErrorID := 0;\nEND_IF;",
                f"{m.upper()}_RSP")
        for w in MODULE_WAIT:
            b.trans(w, "Chk" + m, f"{m.upper()}_REQ")
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
        c.ev(f"{m}.IND", f"Logic.{m.upper()}_REQ")
        c.da(f"{m}.RD_1", f"Logic.{m}Session")
        c.ev(f"Logic.{m.upper()}_RSP", f"{m}.RSP")
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
# How long a skill shows Succeeded before it returns to Idle by itself.
SUCCEEDED_FOR = "T#1500ms"


def make_skill_control(p: Project):
    """SKILL_Control: the state machine every skill shares (primitive or module level skill).

    Idle/Succeeded/Failed -Start-> Running -> Succeeded | Failed(ErrorID); Succeeded returns to Idle
    by itself after SUCCEEDED_FOR (TO_IDLE_START -> TO_IDLE). Stop, a parent HALT or (for
    a skill started over OPC UA) the module entering Stopping -> Stopping: the execution is halted, then the stop procedure runs
    (RUN_STOPPING -> STOPPING_DONE) -> Failed(Interrupted). Abort, a parent ABORT or the module entering
    Aborting -> Aborted (outputs off at once); Reset, a parent RESET or the module Clearing -> Idle
    (RESET_SEQ passes it on to children).
    OPC UA commands need the occupation and (Start) the module in Execute; commands from a parent
    are not gated. Every start and end is counted on the module's activity channel (ACT +1/-1).
    """
    e, s = ERRORS, SKILL_STATES
    cmds = {"START": ["Session", "ParamsInRange", "EquipmentFree"], "STOP": ["StopSession"], "ABORT": ["AbortSession"], "RESET": ["ResetSession"]}
    ei = {"INIT": (["Module", "UaRoot", "UaPath"], "EInit"),
          **{f"{k}_REQ": v for k, v in cmds.items()},
          "OWNER_CHG": ["Owner"], "MOD_CHG": ["ModuleState"], "START": [], "HALT": [], "ABORT": [], "RESET": [],
          "EXECUTE_DONE": [], "EXECUTE_FAILED": ["ExecuteError"], "STOPPING_DONE": [], "TO_IDLE": []}
    eo = {"INITO": (["StartMethodId", "StopMethodId", "AbortMethodId", "ResetMethodId", "StateId", "ActivityId",
                     "ReleaseId"], "EInit"),
          **{f"{k}_RSP": ["Accepted", "ResponseError"] for k in cmds},
          "PUB": ["State", "ErrorID"], "RUN": ["CalledByClient"], "HALT_SEQ": [], "ABORT_SEQ": [], "RESET_SEQ": [], "RUN_STOPPING": [],
          "SUCCESS": [], "FAILURE": ["ErrorID"], "RELEASE": [], "ACT": ["ActivityDelta"], "TO_IDLE_START": [], "TO_IDLE_STOP": []}
    iv = {"Module": "WSTRING", "UaRoot": "WSTRING", "UaPath": "WSTRING", "Session": "WSTRING", "ParamsInRange": "BOOL",
          "EquipmentFree": "BOOL", "StopSession": "WSTRING", "AbortSession": "WSTRING", "ResetSession": "WSTRING", "Owner": "WSTRING",
          "ModuleState": "USINT", "ExecuteError": "UINT"}
    ov = {"StartMethodId": "WSTRING", "StopMethodId": "WSTRING", "AbortMethodId": "WSTRING", "ResetMethodId": "WSTRING", "StateId": "WSTRING",
          "ActivityId": "WSTRING", "ReleaseId": "WSTRING", "Accepted": "BOOL", "ResponseError": "UINT", "State": "USINT", "ErrorID": "UINT",
          "ActivityDelta": "INT", "CalledByClient": "BOOL"}
    b = Basic(p, LIB, "SKILL_Control",
              "Skill state machine: Start/Stop/Abort/Reset over OPC UA (owner only, Start only in module Execute) "
              "and START/HALT/ABORT from a parent; Idle 0, Running 1, Stopping 2, Succeeded 3, Failed 4, Aborted 5; "
              "RUN starts the execution (CalledByClient: with the Start arguments, else with the parent's values)",
              ei, eo, iv, ov, {"Owned": "BOOL", "Here": "USINT", "Active": "BOOL"}, folder="Skills/Base")
    base = cat("UaRoot", "UaPath")
    b.state("START")
    b.state("Init", "\n".join([f"StartMethodId := {ua('CREATE_METHOD', base, lit('/Start'))};",
                               f"StopMethodId := {ua('CREATE_METHOD', base, lit('/Stop'))};",
                               f"AbortMethodId := {ua('CREATE_METHOD', base, lit('/Abort'))};",
                               f"ResetMethodId := {ua('CREATE_METHOD', base, lit('/Reset'))};",
                               f"StateId := {ua('WRITE', base, lit('/State;'), base, lit('/ErrorID'))};",
                               f"ActivityId := {loc('Module', 'activity')};",
                               f"ReleaseId := {loc('Module', 'release')};"]), "INITO")
    for w, (state, here) in SKILL_WAIT.items():
        b.state(w, f"State := {s[state]};\nHere := {here};", "PUB", ["TO_IDLE_START"] if w == "Succeeded" else ())
    # Entry actions; a start stops the timer of a Succeeded it leaves.
    b.state("GoUa", "Active := TRUE;\nActivityDelta := 1;\nErrorID := 0;\nCalledByClient := TRUE;", "ACT", ["TO_IDLE_STOP", "RUN"])
    b.state("GoParent", "Active := TRUE;\nActivityDelta := 1;\nErrorID := 0;\nCalledByClient := FALSE;", "ACT",
            ["TO_IDLE_STOP", "RUN"])
    b.state("Halt", None, "HALT_SEQ")
    b.state("RunStop", None, "RUN_STOPPING")
    # Every end of a run is announced (RELEASE): a module level skill then gives up all it holds.
    b.state("Succeed", "Active := FALSE;\nActivityDelta := -1;\nErrorID := 0;", "ACT", ["RELEASE", "SUCCESS"])
    b.state("Fail", "Active := FALSE;\nActivityDelta := -1;\nErrorID := ExecuteError;", "ACT", ["RELEASE", "FAILURE"])
    b.state("Interrupted", f"Active := FALSE;\nActivityDelta := -1;\nErrorID := {e['Interrupted']};", "ACT",
            ["RELEASE", "FAILURE"])
    b.state("AbortChk")
    b.state("AbortActive", f"Active := FALSE;\nActivityDelta := -1;\nErrorID := {e['Interrupted']};", "ABORT_SEQ", ["ACT", "RELEASE"])
    b.state("AbortIdle", None, "ABORT_SEQ")
    b.state("StartRefused", f"ErrorID := {e['NotReady']};", "FAILURE")
    b.state("ResetOk", None, "RESET_SEQ")
    # Command checks: answer the method, then act or return to the wait state (Here).
    owned = 'Owned := ({0} = Owner) AND (Owner <> "");\n'
    session = {"Start": "Session", "Stop": "StopSession", "Abort": "AbortSession", "Reset": "ResetSession"}
    b.state("ChkStart", owned.format(session["Start"]) + "Accepted := FALSE;\n"
            f"IF NOT Owned THEN\n  ResponseError := {e['NotPermitted']};\n"
            f"ELSIF ModuleState <> {STATES['Execute']} THEN\n  ResponseError := {e['NotReady']};\n"
            f"ELSIF (Here = 1) OR (Here = 2) OR (Here = 3) THEN\n  ResponseError := {e['Busy']};\n"
            f"ELSIF Here = 6 THEN\n  ResponseError := {e['NotReady']};\n"
            f"ELSIF NOT ParamsInRange THEN\n  ResponseError := {e['OutOfRange']};\n"
            f"ELSIF NOT EquipmentFree THEN\n  ResponseError := {e['Busy']};\n"
            "ELSE\n  Accepted := TRUE;\n  ResponseError := 0;\nEND_IF;", "START_RSP")
    for m, valid in [("Stop", "Here = 1"), ("Abort", "Here <> 6"), ("Reset", "Here = 6")]:
        b.state("Chk" + m, owned.format(session[m]) + f"Accepted := Owned AND ({valid});\n"
                f"IF NOT Owned THEN\n  ResponseError := {e['NotPermitted']};\n"
                f"ELSIF NOT Accepted THEN\n  ResponseError := {e['NotReady']};\nELSE\n  ResponseError := 0;\nEND_IF;",
                f"{m.upper()}_RSP")
    b.trans("START", "Init", "INIT")
    b.trans("Init", "Idle", "1")
    for w in SKILL_WAIT:
        for k in cmds:
            b.trans(w, f"Chk{k.capitalize()}", f"{k}_REQ")
    for w in READY:
        b.trans(w, "GoParent", "START")
    b.trans("Aborted", "StartRefused", "START")
    b.trans("StartRefused", "Aborted", "1")
    for w in ["Running"]:
        b.trans(w, "Succeed", "EXECUTE_DONE")
        b.trans(w, "Fail", "EXECUTE_FAILED")
        b.trans(w, "Halt", "HALT")
        # Only a skill the occupant started stops itself when the module stops. One started by a parent
        # is halted by it; a step of the Stopping procedure must run exactly then.
        b.trans(w, "Halt", f"MOD_CHG[(ModuleState = {STATES['Stopping']}) AND CalledByClient]")
    b.trans("Stopping", "RunStop", "EXECUTE_DONE")
    b.trans("Stopping", "RunStop", "EXECUTE_FAILED")
    b.trans("StopProc", "Interrupted", "STOPPING_DONE")
    for w in [x for x in SKILL_WAIT if x != "Aborted"]:
        b.trans(w, "AbortChk", "ABORT")
        # Aborting is followed at once by Aborted, and a subscriber may see only the latter (a
        # local channel keeps the latest value): both mean abort.
        b.trans(w, "AbortChk", f"MOD_CHG[(ModuleState = {STATES['Aborting']}) OR (ModuleState = {STATES['Aborted']})]")
    # Likewise Clearing is followed at once by Stopped.
    b.trans("Aborted", "ResetOk", f"MOD_CHG[(ModuleState = {STATES['Clearing']}) OR (ModuleState = {STATES['Stopped']})]")
    b.trans("Aborted", "ResetOk", "RESET")
    b.trans("ResetOk", "Idle", "1")
    b.trans("GoUa", "Running", "1")
    b.trans("GoParent", "Running", "1")
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
    for chk, target in [("ChkStart", "GoUa"), ("ChkStop", "Halt"), ("ChkAbort", "AbortChk"), ("ChkReset", "ResetOk")]:
        b.trans(chk, target, "Accepted")
        for w, (_, here) in SKILL_WAIT.items():
            b.trans(chk, w, f"Here = {here}")
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
    c.ev("START_REQ", "Control.START_REQ")
    for v in ["Session", "ParamsInRange", "EquipmentFree"]:
        c.da(v, f"Control.{v}")
    c.ev("Control.START_RSP", "START_RSP")
    c.da("Control.Accepted", "Accepted", *[f"Ua{m}.SD_1" for m in methods])
    c.da("Control.ResponseError", "StartError", *[f"Ua{m}.SD_2" for m in methods])
    for m in methods:
        c.da(f"Control.{m}MethodId", f"Ua{m}.ID")
        c.ev(f"Ua{m}.IND", f"Control.{m.upper()}_REQ")
        c.da(f"Ua{m}.RD_1", f"Control.{m}Session")
        c.ev(f"Control.{m.upper()}_RSP", f"Ua{m}.RSP")
    c.ev("Owner.CHG", "Control.OWNER_CHG")
    c.da("Owner.Owner", "Control.Owner")
    c.ev("Mode.CHG", "Control.MOD_CHG")
    c.da("Mode.State", "Control.ModuleState")
    c.da("Control.StateId", "PubState.ID")
    c.ev("Control.PUB", "PubState.REQ")
    c.da("Control.State", "PubState.SD_1", "State")
    c.da("Control.ErrorID", "PubState.SD_2", "ErrorID")
    c.da("Control.ActivityId", "Act.ID")
    c.ev("Control.ACT", "Act.REQ")
    c.da("Control.ActivityDelta", "Act.SD_1")
    for ev in ["START", "HALT", "ABORT", "RESET", "EXECUTE_DONE", "EXECUTE_FAILED", "STOPPING_DONE"]:
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
    c.group("StateMachine", "The skill's states and when a Succeeded returns to Idle",
            ["Control", "ToIdle"])
    c.group("ModuleViews", "The module's owner and state in, the activity count out", ["Owner", "Mode", "Act"])
    c.group("OpcUa", "The methods Stop, Abort and Reset, and the published State and ErrorID",
            ["UaStop", "UaAbort", "UaReset", "PubState"])
    c.group("Release", "At the end of a run of a module level skill: everything it holds given up",
            ["PubRelease"])
    c.write()


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


def make_library(p: Project):
    """Write every module-independent type."""
    make_io(p)
    make_view(p, "Owner", "owner", "Owner", "WSTRING", "occupation owner")
    make_view(p, "State", "state", "State", "USINT", "PackML state")
    make_occupation(p)
    make_state_manager(p)
    make_skill_control(p)
    make_skill_core(p)
    make_parameters(p)
