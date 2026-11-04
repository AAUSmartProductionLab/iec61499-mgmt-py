"""Plain-language descriptions for the 4diac IDE: what each block type is for, and what each block of a
module's program does, where its calls come from and where its data goes.

A type's ``Comment`` begins with a few sentences in plain words; its technical summary follows.
Every block instance gets a ``Comment`` saying its role in the program it is in: in the application
(the module's own blocks, the steps of its skills and procedures) and inside the composite types (the
blocks a skill or an equipment block is made of). The IDE shows a type's comment in the palette and
the type's properties, and an instance's comment on the block and in its properties.

Comments are not part of a type's hash (checked on 28 Oct 2026 with the 4diac IDE 3.3 export): a
program with new comments runs on the FORTE that was built before. docs/filling-program.md explains
the same in more detail.
"""
from __future__ import annotations

import re

# What a block type is for, by its name (a library type) or by its prefix (a module's own type).
LIBRARY = {
    "MOD_Occupation": "Who may command the module. A client first calls the OPC UA method Occupy with a session "
                      "id it chose; until it calls Release, only commands carrying that session id are accepted. "
                      "Publishes Occupied (never the id) and tells every block of the module who the owner is.",
    "MOD_OccupationIds": "Builds the OPC UA addresses (Occupy, Release, Occupied) and the local channel names of the "
                         "occupation from the module's name and OPC UA root.",
    "MOD_OccupationLogic": "Decides Occupy and Release: occupy when free (or again by the owner), release only by the "
                           "owner, and answer Accepted or an error code.",
    "MOD_StateManager": "The module's PackML state: Stopped, Resetting, Idle, Execute, Stopping, Aborted. The owner "
                        "changes it with the OPC UA methods Reset, Start, Stop, Abort and Clear. It runs the "
                        "Resetting and Stopping procedures and publishes the state for clients and for every block.",
    "MOD_StateIds": "Builds the OPC UA addresses (Module/Reset ... Module/State) and the local channel names of the "
                    "state manager.",
    "MOD_StateLogic": "The PackML state machine itself: Reset, Start, Stop, Abort and Clear take it from state to "
                      "state (MOD_StateGate has already checked who sent them, and that PackML allows them now); "
                      "while Stopping it waits until no skill runs any more.",
    "MOD_ActivityCount": "Counts the skills that are running: every skill says +1 when it starts and -1 when it ends.",
    "MOD_OwnerView": "Tells the block it sits in who occupies the module, and asks for it once at start.",
    "MOD_OwnerLatch": "Keeps the last owner heard on the owner channel.",
    "MOD_StateView": "Tells the block it sits in the module's PackML state, and asks for it once at start.",
    "MOD_StateLatch": "Keeps the last module state heard on the state channel.",
    "SKILL_Core": "The part every skill shares: its state machine (Idle, Running, Stopping, Succeeded, Failed, "
                  "Aborted), the OPC UA methods Stop, Abort and Reset, and the State and ErrorID it publishes. It "
                  "checks a client's Start (the caller holds the occupation, the module is in Execute, the skill is "
                  "not running, the values are in range, the equipment is free) and then starts the skill's own "
                  "logic.",
    "SKILL_Control": "The skill's state machine inside SKILL_Core: what Start, Stop, Abort and Reset do in each state. "
                     "A client's command reaches it only once SKILL_Gate has accepted it, so here a command is the "
                     "same from a client or from a parent.",
    "MOD_StateGate": "The module's front desk inside MOD_StateManager: answers Reset, Start, Stop, Abort or Clear at "
                     "once (only from the module's owner, only in a state PackML allows it in) and passes an accepted "
                     "command on to MOD_StateLogic.",
    "SKILL_Run": "One run of a skill primitive, the same for every primitive: waits until the equipment is free, checks "
                 "the precondition, sends the command, then watches the conditions (or a timer) until the skill is "
                 "done, has failed or has timed out, and sends the closing command. What the skill is comes in from its "
                 "contract (SC_).",
    "AContract": "An adapter: one connection from a primitive's contract (SC_, the plug) to its run (SKILL_Run, the "
                 "socket) that carries what the contract says: at the start what to do and whether it may start, at "
                 "each new state of the equipment whether it is done and may go on.",
    "AEquipment": "An adapter: one connection from a skill's run (the plug) to its equipment's port (EP_, the "
                  "socket) that carries a command out and the word that it was played back.",
    "SKILL_NoEquipment": "Stands in for the equipment of a primitive that has none (one that only waits): plays "
                         "every command at once.",
    "SKILL_RunLogic": "The state machine of SKILL_Run: the precondition, waiting for the equipment, the command, the "
                      "end condition, the timeout, the closing command.",
    "SKILL_Gate": "The front desk of a skill, inside SKILL_Core: answers a client's Start, Stop, Abort or Reset at "
                  "once (only the module's owner; Start only with the module in Execute, the skill not running, the "
                  "values in range and the equipment free) and passes an accepted command on to SKILL_Control, as a "
                  "parent's command is passed on.",
    "SKILL_FailMerge": "Joins two failure events (with their error codes) into one, because a data input can only be "
                       "wired once.",
    "SKILL_Merge": "Where the two branches of a decision meet again: either branch's end goes on.",
    "IO_DI": "One digital input (a switch, a sensor). Its Address says where the signal is: a Raspberry Pi pin, a "
             "Modbus register, or simulated. It reads the value when asked.",
    "IO_DO": "One digital output (a motor's enable, a direction, a valve). Its Address says where the signal goes: a "
             "Raspberry Pi pin, a Modbus coil, or simulated.",
    "IO_AI": "One analog input (a weight, a pressure). Its Address says where it is read: an IO handle, a Modbus "
             "register, or simulated.",
    "IO_AO": "One analog output, also a PWM channel (the step pulses of a stepper motor, a motor's speed). Its Address "
             "says where it goes: a Raspberry Pi PWM channel, a Modbus register, or simulated.",
}
LIBRARY_PREFIX = {
    "IO_Route": "Picks the way an IO block reaches its signal from the Address (a Pi line, a local IO handle, Modbus "
                "or simulated) and passes values through that way only.",
    "SKILL_Param_": "One parameter of a skill: keeps its default, checks a value a client sends with Start against "
                    "the limits, and holds the value for the run.",
    "SKILL_Join": "Ends a block of steps that run side by side: done when every branch is done; if one fails, the "
                  "others are halted and the block fails.",
    "SKILL_Condition_": "One comparison in a decision of a skill (for example Weight greater than 1.9): answers YES or "
                        "NO.",
}
MODULE_PREFIX = {
    "SK_": "A skill primitive: one action of one piece of equipment (move the axis, run the pump, weigh). It can be "
           "called on its own over OPC UA, or be a step of a bigger skill. Inside: SKILL_Core (state machine and "
           "OPC UA methods), a parameter block per parameter, SC_ (its contract: what this skill does and when it is "
           "done), SKILL_Run (one run, the same for every primitive) and EP_ (the equipment as the skill sees it).",
    "SC_": "The contract of a skill primitive, the only part that is its own: which command it sends (and with what "
           "argument, and which when it ends), how long it may run, and three conditions on the equipment's signals "
           "and its parameters: when it may start, when it is done, what must hold while it runs.",
    "EP_": "The equipment as its skills see it, the same in every skill that uses it: plays a command (its output "
           "values, phase by phase) on the equipment's command channel, and gives the equipment's newest state.",
    "EQ_": "An equipment block: the only block that touches this equipment's pins. Skills send it what to switch "
           "over a local channel; it switches the outputs (off first, then on), reads the inputs every cycle and "
           "reports them to the skills and to OPC UA. One skill holds it at a time; on release or when the module "
           "aborts it switches everything off.",
    "EL_": "The logic of an equipment block: one holder at a time, outputs switched off before new ones go on, all off "
           "on release or abort, inputs reported when they change.",
    "EV_": "Names the equipment's two channels, and unpacks its state channel into named values (its inputs and who "
           "holds it) for a skill.",
    "EC_": "The equipment's command table: turns a command's name (Up, Down, Run, ...) into the output values to "
           "switch, phase by phase with their times.",
}


