"""Comments for the pins of the generated block types; the 4diac IDE shows them as tooltips.

A pin's comment is found in this order: the type's own (``TYPES``), its kind's (``KINDS``, by the
type's prefix), the names every kind shares (``COMMON``), the module's own names (``domain``: its
equipment's signals, its skills' parameters and results), and the patterns of names the generator
makes (``PATTERNS``: ``I_<input>``, ``<point>_Address``, ...). A test requires every pin to have one.
"""
from __future__ import annotations

import re

SKILL_STATES = "0 Idle, 1 Running, 2 Stopping, 3 Succeeded, 4 Failed, 5 Aborted"
ERRORS = ("0 none, 1 PreconditionViolated, 2 InvariantViolated, 3 Timeout, 4 NotReady, 5 NotPermitted, 6 Busy, "
          "7 Interrupted, 8 OutOfRange")
PACKML = "PackML state: 1 Clearing, 2 Stopped, 3 Starting, 4 Idle, 6 Execute, 7 Stopping, 8 Aborting, 9 Aborted, 15 Resetting"

COMMON = {
    # Events every kind has.
    "INIT": "Initialise, once at start-up (the INIT chain); takes the values given with it",
    "INITO": "Initialised: the next block of the INIT chain goes on",
    "REQ": "Request",
    "CNF": "Confirmation of REQ",
    "CHG": "The value changed",
    # The module and OPC UA.
    "Module": "The module's name; its local channels are named after it (loc[<Module>/...])",
    "UaRoot": "The module's OPC UA folder, e.g. /Objects/Filling",
    "UaPath": "This skill's OPC UA folder below UaRoot, e.g. /Skills/Dispensing",
    "UaEnable": "Publish on OPC UA",
    "Methods": "Offer the OPC UA methods Start, Stop, Abort, Reset (FALSE: a step, run by its parent)",
    "Accepted": "The call was accepted",
    "ErrorID": f"Error code: {ERRORS}",
    "Owner": "Session ID of the module's owner (empty: free)",
    "ModuleState": PACKML,
    "State": f"Skill state: {SKILL_STATES}",
    # A skill's run.
    "START": "Start a run, from the parent (a step of a sequence): no session check",
    "HALT": "Stop the run, from the parent",
    "ABORT": "Abort: everything off at once",
    "RESET": "Reset from Failed or Aborted to Idle",
    "SUCCESS": "The run succeeded (the results are set)",
    "FAILURE": "The run failed (ErrorID)",
    "Holder": "The name the equipment is held under: the skill's own, or for a step the skill it belongs to",
    "Session": "Session ID of the caller of Start (must be the module's owner)",
    "Timeout": "How long the run may take before it fails with Timeout (3)",
}