def strip(value: str | None) -> str:
    """A parameter's value without the quotes of a string literal."""
    return (value or "").strip().strip("'\"")


def type_comment(name: str, technical: str | None) -> str:
    """The comment of a block type: plain words first, then its technical summary."""
    plain = LIBRARY.get(name) or next((text for prefix, text in LIBRARY_PREFIX.items() if name.startswith(prefix)), None) \
        or next((text for prefix, text in MODULE_PREFIX.items() if name.startswith(prefix)), None)
    if not plain or (technical or "").startswith(plain):
        return technical or ""
    return f"{plain} Technical: {technical}" if technical else plain


# Inside a composite type: what each block is for, by the composite's kind and the block's name.
INSIDE = {
    "SK_": {
        "Control": "The skill's state machine (SKILL_Core): checks a client's Start, publishes State and ErrorID, "
                   "offers Stop, Abort and Reset over OPC UA, and starts the run when it may begin.",
        "Contract": "What this skill is (its SC_ type): the command it sends, how long it may run, and when it may "
                    "start, is done, and must stop.",
        "Run": "One run (SKILL_Run, the same in every primitive): waits for the equipment, checks the contract's "
               "precondition, sends the command and watches the conditions until the skill is done.",
        "Port": "The equipment as this skill sees it (EP_): its state in (to the contract), the commands from the run "
                "(over the adapter AEquipment).",
        "UaStart": "The OPC UA method Start: a client's call arrives here with its session id and the parameters; "
                   "Control's answer (Accepted, ErrorID) goes back to the client.",
        "PubParams": "Writes the parameter values of the current run to OPC UA (Parameters/...).",
        "PubResults": "Writes the skill's results to OPC UA (Results/...) when a run succeeds.",
    },
    "SKILL_Run": {
        "Logic": "The run's state machine (SKILL_RunLogic).",
        "Timer": "Ends a skill that runs for a time, or fails a skill that takes longer than its timeout.",
        "WaitT": "Waits up to half a second for the equipment to become free before giving up (Busy).",
    },
    "EP_": {
        "EqView": "Names the equipment's channels, and unpacks its state into named values.",
        "EqState": "Listens to the equipment's state channel: its inputs and who holds it.",
        "Driver": "The equipment's command table (EC_): turns a command into output values, phase by phase.",
        "PhaseT": "Times the phases of a command.",
        "EqCmd": "Sends the output values and the holder's name to the equipment block on its command channel.",
    },
    "EQ_": {
        "Logic": "The equipment's logic (EL_): takes commands from one holder at a time, switches the outputs (off "
                 "first, then on), switches all off on release or module abort, and reports input changes.",
        "Cycle": "Ticks every cycle so the inputs are read and the outputs refreshed.",
        "MoveT": "Times a move to a position: the distance divided by the axis' speed.",
        "Mode": "Watches the module's PackML state, to switch everything off when the module aborts.",
        "SubCmd": "Receives the commands skills send on this equipment's command channel.",
        "SubRelease": "Hears the module's release channel: when its holder gives up, everything goes off.",
        "PubState": "Publishes the inputs and the holder on this equipment's state channel, for the skills.",
        "PubUa": "Writes the inputs (and a position, if it keeps one) to OPC UA, below Equipment/<item>.",
    },
    "MOD_Occupation": {
        "Ids": "Builds the OPC UA addresses and channel names from the module's name.",
        "Occupy": "The OPC UA method Occupation/Occupy(Session).",
        "Release": "The OPC UA method Occupation/Release(Session).",
        "Logic": "Decides who may occupy and release.",
        "PubOwner": "Tells every block of the module the owner, on the owner channel.",
        "SubQuery": "Answers a block that asks who the owner is (at its start).",
        "PubUa": "Writes Occupation/Occupied to OPC UA.",
    },
    "MOD_StateManager": {
        "Ids": "Builds the OPC UA addresses and channel names from the module's name.",
        "Owner": "Knows who occupies the module: only the owner may change the state.",
        "Reset": "The OPC UA method Module/Reset(Session).",
        "Start": "The OPC UA method Module/Start(Session).",
        "Stop": "The OPC UA method Module/Stop(Session).",
        "Abort": "The OPC UA method Module/Abort(Session).",
        "Clear": "The OPC UA method Module/Clear(Session).",
        "Gate": "Decides the commands: only from the owner, only in a state PackML allows them in; answers at once.",
        "Logic": "The PackML state machine.",
        "PubUa": "Writes Module/State to OPC UA.",
        "PubState": "Tells every block the module state, on the state channel.",
        "SubQuery": "Answers a block that asks for the state (at its start).",
        "SubAct": "Hears the skills say +1 when they start and -1 when they end.",
        "Count": "Counts the running skills: Stopping waits until none runs.",
        "Wd": "Gives up waiting for the skills to stop after StopTimeout: the module then aborts.",
    },
    "SKILL_Core": {
        "Gate": "Decides a client's Start, Stop, Abort and Reset and answers it; passes accepted ones, and the "
                "parent's commands, on to Control.",
        "Control": "The skill's state machine (SKILL_Control).",
        "Owner": "Knows who occupies the module: only the owner may command the skill over OPC UA.",
        "Mode": "Knows the module's state: a client may start the skill only in Execute; the skill stops when the "
                "module stops.",
        "UaStop": "The OPC UA method Stop(Session).",
        "UaAbort": "The OPC UA method Abort(Session).",
        "UaReset": "The OPC UA method Reset(Session).",
        "PubState": "Writes State and ErrorID to OPC UA.",
        "Act": "Says +1 when the skill starts and -1 when it ends, for the module's count of running skills.",
        "ToIdle": "Brings a succeeded skill back to Idle after 1.5 s.",
        "PubRelease": "When a run ends, says on the release channel that this skill gives up its equipment.",
    },
    "MOD_OwnerView": {"Latch": "Keeps the last owner heard.", "Listen": "Listens to the owner channel.",
                      "Query": "Asks for the owner once at start."},
    "MOD_StateView": {"Latch": "Keeps the last module state heard.", "Listen": "Listens to the module's state channel.",
                      "Query": "Asks for the state once at start."},
    "IO_": {"Route": "Picks the way to the signal from the Address and passes values that way.",
            "Line": "Sets up a Raspberry Pi line (GPIO) or PWM channel when the Address names one.",
            "Local": "Reads or writes a FORTE IO handle (IX, QX, IW, QW).",
            "Bus": "Reads or writes a Modbus register when the Address names one."},
}


def comment_type_network(name: str, net) -> None:
    """Give every block inside the composite type ``name`` its comment, if it has none."""
    table = INSIDE.get(name) or next((t for prefix, t in INSIDE.items() if prefix.endswith("_") and name.startswith(prefix)), {})
    for block in net.findall("FB"):
        if block.get("Comment"):
            continue
        what = table.get(block.get("Name"))
        if what is None:
            what = io_point(block, name) or parameter_block(block)
        if what:
            block.set("Comment", what)


def io_point(block, container: str) -> str | None:
    """An IO block inside an equipment block: which signal it is."""
    name = block.get("Name")
    match = re.match(r"(In|Out)_(\w+)$", name)
    if not match or not container.startswith("EQ_"):
        return None
    way = "reads the input" if match.group(1) == "In" else "switches the output"
    return f"The pin {match.group(2)}: {way} at {match.group(2)}_Address (a Pi pin, Modbus, or simulated)."


def parameter_block(block) -> str | None:
    match = re.match(r"Par_(\w+)$", block.get("Name"))
    if not match:
        return None
    return (f"The parameter {match.group(1)}: its default, the check of a client's value against its limits, and the "
            "value held for the run.")


# In the application: what each block of the module does there.

def comment_application(net, spec) -> None:
    """Give every block of a module's application (and of its subapplications) its comment."""
    root = f"/Objects/{spec.module}" if not getattr(spec, "opcua_root", None) else strip(spec.opcua_root)
    module = spec.module
    for block in net.findall("FB"):
        if not block.get("Comment"):
            block.set("Comment", top_level(block, spec, root, module))
    for sub in net.findall("SubApp"):
        inner = sub.find("SubAppNetwork")
        if inner is not None:
            comment_sequence(inner, sub.get("Name"), spec, root, [sub.get("Name")])