KINDS = {
    "SKILL_Param_": {
        "INIT": "Publish the default as the value",
        "CHECK": "Check Requested against Lower..Upper",
        "CHECKED": "Checked: AllInRange",
        "LATCH": "Take the value for this run: Requested if CalledByClient, else Default",
        "LATCHED": "Value holds this run's value",
        "INITO": "Initialised: Value is the default",
        "Default": "The value when the caller gives none; a parent's binding sets it",
        "Lower": "The smallest value accepted",
        "Upper": "The largest value accepted",
        "Requested": "The value the caller asks for (an argument of Start)",
        "PreviousInRange": "The parameters checked before this one are all in range (TRUE for the first)",
        "CalledByClient": "Started over OPC UA: take Requested, not the default",
        "Value": "The value for this run",
        "AllInRange": "This and every parameter before it are in range",
    },
    "IO_Route": {
        "INIT": "Work out from Address how the point is reached",
        "Address": "Where the point is: 'gpio[chip:line(:pull_up|:pull_down)(:active_low)]', "
                   "'pwm[chip:channel:period_ns]', 'modbus[...]', 'sim', or an IO handle's name; empty: not connected",
        "SimValue": "The value read when the address is 'sim'",
        "INIT_IO": "Set up the line, the local IO block and the Modbus client (each only if it is the way)",
        "IO_READY": "The line, the local IO block and the Modbus client are initialised",
        "INITO": "Initialised: QO says whether the point is reachable",
        "REQ": "Access the point",
        "REQ_G": "Access the point through the local IO block (IX/QX/IW/QW)",
        "REQ_M": "Access the point through the Modbus client",
        "CNF_G": "The local IO block answered",
        "CNF_M": "The Modbus client answered",
        "CNF": "Done: QO says whether it worked",
        "QO_G": "The local IO block works",
        "QO_M": "The Modbus client works",
        "IN_G": "The raw value read through the local IO block",
        "IN_M": "The raw value read through Modbus",
        "GQI": "Use the local IO block",
        "MQI": "Use the Modbus client",
        "IoName": "The local IO handle's name (PARAMS of IX/QX/IW/QW)",
        "ModbusId": "The Modbus CLIENT's ID",
        "LineQI": "Set up a Raspberry Pi line here (a gpio[...] or pwm[...] address)",
        "LineName": "The name the line is registered under (the address)",
        "ChipNo": "The GPIO or PWM chip's number",
        "LineNo": "The GPIO line's or PWM channel's number",
        "LineBias": "GPIO bias: 0 none, 2 pull-up, 3 pull-down (FORTE 3.3.0's numbering)",
        "LineLow": "The line is active low",
        "Period": "The PWM period in ns",
        "Root": "The sysfs PWM folder (empty: /sys/class/pwm)",
        "Value": "The raw value to write (0 to 65535 for an analog output)",
        "IN": "The value read (an analog one scaled)",
        "QO": "The point is reachable, the last access worked",
    },
    "IO_": {
        "INIT": "Set up the point from Address (at start-up)",
        "Address": "Where the point is: 'gpio[chip:line(:pull_up|:pull_down)(:active_low)]', "
                   "'pwm[chip:channel:period_ns]', 'modbus[...]', 'sim', or an IO handle's name; empty: not connected",
        "SimValue": "The value read when the address is 'sim'",
        "INITO": "Set up: QO says whether the point is reachable",
        "REQ": "Read the point, or write OUT to it",
        "CNF": "Done: QO says whether it worked (an input: IN is the value read)",
        "QO": "The point is reachable, the last access worked",
        "IN": "The value read (an analog one scaled)",
        "OUT": "The value to write",
        "EN": "On; FALSE writes 0 (no pulses on a PWM channel)",
        "Gain": "Raw = Bias + OUT * Gain, limited to 0..65535",
        "Bias": "Raw = Bias + OUT * Gain, limited to 0..65535",
        "Scale": "Engineering value per raw count",
    },
    "MOD_StateLogic": {
        "CNF": "The state changed",
        "ACT": "The number of running skills changed (AllIdle)",
        "OWNER_CHG": "The owner changed",
        "RESETTING_DONE": "The Resetting procedure ended",
        "RESETTING_FAILED": "The Resetting procedure failed",
        "STOPPING_DONE": "The Stopping procedure ended",
        "STOPPING_FAILED": "The Stopping procedure failed",
        "STOP_TIMEOUT": "Stopping took longer than StopTimeout",
        "RUN_RESETTING": "Run the Resetting procedure",
        "RUN_STOPPING": "Run the Stopping procedure",
        "WD_START": "Start the stop timeout",
        "WD_STOP": "Stop the stop timeout",
        "State": PACKML,
        "AllIdle": "No skill runs",
    },
    "MOD_": {
        "RESETTING_DONE": "The Resetting procedure ended",
        "RESETTING_FAILED": "The Resetting procedure failed",
        "STOPPING_DONE": "The Stopping procedure ended",
        "STOPPING_FAILED": "The Stopping procedure failed",
        "RUN_RESETTING": "Run the Resetting procedure (the module was reset)",
        "RUN_STOPPING": "Run the Stopping procedure (the module was stopped)",
        "StopTimeout": "How long Stopping may take before the module aborts",
        "State": PACKML,
        "ACT": "A skill started (+1) or ended (-1)",
        "Delta": "+1 when a skill starts, -1 when it ends",
        "Active": "Some skill runs",
        "AllIdle": "No skill runs",
        "REQ": "The value arrived on the local channel",
        "Received": "The value as it arrived",
        "IdSub": "Local channel the value arrives on",
        "IdQuery": "Local channel that asks for the current value (a block that starts later)",
        "IdOwner": "Local channel of the owner",
        "IdState": "Local channel of the module's state",
        "IdAct": "Local channel of the activity count",
        "IdPub": "OPC UA ID of the published value",
        "IdOccupy": "OPC UA ID of the method Occupy",
        "IdRelease": "OPC UA ID of the method Release",
        "Occupied": "The module is occupied",
        "OCCUPY_REQ": "Occupy(Session) was called",
        "OCCUPY_RSP": "Answer to Occupy: Accepted, ErrorID",
        "RELEASE_REQ": "Release(Session) was called",
        "RELEASE_RSP": "Answer to Release: Accepted, ErrorID",
        "QUERY_REQ": "A block asks for the current owner",
    },
    "SKILL_": {
        "START_REQ": "Start(Session, parameters) was called: check Session, ParamsInRange, EquipmentFree",
        "START_RSP": "Answer to Start",
        "STOP_REQ": "Stop(Session) was called",
        "STOP_RSP": "Answer to Stop",
        "ABORT_REQ": "Abort(Session) was called",
        "ABORT_RSP": "Answer to Abort",
        "RESET_REQ": "Reset(Session) was called",
        "RESET_RSP": "Answer to Reset",
        "OWNER_CHG": "The module's owner changed",
        "MOD_CHG": "The module's state changed (its Stopping halts, its Aborting aborts the skill)",
        "EXECUTE_DONE": "The execution ended successfully",
        "EXECUTE_FAILED": "The execution failed (ExecuteError)",
        "STOPPING_DONE": "The stop sequence ended",
        "TO_IDLE": "Succeeded long enough: back to Idle",
        "PUB": "Publish State and ErrorID",
        "RUN": "Run: latch the parameters, start the execution",
        "HALT_SEQ": "Halt the execute sequence",
        "ABORT_SEQ": "Abort the sequences",
        "RESET_SEQ": "Reset the sequences",
        "RUN_STOPPING": "Run the stop sequence (the skill was stopped)",
        "RELEASE": "A run ended: give up what the skill holds (published if ReleaseAll)",
        "ACT": "Count the module's activity (ActivityDelta)",
        "TO_IDLE_START": "Start the timer back to Idle",
        "TO_IDLE_STOP": "Stop the timer back to Idle",
        "ReleaseAll": "When a run ends, give up everything held under Holder (a module level skill)",
        "ParamsInRange": "Every Start argument lies within its limits",
        "EquipmentFree": "The equipment is free, or held by this skill",
        "ExecuteError": "Why the execution failed",
        "StopSession": "Session ID of the caller of Stop",
        "AbortSession": "Session ID of the caller of Abort",
        "ResetSession": "Session ID of the caller of Reset",
        "StartMethodId": "OPC UA ID of the Start method, for its SERVER block",
        "StopMethodId": "OPC UA ID of the Stop method",
        "AbortMethodId": "OPC UA ID of the Abort method",
        "ResetMethodId": "OPC UA ID of the Reset method",
        "StateId": "OPC UA ID of the published State and ErrorID",
        "ActivityId": "Local channel of the module's activity count",
        "ReleaseId": "Local channel the module's equipment is released on",
        "ResponseError": "Why a call was refused (error code)",
        "StartError": "Why Start was refused (error code)",
        "ActivityDelta": "+1 when the run starts, -1 when it ends",
        "CalledByClient": "Started over OPC UA (take the Start arguments), not by a parent (take the defaults)",
        "FAIL_1": "A step failed (Error1)",
        "FAIL_2": "A step failed (Error2)",
        "FAIL": "One of them failed (Error)",
        "Error1": "Error code of the first",
        "Error2": "Error code of the second",
        "Error": "Error code of the one that failed",
    },
    "SKILL_Join": {
        "START": "The parallel block starts: forget the last run",
        **{f"DONE_{i}": f"Branch {i} is done" for i in range(1, 5)},
        **{f"FAILED_{i}": f"Branch {i} failed (Error{i})" for i in range(1, 5)},
        **{f"Error{i}": f"Error code of branch {i}" for i in range(1, 5)},
        "DONE": "Every branch is done",
        "FAILED": "A branch failed and every branch has ended (Error)",
        "HALT": "A branch failed: stop the others",
        "Error": "Error code of the branch that failed first",
    },
    "SKILL_Condition_": {
        "EVAL": "Evaluate the condition (the steps before it are done)",
        "YES": "The condition holds: the first branch",
        "NO": "The condition does not hold: the second branch, or past the conditional steps",
        "Operand": "What is compared: a parameter of the skill or a result of a step",
        "Expected": "What it is compared with",
        "Operator": "eq, ne, gt, gte, lt or lte: Operand <op> Expected",
    },
    "SKILL_Merge": {
        "EI1": "The first branch of the decision is done",
        "EI2": "The second branch is done, or there was none to run",
        "EO": "The decision is done: the next step goes on",
    },
    "SK_": {
        "INIT": "Initialise: its OPC UA nodes and its equipment's channels",
        "ReleaseAfter": "Give up the equipment when the run ends (FALSE: the next step keeps it)",
    },
    "SL_": {
        "INIT": "Initialise: name the channels and OPC UA variables",
        "START": "Start the run with the parameters (checks the Precondition first)",
        "HALT": "Stop the run (ErrorID Interrupted)",
        "ABORT": "Abort the run: the equipment off and given up",
        "TIMER": "The run's timer expired",
        "SAMPLE": "The equipment's state arrived",
        "WAIT_OVER": "Waited long enough for another holder to let go",
        "PLAYED": "The command's phases were played",
        "DONE": "The run succeeded (results set)",
        "FAILED": "The run failed (ErrorID)",
        "HALTED": "The run was stopped",
        "TIMER_START": "Start the timer (TimerDT)",
        "TIMER_STOP": "Stop the timer",
        "WAIT_START": "Start waiting for the equipment",
        "WAIT_STOP": "Stop waiting",
        "CMD": "Send a command to the equipment",
        "EQ_FREE": "EquipmentFree is updated",
        "EquipmentFree": "The equipment is free, or held under Holder",
        "Equipment": "The equipment item it drives",
        "ReleaseAfter": "Give up the equipment with the run's last command",
        "EqHolder": "Who holds the equipment now (empty: free)",
        "TimerDT": "How long the timer runs",
        "IdEqState": "Local channel of the equipment's state",
        "IdEqCmd": "Local channel of the equipment's commands",
        "IdParams": "OPC UA ID of the published parameters",
        "IdResults": "OPC UA ID of the published results",
        "C_Holder": "Sent with the command: who holds the equipment",
        "C_Command": "Sent with the command: the command's code",
        "C_Arg": "Sent with the command: its argument (e.g. a position)",
        "C_Release": "Sent with the command: give up the equipment after it",
    },
    "EL_": {
        "CMD": "A command arrived from a holder",
        "RELEASE": "A release arrived on the module's release channel (R_Holder)",
        "SAMPLE": "The inputs were read",
        "REFRESH": "Cycle: write the outputs again",
        "DRIVEN": "The outputs were written",
        "MOD_CHG": "The module's state changed (its Aborting switches all off)",
        "MOVE_T": "The move's time is up: the axis is at the goal",
        "DRIVE": "Write the outputs",
        "STATE": "Publish the state (the inputs and the holder)",
        "MOVE_START": "Start the move's timer (MoveDT)",
        "MOVE_STOP": "Stop the move's timer",
        "Name": "The equipment item's name: its local channels and OPC UA folder",
        "C_Holder": "Who sends the command",
        "C_Release": "Give up the equipment after this command",
        "C_Move": "Move to a position",
        "C_Goal": "The position to move to",
        "R_Holder": "Who gives up the equipment",
        "IdCmd": "Local channel of the commands",
        "IdRelease": "Local channel of the releases (the module's, one for all equipment)",
        "IdState": "Local channel of the state",
        "IdPub": "OPC UA ID of the published inputs",
        "Holder": "Who holds the equipment (empty: free)",
        "MoveDT": "How long the move takes",
    },
    "EV_": {"REQ": "The equipment's state arrived", "CNF": "The values below are updated",
            "Holder": "Who holds the equipment (empty: free)"},
    "EC_": {
        "PLAY": "Play a command: its output values, phase by phase",
        "PHASE_T": "A phase's time is up",
        "OUT": "Send the output values",
        "PHASE_START": "Start a phase's timer (PhaseDT)",
        "PHASE_STOP": "Stop the phase's timer",
        "PLAYED": "All phases were played",
        "Holder": "Who sends the command",
        "Command": "The command's code",
        "Arg": "The command's argument (e.g. a position)",
        "Release": "Give up the equipment after the command",
        "O_Holder": "Sent: who holds the equipment",
        "O_Release": "Sent: give up the equipment after this",
        "N_Move": "Sent: move to a position",
        "N_Goal": "Sent: the position to move to",
        "PhaseDT": "How long the phase lasts",
    },
    "EQ_": {"Name": "The equipment item's name: its local channels and OPC UA folder",
            "CycleTime": "How often the inputs are read"},
}