def params(block) -> dict[str, str]:
    return {p.get("Name"): strip(p.get("Value")) for p in block.findall("Parameter")}


def kind(block) -> str:
    return block.get("Type", "").split("::")[-1]


def top_level(block, spec, root: str, module: str) -> str:
    name, typ, given = block.get("Name"), kind(block), params(block)
    if typ == "MOD_Occupation":
        return (f"Who may command the module. A client calls Occupy(Session) at {root}/Occupation first; until it "
                f"calls Release, only commands with that session id are accepted. Every block hears the owner on "
                f"loc[{module}/owner].")
    if typ == "MOD_StateManager":
        return (f"The module's PackML state. The owner calls Reset, Start, Stop, Abort or Clear at {root}/Module; "
                f"State is at {root}/Module/State and on loc[{module}/state]. Reset runs the Resetting procedure, Stop "
                "the Stopping procedure; skills may be started only in Execute.")
    if typ.startswith("EQ_"):
        eq = spec.equipment.get(name)
        pins = ", ".join(f"{k[:-len('_Address')]} = {v}" for k, v in given.items() if k.endswith("_Address")) or "no pins"
        about = (eq.description if eq is not None and eq.description else name)
        return (f"Equipment {name}: {about}. The only block that touches its pins ({pins}). Skills send it what to "
                f"switch on loc[{module}/{name}/cmd]; it reports its inputs on loc[{module}/{name}/state] and at "
                f"{root}/Equipment/{name}.")
    if typ.startswith("SK_"):
        skill = typ[len("SK_"):]
        decl = spec.skills.get(skill)
        about = decl.description if decl is not None and decl.description else skill
        equipment = f", using {decl.equipment}" if decl is not None and decl.equipment else ""
        return (f"Skill {skill}, offered on its own: {about}{equipment}. A client calls Start (with the parameters), "
                f"Stop, Abort or Reset at {root}{given.get('UaPath', '')}; State, ErrorID, Parameters and Results "
                "are there too.")
    return ""