PATTERNS = [
    (r"I_(\w+)", "{0} as read or received"),
    (r"CE_(\w+)", "Commanded: {0} enabled"),
    (r"C_(\w+)", "Commanded value of {0}"),
    (r"NE_(\w+)", "Sent: {0} enabled"),
    (r"N_(\w+)", "Sent: the value of {0}"),
    (r"O_(\w+)", "The value to write to {0}"),
    (r"E_(\w+)", "{0} enabled (FALSE writes 0)"),
    (r"(\w+)_Address", "Where {0} is: 'gpio[chip:line(:pull_up|:pull_down)(:active_low)]', "
                       "'pwm[chip:channel:period_ns]', 'modbus[...]', 'sim', or an IO handle's name; empty: not connected"),
    (r"(\w+)_Sim", "The value of {0} when simulated (address 'sim')"),
    (r"(\w+)_Scale", "Engineering value per raw count of {0}"),
    (r"(\w+)_Gain", "{0}: raw = Bias + value * Gain"),
    (r"(\w+)_Bias", "{0}: raw = Bias + value * Gain"),
    (r"R_(\w+)", "Result: {0}"),
    (r"(\w+)Session", "Session ID of the caller of {0}"),
    (r"(\w+)_REQ", "{0}(Session) was called"),
    (r"(\w+)_RSP", "Answer to {0}: Accepted, ErrorID"),
    (r"Id(\w+)", "ID of the channel or OPC UA node of {0}"),
]