def comment_sequence(net, path: str, spec, root: str, trail: list[str]) -> None:
    """The blocks inside a module level skill, a sequence or a procedure (recursively)."""
    steps = [b for b in net.findall("FB") if kind(b).startswith("SK_")]
    wires = [(c.get("Source"), c.get("Destination")) for c in net.iterfind("DataConnections/Connection")]
    for block in net.findall("FB"):
        if block.get("Comment"):
            continue
        name, typ, given = block.get("Name"), kind(block), params(block)
        text = ""
        if typ.startswith("SK_"):
            n = steps.index(block) + 1
            skill = typ[len("SK_"):]
            constants = ", ".join(f"{k} = {v}" for k, v in given.items()
                                  if k not in ("Module", "UaRoot", "UaPath", "UaEnable", "Methods", "Holder", "ReleaseAfter"))
            whose = " / ".join(trail)
            # What the skill hands the step (a wire from the sequence's input) and what the step hands back.
            handed = [f"{d.split('.', 1)[1]} from {trail[0]}'s {s}" for s, d in wires
                      if d.startswith(f"{name}.") and "." not in s]
            back = [f"its {s.split('.', 1)[1][len('R_'):]} is {trail[0]}'s result" for s, d in wires
                    if s.startswith(f"{name}.R_") and "." not in d]
            text = (f"Step {n} of {whose}: runs the skill {skill}" + (f" with {constants}" if constants else "")
                    + (f"; {', '.join(handed)}" if handed else "") + (f"; {', '.join(back)}" if back else "")
                    + f". Its State and ErrorID are at {root}{given.get('UaPath', '')}; it keeps the equipment under "
                    f"the name {given.get('Holder', '')}.")
        elif typ == "SKILL_Core":
            text = (f"The state machine of the skill {trail[0]}: checks a client's Start (occupation, module in Execute, "
                    f"not running, values in range), publishes State and ErrorID at {root}{given.get('UaPath', '')}, "
                    "offers Stop, Abort and Reset there, starts Execute and runs Stop when the skill is stopped.")
        elif typ.startswith("SERVER_"):
            text = (f"The OPC UA method Start of {trail[0]}: a client's call (session id and parameters) arrives "
                    "here; the parameters are checked, then Control answers Accepted or an error code.")
        elif typ.startswith("SKILL_Param_"):
            limits = ", ".join(f"{k} {v}" for k, v in given.items() if k in ("Lower", "Upper"))
            text = (f"The parameter {name} of {trail[0]}: default {given.get('Default', '')}"
                    + (f" ({limits})" if limits else "") + "; checks a client's value, then holds it for the run "
                    "and hands it to the steps.")
        elif typ.startswith("PUBLISH_"):
            where = re.findall(r"WRITE;([^\]]+)", given.get("ID", ""))
            text = f"Writes {'the parameters' if 'Param' in name else 'the results'} of the run to OPC UA: " + \
                   (", ".join(where[0].split(";")) if where else "")
        elif typ == "SKILL_FailMerge":
            text = "Joins the failures of the steps into one (with its error code), so any step's failure ends the sequence."
        elif typ.startswith("SKILL_Join"):
            text = "Ends the steps that run side by side: done when all are done; halts the others when one fails."
        elif typ == "SKILL_Merge":
            text = "Where the two branches of the decision meet again."
        elif typ.startswith("SKILL_Condition_"):
            text = (f"Compares {given.get('Operand', 'a value')} {given.get('Operator', '')} {given.get('Expected', '')}"
                    " for the decision: YES or NO.")
        if text:
            block.set("Comment", text)
    for sub in net.findall("SubApp"):
        inner = sub.find("SubAppNetwork")
        if inner is not None:
            comment_sequence(inner, sub.get("Name"), spec, root, [*trail, sub.get("Name")])