def comment(type_name: str, pin: str, domain: dict[str, str]) -> str | None:
    """The comment of ``pin`` of the type ``type_name``."""
    for prefix, pins in sorted(KINDS.items(), key=lambda kv: -len(kv[0])):
        if type_name.startswith(prefix) and pin in pins:
            return pins[pin]
    if pin in COMMON:
        return COMMON[pin]
    if pin in domain:
        return domain[pin]
    for pattern, text in PATTERNS:
        if m := re.fullmatch(pattern, pin):
            return text.format(m.group(1))
    return None


def domain(spec) -> dict[str, str]:
    """What the module's own names mean: its equipment's signals, its skills' parameters and results."""
    found = {}
    for item, eq in spec.equipment.items():
        for name, i in eq.inputs.items():
            unit = f" ({i.unit})" if i.unit else ""
            what = "worked out by the equipment" if getattr(i, "computed", False) else "an input"
            found.setdefault(name, f"{item}: {name}{unit}, {what}")
        for name, o in eq.outputs.items():
            unit = f" ({o.unit})" if o.unit else ""
            found.setdefault(name, f"{item}: {name}{unit}, an output")
    for skills in (spec.skills, spec.composites):
        for skill in skills.values():
            for name, p in skill.parameters.items():
                bounds = (f", {p.minimum} to {p.maximum}" if p.minimum is not None and p.maximum is not None else "")
                unit = f" {p.unit}" if p.unit else ""
                found.setdefault(name, f"Parameter {name}{unit}{bounds}{': ' + p.description if p.description else ''}")
    return found


def annotate(root, domain_: dict[str, str]):
    """Give every event and variable of a type's interface its comment (one already set is kept)."""
    name = root.get("Name", "")
    iface = root.find("InterfaceList")
    if iface is None:
        return
    for el in iface.iter():
        if el.tag in ("Event", "VarDeclaration") and not el.get("Comment"):
            text = comment(name, el.get("Name"), domain_)
            if text:
                el.set("Comment", text)
