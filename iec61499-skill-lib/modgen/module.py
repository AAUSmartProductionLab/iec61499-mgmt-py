"""Module-specific types and system, generated from a module specification.

Equipment IO CFB ``EQ_<Name>`` (logic ``EL_<Name>``): owns its IO points (FORTE binds one FB per
IO point), runs commands from its local ``cmd`` channel as timed phases with break before make,
grants the equipment to one holder at a time, switches off when the module aborts, and publishes
its inputs and holder on its ``state`` channel and its inputs over OPC UA.

Skill primitive ``SK_<Name>``: the shared ``SKILL_Core`` (state machine, Stop/Abort/Reset, State),
the Start method with one ``SKILL_Param_<type>`` latch per parameter (range check, latching) and
the execution ``SL_<Name>`` (one equipment command until ``ensures`` or ``after``; contract,
timeout, lock), with OPC UA methods Start(Session, parameters...), Stop, Abort, Reset and
variables State, ErrorID, Parameters/*, Results/*.

Module level skill (composite): a subapp of the same library blocks, wired the same way, with the
OPC UA publishers and the equipment release, and the ``Execute``/``Stop`` subapps holding private
skill primitive instances in sequence. It needs no type of its own, so FORTE can create a new one
online.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from .fbxml import (STD, Basic, Composite, Project, Simple, SubNet, Wiring, arrange, connections, elem, fb, publish,
                    save, server, subapp, subscribe, wstr)
from .library import ERRORS, cat, lit, q, ua
from .spec import BACKENDS, Equipment, ModuleSpec, Output, Parameter, Skill, Step, ms, names

IO_TYPE = {("in", "BOOL"): "DI", ("in", "LREAL"): "AI", ("out", "BOOL"): "DO", ("out", "LREAL"): "AO"}
# GPIOChip BiasMode. FORTE 3.3.0 indexes {as is, disable, pull-up, pull-down} with an enum
# {None, PullUp, PullDown}, so the documented PullUp (1) only disables the bias.
BIAS = {"none": 0, "pull_up": 2, "pull_down": 3}


def tlit(duration: str) -> str:
    """IEC TIME literal of ``200ms`` or ``2s``."""
    return f"T#{ms(duration)}ms"


def num(value) -> str:
    """LREAL literal."""
    return repr(float(value))


def value_lit(value, typ: str) -> str:
    """IEC literal of a constant for a parameter of type ``typ``."""
    return Parameter(type=typ, default=value).literal() if typ != "BOOL" else ("TRUE" if value else "FALSE")


# --------------------------------------------------------------------------------------------
# Equipment IO (generic) and the equipment's commands (used inside the skills)
# --------------------------------------------------------------------------------------------

def message(eq: Equipment, prefix: str, enable: str) -> list[str]:
    """Variables of the equipment's command message after (Holder, Release): one value per output,
    then one enable per analog output (off is no signal at all, not the value 0)."""
    return [f"{prefix}{o}" for o in eq.outputs] + [f"{enable}{o}" for o, x in eq.outputs.items() if x.type == "LREAL"]


def targets_code(eq: Equipment) -> str:
    """ST computing the output values N_*/NE_* and the phase timing of (Command, Phase)."""
    outs = eq.outputs
    lines = [f"N_{o} := FALSE;" if x.type == "BOOL" else f"N_{o} := 0.0;\nNE_{o} := FALSE;" for o, x in outs.items()]
    lines.append("Timed := FALSE;\nPhaseDT := T#0ms;")

    def phase_code(phase, indent):
        pad = " " * indent
        body = []
        for o, v in phase.values().items():
            if outs[o].type == "BOOL":
                body.append(f"{pad}N_{o} := {'TRUE' if v else 'FALSE'};")
            else:
                body.append(f"{pad}N_{o} := {'Arg' if v == 'Arg' else num(v)};")
                body.append(f"{pad}NE_{o} := TRUE;")
        if phase.duration:
            body += [f"{pad}PhaseDT := {tlit(phase.duration)};", f"{pad}Timed := TRUE;"]
        return body

    first = True
    # Command 0 is all off, like any command whose phases set nothing and take no time.
    active = [(c, st) for c, st in list(eq.commands.items())[1:] if any(ph.values() or ph.duration for ph in st)]
    for cmd, steps in active:
        lines.append(f"{'IF' if first else 'ELSIF'} Command = {eq.code(cmd)} THEN")
        first = False
        if len(steps) == 1:
            lines += phase_code(steps[0], 2)
        else:
            for i, phase in enumerate(steps):
                head = "IF" if i == 0 else ("ELSE" if i == len(steps) - 1 else "ELSIF")
                lines.append(f"  {head} Phase = {i} THEN" if head != "ELSE" else "  ELSE")
                lines += phase_code(phase, 4)
            lines.append("  END_IF;")
    if not first:
        lines.append("END_IF;")
    return "\n".join(line for line in lines if line.strip())


def takes_arg(eq: Equipment) -> bool:
    """A command of the equipment passes its argument to an output (``Angle: Arg``)."""
    return any(v == "Arg" for steps in eq.commands.values() for phase in steps for v in phase.values().values())


def make_equipment_commands(p: Project, pkg: str, name: str, eq: Equipment):
    """EC_<name>: what the equipment's commands mean, for the skills that drive it.

    PLAY(Holder, Command, Arg, Release) sends the command's output values to the equipment, phase
    by phase (a start boost, a brake pulse); the release goes with the last phase, and PLAYED
    follows it. A new PLAY replaces the command being played.
    """
    values = message(eq, "N_", "NE_")
    arg = ["Arg"] if takes_arg(eq) else []
    types = {**{f"N_{o}": x.type for o, x in eq.outputs.items()}, **{v: "BOOL" for v in values if v.startswith("NE_")}}
    b = Basic(p, pkg, f"EC_{name}", f"Commands of {name} as output values, in timed phases: "
              + ", ".join(f"{k}={eq.code(k)}" for k in eq.commands),
              {"PLAY": ["Holder", "Command", *arg, "Release"], "PHASE_T": []},
              {"OUT": ["O_Holder", "O_Release", *values], "PHASE_START": ["PhaseDT"], "PHASE_STOP": [], "PLAYED": []},
              {"Holder": "WSTRING", "Command": "USINT", **{a: "LREAL" for a in arg}, "Release": "BOOL"},
              {"O_Holder": "WSTRING", "O_Release": "BOOL", **types, "PhaseDT": "TIME"},
              {"Phase": "USINT", "Timed": "BOOL"}, folder="Equipment/Commands")
    b.state("START")
    b.state("Play", "Phase := 0;", "PHASE_STOP")
    b.state("Next", "Phase := Phase + 1;")
    b.state("Send", targets_code(eq) + "\nO_Holder := Holder;\nO_Release := Release AND NOT Timed;", "OUT")
    b.state("Hold", None, "PHASE_START")
    b.state("Played", None, "PLAYED")
    b.trans("START", "Play", "PLAY")
    b.trans("START", "Next", "PHASE_T")
    b.trans("Play", "Send", "1")
    b.trans("Next", "Send", "1")
    b.trans("Send", "Hold", "Timed")
    b.trans("Send", "Played", "1")
    b.trans("Hold", "START", "1")
    b.trans("Played", "START", "1")
    b.write()


def make_equipment(p: Project, pkg: str, name: str, eq: Equipment):
    """EQ_<name> and its logic EL_<name>: the equipment's IO points and nothing about what they mean.

    It writes the output values its holder sends (break before make), reads the inputs every cycle
    and reports them when they change, lets one holder at a time write, and switches everything
    off when the holder gives up or the module aborts.
    """
    ins, outs = eq.inputs, eq.outputs
    bools = [o for o, x in outs.items() if x.type == "BOOL"]
    reals = [o for o, x in outs.items() if x.type == "LREAL"]
    received, wanted = message(eq, "C_", "CE_"), message(eq, "N_", "NE_")
    drive = message(eq, "O_", "E_")
    types = [x.type for x in outs.values()] + ["BOOL"] * len(reals)
    pub = []
    for i, s in enumerate(ins):
        pub += ["UaRoot", lit("/Equipment/"), "Name", lit(f"/{s}" + (";" if i < len(ins) - 1 else ""))]
    b = Basic(p, pkg, f"EL_{name}",
              f"{name}: output values from its holder -> outputs (break before make); one holder at a time; "
              "all off on release or when the module aborts; inputs -> state channel when they change",
              {"INIT": (["Module", "Name", *(["UaRoot"] if ins else [])], "EInit"),
               "CMD": ["C_Holder", "C_Release", *received], "RELEASE": ["R_Holder"],
               "SAMPLE": [f"I_{s}" for s in ins], "REFRESH": [], "DRIVEN": [], "MOD_CHG": ["ModState"]},
              {"INITO": (["IdCmd", "IdRelease", "IdState", "IdPub"], "EInit"), "DRIVE": drive,
               "STATE": [*ins, "Holder"]},
              {"Module": "WSTRING", "Name": "WSTRING", **({"UaRoot": "WSTRING"} if ins else {}),
               "C_Holder": "WSTRING", "C_Release": "BOOL", **dict(zip(received, types)), "R_Holder": "WSTRING",
               **{f"I_{s}": i.type for s, i in ins.items()}, "ModState": "USINT"},
              {"IdCmd": "WSTRING", "IdRelease": "WSTRING", "IdState": "WSTRING", "IdPub": "WSTRING",
               **dict(zip(drive, types)), **{s: i.type for s, i in ins.items()}, "Holder": "WSTRING"},
              {"Publish": "BOOL", "Beat": "USINT", "LastHolder": "WSTRING", "Pending": "BOOL", "OffPending": "BOOL",
               **{f"L_{s}": i.type for s, i in ins.items()}, **dict(zip(wanted, types))},
              folder="Equipment/Base")
    channel = lambda part: cat(lit("loc["), "Module", lit("/"), "Name", lit(f"/{part}]"))  # noqa: E731
    free = '(Holder = "") OR (C_Holder = Holder)'
    off = "(ModState = 8) OR (ModState = 9)"                                  # the module Aborting or Aborted
    b.state("START")
    b.state("Init", f"IdCmd := {channel('cmd')};\nIdRelease := {channel('release')};\nIdState := {channel('state')};\n"
                    + (f"IdPub := {ua('WRITE', *pub)};" if ins else 'IdPub := "";'), "INITO")
    # The state is published only when an input or the holder changed, and every 20 samples as a
    # heartbeat (for skills added online): every Modbus poll delivers a sample, and publishing each
    # to every skill overran FORTE's external event queue.
    changed = " OR ".join([*[f"({s} <> L_{s})" for s in ins], "(Holder <> LastHolder)", "(Beat >= 20)"])
    b.state("Sample", "\n".join([*[f"{s} := I_{s};" for s in ins], f"Publish := {changed};", "Beat := Beat + 1;"]))
    b.state("Publish", "\n".join([*[f"L_{s} := {s};" for s in ins], "LastHolder := Holder;", "Beat := 0;"]), "STATE")
    # Like a PLC scan, the output image is rewritten every cycle: FORTE's Modbus client drops a
    # write sent while it is not connected, and a cyclic write heals that and reconnects.
    b.state("Refresh", None, "DRIVE")
    b.state("Cmd", "\n".join(["Holder := C_Holder;", *[f"{n} := {c};" for n, c in zip(wanted, received)],
                              'IF C_Release THEN\n  Holder := "";\nEND_IF;']))
    b.state("Off", "\n".join([*[f"{n} := {'FALSE' if t == 'BOOL' else '0.0'};" for n, t in zip(wanted, types)],
                              'Holder := "";', "OffPending := FALSE;"]))
    # Outputs that stay on are kept, all others switched off first; then the new set is switched on.
    b.state("Break", "\n".join(f"O_{o} := O_{o} AND N_{o};" for o in bools) or None, "DRIVE")
    b.state("Make", "\n".join(f"{o} := {n};" for o, n in zip(drive, wanted)) or None, "DRIVE")
    b.state("BreakW")
    b.state("MakeW")
    # A message arriving while the outputs are written would be dropped (no transition for it
    # there); it is marked and handled once the outputs are settled. A command's data (C_*) is the
    # latest message, which is the one that counts.
    for w in ["B", "M"]:
        b.state(f"Queue{w}", "Pending := TRUE;")
        b.state(f"Off{w}", "OffPending := TRUE;")
    b.state("CmdPend", "Pending := FALSE;")
    b.state("Settled")
    b.state("Report", "LastHolder := Holder;\nBeat := 0;", "STATE")
    b.trans("START", "Init", "INIT")
    b.trans("START", "Sample", "SAMPLE")
    b.trans("START", "Refresh", "REFRESH")
    b.trans("START", "Cmd", f"CMD[{free}]")
    b.trans("START", "Off", 'RELEASE[(R_Holder = Holder) AND (Holder <> "")]')
    b.trans("START", "Off", f"MOD_CHG[{off}]")
    b.trans("Init", "START", "1")
    b.trans("Sample", "Publish", "Publish")
    b.trans("Sample", "START", "1")
    b.trans("Publish", "START", "1")
    b.trans("Refresh", "START", "1")
    b.trans("Cmd", "Break", "1")
    b.trans("Off", "Break", "1")
    b.trans("Break", "BreakW", "1")
    b.trans("BreakW", "Make", "DRIVEN")
    b.trans("Make", "MakeW", "1")
    b.trans("MakeW", "Settled", "DRIVEN")
    for w, wait in [("B", "BreakW"), ("M", "MakeW")]:
        b.trans(wait, f"Queue{w}", "CMD")
        b.trans(wait, f"Off{w}", 'RELEASE[(R_Holder = Holder) AND (Holder <> "")]')
        b.trans(wait, f"Off{w}", f"MOD_CHG[{off}]")
        b.trans(f"Queue{w}", wait, "1")
        b.trans(f"Off{w}", wait, "1")
    b.trans("Settled", "Off", "OffPending")
    b.trans("Settled", "CmdPend", "Pending")
    b.trans("CmdPend", "Cmd", free)
    b.trans("CmdPend", "Report", "1")
    b.trans("Settled", "Report", "1")
    b.trans("Report", "START", "1")
    b.write()

    iv = {"Module": "WSTRING", "Name": ("WSTRING", wstr(name)), "UaRoot": "WSTRING", "UaEnable": "BOOL",
          "CycleTime": ("TIME", "T#50ms")}
    # Per IO point: backend (0 simulated, 1 local IO handle, 2 Modbus), Modbus ID, IO handle name.
    for s, i in ins.items():
        iv[f"{s}_Backend"], iv[f"{s}_Modbus"], iv[f"{s}_Io"] = ("USINT", "2"), "WSTRING", "STRING"
        iv[f"{s}_Sim"] = (i.type, ("TRUE" if i.sim else "FALSE") if i.type == "BOOL" else num(i.sim))
        if i.type == "LREAL":
            iv[f"{s}_Scale"] = ("LREAL", num(i.scale))
    for o, x in outs.items():
        iv[f"{o}_Backend"], iv[f"{o}_Modbus"], iv[f"{o}_Io"] = ("USINT", "2"), "WSTRING", "STRING"
        if x.type == "LREAL":
            iv[f"{o}_Gain"], iv[f"{o}_Bias"] = ("LREAL", num(x.gain)), ("LREAL", num(x.bias))
    c = Composite(p, pkg, f"EQ_{name}", (eq.description or name) + "; equipment IO: owns its IO points, writes the "
                  "output values its holder sends, reads its inputs every cycle and reports changes",
                  {"INIT": (list(iv), "EInit")}, {"INITO": ([], "EInit")}, iv, {}, folder="Equipment")
    reads, writes = [f"In_{s}" for s in ins], [f"Out_{o}" for o in outs]
    c.fb("Logic", f"{pkg}::EL_{name}")
    c.fb("Cycle", STD["E_CYCLE"])
    c.fb("Mode", q("MOD_StateView"))
    c.fb("SubCmd", subscribe(2 + len(received)), QI="TRUE")
    c.fb("SubRelease", subscribe(1), QI="TRUE")
    c.fb("PubState", publish(len(ins) + 1), QI="TRUE")
    if ins:
        c.fb("PubUa", publish(len(ins)))
    for s, i in ins.items():
        c.fb(f"In_{s}", q("IO_" + IO_TYPE[("in", i.type)]))
    for o, x in outs.items():
        c.fb(f"Out_{o}", q("IO_" + IO_TYPE[("out", x.type)]))
    c.group("Core", "One holder at a time, break before make, all off on release or abort; scanned every CycleTime",
            ["Logic", "Cycle"], dx=7500, dy=1800 + 260 * max(len(received) + len(ins) + 8, len(drive) + len(ins) + 6))
    c.group("Channels", "Local channels to and from the skills (cmd, release, state), the module's state, and the "
            "inputs over OPC UA", ["SubCmd", "SubRelease", "PubState", "PubUa", "Mode"],
            dy=1800 + 260 * (len(received) + 6))
    c.group("Inputs", "The equipment's sensors: read every cycle, one block per IO point", reads, dy=3800)
    c.group("Outputs", "The equipment's actuators: written on a change and every cycle, one block per IO point",
            writes, dy=3800)
    c.chain("INIT", ["Logic", "Mode", "SubCmd", "SubRelease", "PubState", *(["PubUa"] if ins else []), *reads, *writes],
            ["Cycle.START", "INITO"])
    for v in ["Module", "Name", *(["UaRoot"] if ins else [])]:
        c.da(v, "Logic." + v)
    c.da("Module", "Mode.Module")
    c.da("Logic.IdCmd", "SubCmd.ID")
    c.da("Logic.IdRelease", "SubRelease.ID")
    c.da("Logic.IdState", "PubState.ID")
    if ins:
        c.da("Logic.IdPub", "PubUa.ID")
        c.da("UaEnable", "PubUa.QI")
    c.da("CycleTime", "Cycle.DT")
    c.ev("SubCmd.IND", "Logic.CMD")
    for k, v in enumerate(["C_Holder", "C_Release", *received], 1):
        c.da(f"SubCmd.RD_{k}", f"Logic.{v}")
    c.ev("SubRelease.IND", "Logic.RELEASE")
    c.da("SubRelease.RD_1", "Logic.R_Holder")
    c.ev("Mode.CHG", "Logic.MOD_CHG")
    c.da("Mode.State", "Logic.ModState")
    c.ev("Cycle.EO", "Logic.REFRESH")
    if reads:
        c.ev("Cycle.EO", reads[0] + ".REQ")
        for a, z in zip(reads, reads[1:]):
            c.ev(a + ".CNF", z + ".REQ")
        c.ev(reads[-1] + ".CNF", "Logic.SAMPLE")
    else:
        c.ev("Cycle.EO", "Logic.SAMPLE")
    for k, (s, i) in enumerate(ins.items(), 1):
        for v, pin in [("Backend", "Backend"), ("Modbus", "ModbusId"), ("Io", "IoName"), ("Sim", "SimValue")]:
            c.da(f"{s}_{v}", f"In_{s}.{pin}")
        if i.type == "LREAL":
            c.da(f"{s}_Scale", f"In_{s}.Scale")
        c.da(f"In_{s}.IN", f"Logic.I_{s}")
        c.da(f"Logic.{s}", f"PubState.SD_{k}", f"PubUa.SD_{k}")
    c.da("Logic.Holder", f"PubState.SD_{len(ins) + 1}")
    c.ev("Logic.STATE", "PubState.REQ", *(["PubUa.REQ"] if ins else []))
    if writes:
        c.ev("Logic.DRIVE", writes[0] + ".REQ")
        for a, z in zip(writes, writes[1:]):
            c.ev(a + ".CNF", z + ".REQ")
        c.ev(writes[-1] + ".CNF", "Logic.DRIVEN")
    else:
        c.ev("Logic.DRIVE", "Logic.DRIVEN")
    for o, x in outs.items():
        for v, pin in [("Backend", "Backend"), ("Modbus", "ModbusId"), ("Io", "IoName")]:
            c.da(f"{o}_{v}", f"Out_{o}.{pin}")
        c.da(f"Logic.O_{o}", f"Out_{o}.OUT")
        if x.type == "LREAL":
            c.da(f"Logic.E_{o}", f"Out_{o}.EN")
            c.da(f"{o}_Gain", f"Out_{o}.Gain")
            c.da(f"{o}_Bias", f"Out_{o}.Bias")
    c.write()


# --------------------------------------------------------------------------------------------
# Skill primitives and module level skills
# --------------------------------------------------------------------------------------------

def described(params: dict[str, Parameter]) -> str:
    """Parameters for a type comment: name [unit] range, default."""
    return "; ".join(f"{n} [{pr.unit or '-'}] {pr.minimum}..{pr.maximum}, default {pr.default}"
                     for n, pr in params.items()) or "none"


def published(base: str, folder: str, names) -> str:
    """ST expression of the OPC UA ID that publishes ``names`` below ``<base>/<folder>/``."""
    names, terms = list(names), []
    for i, n in enumerate(names):
        terms += [base, lit(f"/{folder}/{n}" + (";" if i < len(names) - 1 else ""))]
    return ua("WRITE", *terms)


def ua_literal(kind: str, paths) -> str:
    """The same as a WSTRING literal, for the ID of an instance in the application."""
    return wstr(f"opc_ua[{kind};{';'.join(paths)}]")


def used_inputs(skill: Skill, eq: Equipment | None) -> list[str]:
    """Equipment inputs a skill primitive reads (contract, end condition, argument, results)."""
    if eq is None:
        return []
    words = set()
    for expr in [skill.requires, skill.ensures, skill.invariant, skill.arg]:
        if isinstance(expr, str):
            words |= names(expr)
    words |= set(skill.results.values())
    return [s for s in eq.inputs if s in words]


def make_equipment_view(p: Project, pkg: str, name: str, eq: Equipment):
    """EV_<name>: types the equipment's state channel for the skills (a subscriber's ANY outputs
    must end on typed pins) and lets each skill take only the inputs it uses."""
    ins = eq.inputs
    Simple(p, pkg, f"EV_{name}", f"Typed view of {name}'s state channel (inputs and holder)",
           {"REQ": [*[f"I_{s}" for s in ins], "I_Holder"]}, {"CNF": [*ins, "Holder"]},
           {**{f"I_{s}": i.type for s, i in ins.items()}, "I_Holder": "WSTRING"},
           {**{s: i.type for s, i in ins.items()}, "Holder": "WSTRING"},
           {"REQ": ("\n".join([*[f"{s} := I_{s};" for s in ins], "Holder := I_Holder;"]), "CNF")},
           folder="Equipment/Base").write()


def make_skill_logic(p: Project, pkg: str, name: str, skill: Skill, eq: Equipment | None):
    """SL_<name>: executes one run of a skill primitive; at INIT it names its channels and the OPC UA
    variables of its parameters and results."""
    params, e = skill.parameters, ERRORS
    ins = eq.inputs if eq else {}
    drive = eq.code(skill.command) if eq else None
    stop = eq.code(skill.stop) if eq and skill.stop else 0
    timed = skill.after is not None
    after = skill.after if isinstance(skill.after, str) else num(skill.after or 0)
    has_eq = eq is not None
    used = used_inputs(skill, eq)
    ids = [*(["IdEqState", "IdEqCmd"] if has_eq else []), *(["IdParams"] if params else []),
           *(["IdResults"] if skill.results else [])]
    init = ((["Module", "Equipment", "Token", "LastUse"] if has_eq else []) + ([] if timed else ["Timeout"])
            + (["UaRoot", "UaPath"] if params or skill.results else []))
    ei = {"INIT": (init, "EInit"), "START": list(params), "HALT": [], "ABORT": [], "TIMER": []}
    eo = {"INITO": (ids, "EInit"), "DONE": [f"R_{r}" for r in skill.results],
          "FAILED": ["ErrorID"], "HALTED": ["ErrorID"], "TIMER_START": ["TimerDT"], "TIMER_STOP": []}
    types = {"Module": "WSTRING", "Equipment": "WSTRING", "Token": "WSTRING", "LastUse": "BOOL", "Timeout": "TIME",
             "UaRoot": "WSTRING", "UaPath": "WSTRING"}
    iv = {**{v: types[v] for v in init}, **{n: pr.type for n, pr in params.items()}}
    ov = {"ErrorID": "UINT", "TimerDT": "TIME", **{f"R_{r}": ins[src].type for r, src in skill.results.items()},
          **{i: "WSTRING" for i in ids}}
    if has_eq:
        # Only the inputs the skill uses (the equipment view EV_ receives the whole state channel).
        ei["SAMPLE"] = [*used, "Holder"]
        ei["WAIT_OVER"] = []
        ei["PLAYED"] = []
        eo["WAIT_START"], eo["WAIT_STOP"] = [], []
        eo["CMD"] = ["C_Holder", "C_Command", "C_Arg", "C_Release"]
        eo["EQ_FREE"] = ["EqFree"]
        iv.update({**{s: ins[s].type for s in used}, "Holder": "WSTRING"})
        ov.update({"C_Holder": "WSTRING", "C_Command": "USINT", "C_Arg": "LREAL", "C_Release": "BOOL", "EqFree": "BOOL"})
    what = (f"holds {skill.equipment}.{skill.command} until {skill.ensures or f'{after} s'}" if has_eq
            else f"waits {after} s")
    b = Basic(p, pkg, f"SL_{name}", f"{name}: Requires {skill.requires}; {what}; Invariant {skill.invariant}",
              ei, eo, iv, ov, {"Outcome": "USINT"} if has_eq else None, folder="Skills/Logic")

    # The final command releases the equipment when this is the last step using it (LastUse), in
    # the same message: a separate release could overwrite the stop on the local channel.
    def cmd(code, release="LastUse"):
        return f"C_Holder := Token;\nC_Command := {code};\nC_Arg := {arg};\nC_Release := {release};"

    arg = (skill.arg if isinstance(skill.arg, str) else num(skill.arg)) if skill.arg is not None else "0.0"
    busy = '(Holder <> "") AND (Holder <> Token)'
    base = cat("UaRoot", "UaPath")
    init_code = []
    if has_eq:
        init_code += [f"IdEqState := {cat(lit('loc['), 'Module', lit('/'), 'Equipment', lit('/state]'))};",
                      f"IdEqCmd := {cat(lit('loc['), 'Module', lit('/'), 'Equipment', lit('/cmd]'))};"]
    if params:
        init_code.append(f"IdParams := {published(base, 'Parameters', params)};")
    if skill.results:
        init_code.append(f"IdResults := {published(base, 'Results', skill.results)};")
    b.state("Idle")
    b.state("Init", "\n".join(init_code) or None, "INITO")
    b.state("Check")
    b.state("Reject", f"ErrorID := {e['PreconditionViolated']};", "FAILED")
    results = "\n".join(f"R_{r} := {src};" for r, src in skill.results.items())
    timer = f"TimerDT := MUL_TIME(T#1s, {after});" if timed else "TimerDT := Timeout;"
    if has_eq:
        b.state("Sample", 'EqFree := (Holder = "") OR (Holder = Token);', "EQ_FREE")
        b.state("Busy", f"ErrorID := {e['Busy']};", "FAILED")
        # Another holder: wait up to 0.5 s for the equipment's next state (a release in flight, e.g.
        # from the previous step or a skill that just stopped) before failing with Busy.
        b.state("WaitFree", None, "WAIT_START")
        b.state("WaitW")
        b.state("Recheck", None, "WAIT_STOP")
        if not timed:
            b.state("AlreadyDone", results or None, "DONE")
        b.state("Run", cmd(drive, "FALSE") + "\n" + timer, "CMD", ["TIMER_START"])
        b.state("RunSample", 'EqFree := (Holder = "") OR (Holder = Token);', "EQ_FREE")
        # A final command may take time (a brake pulse): the run ends when it has been played, and
        # Outcome says how (1 done, 2 failed, 3 halted, 0 aborted: nothing to report).
        b.state("Unsafe", cmd(0) + f"\nErrorID := {e['InvariantViolated']};\nOutcome := 2;", "CMD", ["TIMER_STOP"])
        b.state("Lost", f"ErrorID := {e['Busy']};", "TIMER_STOP", ["FAILED"])
        b.state("Done", cmd(stop) + ("\n" + results if results else "") + "\nOutcome := 1;", "CMD", ["TIMER_STOP"])
        if not timed:
            b.state("TimedOut", cmd(0) + f"\nErrorID := {e['Timeout']};\nOutcome := 2;", "CMD")
        b.state("Halt", cmd(stop) + f"\nErrorID := {e['Interrupted']};\nOutcome := 3;", "CMD", ["TIMER_STOP"])
        b.state("Abort", cmd(0) + "\nOutcome := 0;", "CMD", ["TIMER_STOP"])
        b.state("Ending")
        b.state("EndDone", None, "DONE")
        b.state("EndFailed", None, "FAILED")
        b.state("EndHalted", None, "HALTED")
    else:
        b.state("Run", timer, "TIMER_START")
        b.state("Done", None, "DONE")
        b.state("Halt", f"ErrorID := {e['Interrupted']};", "TIMER_STOP", ["HALTED"])
        b.state("Abort", None, "TIMER_STOP")
    b.state("Running")
    b.trans("Idle", "Init", "INIT")
    b.trans("Init", "Idle", "1")
    b.trans("Idle", "Check", "START")
    b.trans("Check", "Reject", f"NOT ({skill.requires})")
    if has_eq:
        b.trans("Idle", "Sample", "SAMPLE")
        b.trans("Sample", "Idle", "1")
        b.trans("Check", "WaitFree", busy)
        b.trans("WaitFree", "WaitW", "1")
        b.trans("WaitW", "Recheck", f'SAMPLE[NOT ({busy})]')
        b.trans("WaitW", "Busy", "WAIT_OVER")
        b.trans("WaitW", "Idle", "HALT")
        b.trans("WaitW", "Idle", "ABORT")
        b.trans("Recheck", "Check", "1")
        if not timed:
            b.trans("Check", "AlreadyDone", skill.ensures)   # already there: succeed without driving
        b.trans("Running", "Unsafe", f"SAMPLE[NOT ({skill.invariant})]")
        b.trans("Running", "Lost", f"SAMPLE[{busy}]")
        if not timed:
            b.trans("Running", "Done", f"SAMPLE[{skill.ensures}]")
            b.trans("Running", "TimedOut", "TIMER")
        else:
            b.trans("Running", "Done", "TIMER")
        b.trans("Running", "RunSample", "SAMPLE")
        b.trans("RunSample", "Running", "1")
        for s in ["Busy", "Lost", *([] if timed else ["AlreadyDone"])]:
            b.trans(s, "Idle", "1")
        for s in ["Unsafe", "Done", "Halt", "Abort", *([] if timed else ["TimedOut"])]:
            b.trans(s, "Ending", "1")
        b.trans("Ending", "EndDone", "PLAYED[Outcome = 1]")
        b.trans("Ending", "EndFailed", "PLAYED[Outcome = 2]")
        b.trans("Ending", "EndHalted", "PLAYED[Outcome = 3]")
        b.trans("Ending", "Idle", "PLAYED")
        b.trans("Ending", "Abort", "ABORT")
        for s in ["EndDone", "EndFailed", "EndHalted"]:
            b.trans(s, "Idle", "1")
    else:
        b.trans("Running", "Done", "TIMER")
        for s in ["Done", "Halt", "Abort"]:
            b.trans(s, "Idle", "1")
    b.trans("Check", "Run", "1")
    b.trans("Run", "Running", "1")
    b.trans("Running", "Halt", "HALT")
    b.trans("Running", "Abort", "ABORT")
    b.trans("Reject", "Idle", "1")
    b.write()


def start_method(n: Wiring, params: dict[str, Parameter], latches: dict[str, str], start: dict,
                 publish_params: dict, defaults: bool) -> tuple[list[str], str]:
    """The Start method of a skill whose core is the instance ``Control`` (SKILL_Core) in ``n``.

    UaStart (Start(Session, parameters...)): each parameter latch checks its argument and passes
    the result on, the last one to Control.CMD_START. Control.GO latches the arguments (or the
    defaults, for a start from a parent) one after the other and PubParams publishes them.
    ``latches``: parameter -> latch instance; ``start``, ``publish_params``: parameter values of
    UaStart and PubParams; ``defaults``: the latches get the default as a value (else the caller
    wires it). Returns the INIT chain after Control and the event that fires once the values are
    latched.
    """
    n.fb("UaStart", server(2, 1 + len(params)), **start)
    n.da("Control.IdStart", "UaStart.ID")
    n.da("UaStart.RD_1", "Control.S_Start")
    n.ev("Control.RSP_START", "UaStart.RSP")
    n.da("Control.Accepted", "UaStart.SD_1")
    n.da("Control.RspError", "UaStart.SD_2")
    if not params:
        n.ev("UaStart.IND", "Control.CMD_START")
        return ["UaStart"], "Control.GO"
    chain = [latches[x] for x in params]
    for k, (x, pr) in enumerate(params.items()):
        bounds = {v: pr.literal(b) for v, b in (("Lower", pr.minimum), ("Upper", pr.maximum)) if b is not None}
        n.fb(chain[k], q(f"SKILL_Param_{pr.type}"), **({"Default": pr.literal()} if defaults else {}), **bounds)
        n.da(f"UaStart.RD_{k + 2}", f"{chain[k]}.S")
        n.da("Control.FromUa", f"{chain[k]}.FromUa")
        n.da(f"{chain[k]}.P", f"PubParams.SD_{k + 1}")
    n.fb("PubParams", publish(len(params)), **publish_params)
    n.ev("UaStart.IND", chain[0] + ".CHECK")
    n.ev("Control.GO", chain[0] + ".LATCH")
    for a, z in zip(chain, chain[1:]):
        n.ev(a + ".CHECKED", z + ".CHECK")
        n.da(a + ".InRange", z + ".OkIn")
        n.ev(a + ".LATCHED", z + ".LATCH")
    n.ev(chain[-1] + ".CHECKED", "Control.CMD_START")
    n.da(chain[-1] + ".InRange", "Control.InRange")
    n.ev(chain[-1] + ".LATCHED", "PubParams.REQ")
    n.ev("PubParams.INITO", "PubParams.REQ")           # publishes the defaults once
    return ["UaStart", *chain, "PubParams"], chain[-1] + ".LATCHED"


def make_skill(p: Project, pkg: str, name: str, skill: Skill, eq: Equipment | None):
    """SK_<name>: skill primitive CFB: SKILL_Core, the Start method with the parameter latches and the
    execution SL_<name> with its equipment channels and timers."""
    params, results = skill.parameters, list(skill.results)
    make_skill_logic(p, pkg, name, skill, eq)
    iv = {"Module": "WSTRING", "UaRoot": "WSTRING", "UaPath": "WSTRING", "UaEnable": "BOOL", "Methods": "BOOL",
          "Token": "WSTRING", "LastUse": ("BOOL", "TRUE"),
          **({"Timeout": ("TIME", tlit(skill.timeout))} if skill.ensures is not None else {}),
          **{n: (pr.type, pr.literal()) for n, pr in params.items()}}
    ins = eq.inputs if eq else {}
    sent = message(eq, "N_", "NE_") if eq else []
    ov = {"State": "USINT", "ErrorID": "UINT", **{f"R_{r}": ins[s].type for r, s in skill.results.items()}}
    c = Composite(p, pkg, f"SK_{name}", f"Skill primitive {name}: {skill.description or name} (parameters: "
                  f"{described(params)}). OPC UA Start(Session, parameters...)/Stop/Abort/Reset(Session) -> "
                  "[Accepted, ErrorID]; START/HALT/ABORT/RESET from a parent -> SUCCESS or FAILURE(ErrorID)",
                  {"INIT": (list(iv), "EInit"), "START": list(params), "HALT": [], "ABORT": [], "RESET": []},
                  {"INITO": ([], "EInit"), "SUCCESS": [f"R_{r}" for r in results], "FAILURE": ["ErrorID"]},
                  iv, ov, folder="Skills")
    c.fb("Control", q("SKILL_Core"))
    c.fb("Logic", f"{pkg}::SL_{name}", **({"Equipment": wstr(skill.equipment)} if eq else {}))
    start, go = start_method(c, params, {x: f"Par_{x}" for x in params}, {}, {}, defaults=False)
    if results:
        c.fb("PubResults", publish(len(results)))
    if eq:
        c.fb("EqState", subscribe(len(ins) + 1), QI="TRUE")
        c.fb("EqView", f"{pkg}::EV_{skill.equipment}")
        c.fb("WaitT", STD["E_DELAY"], DT="T#500ms")      # how long a step waits for another holder's release
        c.fb("Driver", f"{pkg}::EC_{skill.equipment}")   # what the skill's commands mean for this equipment
        c.fb("PhaseT", STD["E_DELAY"])
        c.fb("EqCmd", publish(2 + len(sent)), QI="TRUE")
    c.fb("Timer", STD["E_DELAY"])
    # Logic names the OPC UA variables before PubParams and PubResults initialise.
    c.chain("INIT", ["Control", "Logic", *start, *(["PubResults"] if results else []),
                     *(["EqState", "EqCmd"] if eq else [])], "INITO")
    for v in ["Module", "UaRoot", "UaPath", "UaEnable", "Methods"]:
        c.da(v, f"Control.{v}")
    c.da("Methods", "UaStart.QI")
    for ev in ["START", "HALT", "ABORT", "RESET"]:
        c.ev(ev, f"Control.{ev}")
    c.ev("Control.SUCCESS", "SUCCESS")
    c.ev("Control.FAILURE", "FAILURE")
    c.da("Control.State", "State")
    c.da("Control.ErrorID", "ErrorID")
    if eq:
        for v in ["Module", "Token", "LastUse"]:
            c.da(v, f"Logic.{v}")
    if params or results:
        c.da("UaRoot", "Logic.UaRoot")
        c.da("UaPath", "Logic.UaPath")
    if skill.ensures is not None:
        c.da("Timeout", "Logic.Timeout")
    if params:
        c.da("UaEnable", "PubParams.QI")
        c.da("Logic.IdParams", "PubParams.ID")
        for x in params:
            c.da(x, f"Par_{x}.Default")
            c.da(f"Par_{x}.P", f"Logic.{x}")
    c.ev(go, "Logic.START")
    if results:
        c.da("UaEnable", "PubResults.QI")
        c.da("Logic.IdResults", "PubResults.ID")
        c.ev("Logic.DONE", "PubResults.REQ")
        for k, r in enumerate(results, 1):
            c.da(f"Logic.R_{r}", f"PubResults.SD_{k}", f"R_{r}")
    c.ev("Control.HALT_O", "Logic.HALT")
    c.ev("Control.ABORT_O", "Logic.ABORT")
    c.ev("Control.RUN_STOP", "Control.STOP_DONE")          # a primitive has no stop procedure
    c.ev("Logic.DONE", "Control.EXEC_DONE")
    c.ev("Logic.FAILED", "Control.EXEC_FAILED")
    c.ev("Logic.HALTED", "Control.EXEC_FAILED")
    c.da("Logic.ErrorID", "Control.ExecError")
    if eq:
        c.da("Logic.EqFree", "Control.EqFree")
        c.da("Logic.IdEqState", "EqState.ID")
        c.ev("EqState.IND", "EqView.REQ")
        for k, s in enumerate([*ins, "Holder"], 1):
            c.da(f"EqState.RD_{k}", f"EqView.I_{s}")
        c.ev("EqView.CNF", "Logic.SAMPLE")
        for s in [*used_inputs(skill, eq), "Holder"]:
            c.da(f"EqView.{s}", f"Logic.{s}")
        c.da("Logic.IdEqCmd", "EqCmd.ID")
        c.ev("Logic.CMD", "Driver.PLAY")
        for v in ["Holder", "Command", *(["Arg"] if takes_arg(eq) else []), "Release"]:
            c.da(f"Logic.C_{v}", f"Driver.{v}")
        c.ev("Driver.OUT", "EqCmd.REQ")
        for k, v in enumerate(["O_Holder", "O_Release", *sent], 1):
            c.da(f"Driver.{v}", f"EqCmd.SD_{k}")
        c.ev("Driver.PHASE_START", "PhaseT.START")
        c.da("Driver.PhaseDT", "PhaseT.DT")
        c.ev("Driver.PHASE_STOP", "PhaseT.STOP")
        c.ev("PhaseT.EO", "Driver.PHASE_T")
        c.ev("Driver.PLAYED", "Logic.PLAYED")
        c.ev("Logic.WAIT_START", "WaitT.START")
        c.ev("Logic.WAIT_STOP", "WaitT.STOP")
        c.ev("WaitT.EO", "Logic.WAIT_OVER")
    c.ev("Logic.TIMER_START", "Timer.START")
    c.da("Logic.TimerDT", "Timer.DT")
    c.ev("Logic.TIMER_STOP", "Timer.STOP")
    c.ev("Timer.EO", "Logic.TIMER")
    c.group("SkillControl", "State machine and OPC UA: Start(Session, parameters) with the range check, Stop, Abort, "
            "Reset; State, parameters and results published", ["Control", *start, "PubResults"], dy=4600)
    c.group("Execution", "One run: the contract, the command to the equipment and the end condition",
            ["Logic", "Timer", "WaitT"], dx=7000, dy=1800 + 260 * (len(used_inputs(skill, eq)) + len(params) + 12))
    c.group("Equipment", "The equipment's state in, the command as output values out (the command table and "
            "its timed phases are in Driver)", ["EqState", "EqView", "Driver", "PhaseT", "EqCmd"], dx=5200,
            dy=1800 + 260 * (len(ins) + len(sent) + 6))
    c.write()


def result_type(spec: ModuleSpec, steps: list[Step], source: str) -> str:
    """Type of a sequence result ``<step>.<result>``: the equipment input behind the step's result."""
    step_name, _, res = source.partition(".")
    skill = spec.skills[next(s for s in steps if s.name == step_name).skill]
    return spec.equipment[skill.equipment].inputs[skill.results[res]].type


# --------------------------------------------------------------------------------------------
# Application and system
# --------------------------------------------------------------------------------------------

def skill_instance(net, spec: ModuleSpec, step: Step, x, y, ua_path: str, token: str, top: bool, methods: bool,
                   ua_root: str):
    """An SK_ instance for a step, with its constant parameter bindings; ``top``: it releases its
    equipment with its final command (LastUse)."""
    skill = spec.skills[step.skill]
    params = {"Module": wstr(spec.module), "UaRoot": ua_root, "UaPath": wstr(ua_path), "UaEnable": "TRUE",
              "Methods": "TRUE" if methods else "FALSE", "Token": wstr(token), "LastUse": "TRUE" if top else "FALSE"}
    for n, v in step.bind.items():
        if not isinstance(v, str):
            params[n] = value_lit(v, skill.parameters[n].type)
    return fb(net, step.name, f"{spec.package}::SK_{step.skill}", x, y, **params)


def sequence(net, spec: ModuleSpec, name: str, steps: list[Step], x, y, ua_prefix: str, token: str | None,
             comment: str, params: dict[str, Parameter] | None = None, results: dict[str, str] | None = None,
             parent_events: bool = True):
    """Subapp running ``steps`` in order: START -> DONE, any FAILURE -> FAILED(ErrorID).

    ``token``: the lock token of a module level skill (children keep its equipment); None for a
    procedure (each child takes and releases equipment itself).
    """
    params, results = params or {}, results or {}
    ei = {"INIT": ([], "EInit"), "START": list(params)}
    if parent_events:
        ei.update({"HALT": [], "ABORT": [], "RESET": []})
    rtypes = {r: result_type(spec, steps, src) for r, src in results.items()}
    eo = {"INITO": ([], "EInit"), "DONE": list(results), "FAILED": ["ErrorID"]}
    _, inner = subapp(net, name, x, y, comment, ei, eo, {n: pr.type for n, pr in params.items()},
                      {"ErrorID": "UINT", **rtypes})
    ua_root = wstr(spec.opcua_root)
    names = []
    for i, step in enumerate(steps):
        eq = spec.skills[step.skill].equipment
        last_use = token is None or not any(spec.skills[s.skill].equipment == eq for s in steps[i + 1:])
        skill_instance(inner, spec, step, 1000 + i * 5000, 1000, f"{ua_prefix}/{step.name}",
                       token or ua_prefix.strip("/"), last_use, False, ua_root)
        names.append(step.name)
    ev = [("INIT", names[0] + ".INIT"), (names[-1] + ".INITO", "INITO"), ("START", names[0] + ".START"),
          (names[-1] + ".SUCCESS", "DONE")]
    da = []
    for a, z in zip(names, names[1:]):
        ev += [(a + ".INITO", z + ".INIT"), (a + ".SUCCESS", z + ".START")]
    if parent_events:
        for e in ["HALT", "ABORT", "RESET"]:
            ev += [(e, f"{n}.{e}") for n in names]
    # Failures merged pairwise (a data input takes one connection).
    if len(names) == 1:
        ev.append((names[0] + ".FAILURE", "FAILED"))
        da.append((names[0] + ".ErrorID", "ErrorID"))
    else:
        prev_ev, prev_err = names[0] + ".FAILURE", names[0] + ".ErrorID"
        for i, n in enumerate(names[1:], 1):
            m = f"Fail{i}"
            fb(inner, m, q("SKILL_FailMerge"), 1000 + i * 5000, 4000)
            ev += [(prev_ev, f"{m}.FAIL_A"), (n + ".FAILURE", f"{m}.FAIL_B")]
            da += [(prev_err, f"{m}.ErrA"), (n + ".ErrorID", f"{m}.ErrB")]
            prev_ev, prev_err = f"{m}.FAIL", f"{m}.Err"
        ev.append((prev_ev, "FAILED"))
        da.append((prev_err, "ErrorID"))
    for step in steps:
        for pname, v in step.bind.items():
            if isinstance(v, str):
                da.append((v, f"{step.name}.{pname}"))
    for r, src in results.items():
        st, _, res = src.partition(".")
        da.append((f"{st}.R_{res}", r))
    connections(inner, ev, da)
    return name


def module_skill(net, spec: ModuleSpec, name: str, x, y):
    """Subapp of a module level skill, of library instances only: Control (SKILL_Core), the Start
    method with one latch per parameter (named like the parameter), the OPC UA publishers and the
    equipment release; then the Execute sequence and the optional Stop sequence. Its OPC UA IDs are
    written as values, since no type of its own computes them."""
    comp = spec.composites[name]
    _, inner = subapp(net, name, x, y, f"Module level skill {name}: {comp.description}".rstrip(": "),
                      {"INIT": ([], "EInit")}, {"INITO": ([], "EInit")})
    n = SubNet(inner)
    root, path = spec.opcua_root, f"/Skills/{name}"
    methods = "TRUE" if comp.offered else "FALSE"
    n.fb("Control", q("SKILL_Core"), Module=wstr(spec.module), UaRoot=wstr(root), UaPath=wstr(path),
         UaEnable="TRUE", Methods=methods)
    params_id = ua_literal("WRITE", [f"{root}{path}/Parameters/{p}" for p in comp.parameters])
    start, go = start_method(n, comp.parameters, {p: p for p in comp.parameters}, {"QI": methods},
                             {"QI": "TRUE", "ID": params_id}, defaults=True)
    chain = ["Control", *start]
    if comp.results:
        n.fb("PubResults", publish(len(comp.results)), QI="TRUE",
             ID=ua_literal("WRITE", [f"{root}{path}/Results/{r}" for r in comp.results]))
        n.ev("Execute.DONE", "PubResults.REQ")
        for k, r in enumerate(comp.results, 1):
            n.da(f"Execute.{r}", f"PubResults.SD_{k}")
        chain.append("PubResults")
    if equipment := spec.uses(name):
        # On success the children have released the equipment (LastUse); on failure or abort the
        # skill gives it up on the release channel, so a lost message still ends all off.
        n.fb("Release", q("SKILL_Release"), Token=wstr(name))
        n.ev("Control.FAILURE", "Release.REQ")
        n.ev("Control.ABORT_O", "Release.REQ")
        for eq in equipment:
            n.fb(f"Rel_{eq}", publish(1), QI="TRUE", ID=wstr(f"loc[{spec.module}/{eq}/release]"))
            n.ev("Release.CNF", f"Rel_{eq}.REQ")
            n.da("Release.Holder", f"Rel_{eq}.SD_1")
            chain.append(f"Rel_{eq}")
    sequence(inner, spec, "Execute", comp.execute, 1000, 5000, f"{path}/Execute", name,
             f"{name}: execute sequence", comp.parameters, comp.results)
    chain.append("Execute")
    n.ev(go, "Execute.START")
    for p in comp.parameters:
        n.da(f"{p}.P", f"Execute.{p}")
    for ev in ["HALT", "ABORT", "RESET"]:
        n.ev(f"Control.{ev}_O", f"Execute.{ev}")
    n.ev("Execute.DONE", "Control.EXEC_DONE")
    n.ev("Execute.FAILED", "Control.EXEC_FAILED")
    n.da("Execute.ErrorID", "Control.ExecError")
    if comp.stop:
        # Published below .../Stopping: a "Stop" object would collide with the skill's Stop method.
        sequence(inner, spec, "Stop", comp.stop, 9000, 5000, f"{path}/Stopping", name, f"{name}: stop sequence")
        chain.append("Stop")
        n.ev("Control.RUN_STOP", "Stop.START")
        n.ev("Control.ABORT_O", "Stop.ABORT")
        n.ev("Control.RESET_O", "Stop.RESET")
        n.ev("Stop.DONE", "Control.STOP_DONE")
        n.ev("Stop.FAILED", "Control.STOP_DONE")
    else:
        n.ev("Control.RUN_STOP", "Control.STOP_DONE")
    n.chain("INIT", chain, "INITO")
    n.group("SkillControl", "State machine and OPC UA: Start(Session, parameters) with one block per parameter (range "
            "check, value for this run), Stop, Abort, Reset; State, parameters and results published",
            ["Control", *start, "PubResults"], dy=4600)
    n.group("Sequences", "What the skill does: Execute, and Stop when it is interrupted; private skill primitives "
            "in order", ["Execute", "Stop"], dx=6000, dy=3200)
    n.group("Releasing", "After a failure or an abort: gives up the equipment the skill holds (all off, free again)",
            ["Release", *[f"Rel_{e}" for e in equipment]], dy=2600)
    n.write()
    return name


def parameter_port(spec: ModuleSpec, skill: str, parameter: str) -> str:
    """Where the application holds a skill's parameter default: an input of the skill primitive's
    instance, or the Default of the module level skill's parameter latch."""
    return f"{skill}.{parameter}.Default" if skill in spec.composites else f"{skill}.{parameter}"


def app_name(spec: ModuleSpec, target: str) -> str:
    """Application of ``target``: the module's name for the first target, ``<Module>_<target>`` else."""
    return spec.module if target == next(iter(spec.targets)) else f"{spec.module}_{target}"


def device_name(target: str) -> str:
    """FORTE device of ``target`` in the system."""
    return f"FORTE_{target.upper()}"


def gpio_lines(net, spec: ModuleSpec, target: str, x, y):
    """Subapp with one GPIOChip per GPIO point of ``target``; its name, or None if there are none.

    A GPIOChip claims one line and registers it under a handle name (VALUE) that the IX/QX in the
    equipment refer to (PARAMS), so the lines are initialised before the equipment. The type
    exists only in Linux builds of FORTE.
    """
    lines = [(point, io) for point, io in spec.points() if spec.backend(target, io) == "gpio"]
    if not lines:
        return None
    _, inner = subapp(net, "GpioLines", x, y, "GPIO lines of the equipment's IO points (Linux /dev/gpiochip)",
                      {"INIT": ([], "EInit")}, {"INITO": ([], "EInit")})
    names = []
    for i, (point, io) in enumerate(lines):
        handle = point.replace(".", "_")
        fb(inner, handle, STD["GPIOChip"], 1000 + i * 3000, 1000, QI="TRUE", VALUE=wstr(handle),
           ChipNumber=str(io.gpio.chip), LineNumber=str(io.gpio.line),
           ReadWriteMode="1" if isinstance(io, Output) else "0",      # 1 push-pull output, 0 input
           BiasMode=str(BIAS[io.gpio.bias]), ActiveLow="TRUE" if io.gpio.active_low else "FALSE")
        names.append(handle)
    events = [("INIT", names[0] + ".INIT"), (names[-1] + ".INITO", "INITO")]
    events += [(a + ".INITO", z + ".INIT") for a, z in zip(names, names[1:])]
    connections(inner, events, [])
    return "GpioLines"


def pwm_lines(net, spec: ModuleSpec, target: str, x, y):
    """Subapp with one PWMChip per PWM output of ``target`` (FORTE module pwmsysfs, Linux only)."""
    channels = [(point, io) for point, io in spec.points() if spec.backend(target, io) == "pwm"]
    if not channels:
        return None
    _, inner = subapp(net, "PwmLines", x, y, "PWM channels of the equipment's analog outputs (Linux /sys/class/pwm)",
                      {"INIT": ([], "EInit")}, {"INITO": ([], "EInit")})
    root = spec.targets[target].pwm_root
    names = []
    for i, (point, io) in enumerate(channels):
        handle = point.replace(".", "_")
        extra = {} if root == "/sys/class/pwm" else {"SysfsRoot": wstr(root)}
        fb(inner, handle, STD["PWMChip"], 1000 + i * 3000, 1000, QI="TRUE", VALUE=wstr(handle),
           ChipNumber=str(io.pwm.chip), Channel=str(io.pwm.channel), PeriodNs=str(io.pwm.period_ns), **extra)
        names.append(handle)
    events = [("INIT", names[0] + ".INIT"), (names[-1] + ".INITO", "INITO")]
    events += [(a + ".INITO", z + ".INIT") for a, z in zip(names, names[1:])]
    connections(inner, events, [])
    return "PwmLines"


def application(root, spec: ModuleSpec, target: str):
    """The module's application on ``target``, in rows: module level, equipment IO, skill primitives,
    module level skills, procedures."""
    pkg, ua_root = spec.package, wstr(spec.opcua_root)
    module = wstr(spec.module)
    t = spec.targets[target]
    app = elem(root, "Application", Name=app_name(spec, target),
               Comment=f"Module {spec.module} on target {target} ({t.host}, IO {t.io}; generated by modgen)")
    net = elem(app, "SubAppNetwork")
    # Wide spacing: the IDE checks for overlapping blocks, including the resource's own START
    # block at the origin, and a mapped block keeps its application coordinates.
    fb(net, "Boot", STD["E_RESTART"], 2000, 200)
    fb(net, "Occupation", q("MOD_Occupation"), 5000, 200, Module=module, UaRoot=ua_root, UaEnable="TRUE")
    fb(net, "Module", q("MOD_StateManager"), 9000, 200, Module=module, UaRoot=ua_root, UaEnable="TRUE",
       StopTimeout=tlit(spec.stop_timeout))
    lines = [n for n in (gpio_lines(net, spec, target, 13000, 200), pwm_lines(net, spec, target, 17000, 200)) if n]
    chain = lines + ["Occupation", "Module"]
    for i, (name, eq) in enumerate(spec.equipment.items()):
        io = {}
        for s, point in [*eq.inputs.items(), *eq.outputs.items()]:
            backend = spec.backend(target, point)
            io[f"{s}_Backend"] = str(BACKENDS[backend])
            if backend == "modbus":
                io[f"{s}_Modbus"] = wstr(spec.modbus_id(point.modbus, isinstance(point, Output), target))
            elif backend in ("gpio", "pwm"):
                io[f"{s}_Io"] = f"'{name}_{s}'"
        fb(net, name, f"{pkg}::EQ_{name}", 2000 + i * 5000, 3000, Module=module, UaRoot=ua_root, UaEnable="TRUE", **io)
        chain.append(name)
    for i, (name, skill) in enumerate((n, s) for n, s in spec.skills.items() if s.offered):
        skill_instance(net, spec, Step(skill=name, name=name), 2000 + i * 5000, 6000, f"/Skills/{name}", name, True,
                       True, ua_root)
        chain.append(name)
    events, data = [("Boot.COLD", chain[0] + ".INIT"), ("Boot.WARM", chain[0] + ".INIT")], []
    for i, proc in enumerate(["Resetting", "Stopping"]):
        upper = proc.upper()
        if proc in spec.procedures:
            sequence(net, spec, proc, spec.procedures[proc], 2000 + i * 5000, 12000, f"/Procedures/{proc}", None,
                     f"Procedure the module runs while {proc}", parent_events=False)
            chain.append(proc)
            events += [(f"Module.RUN_{upper}", f"{proc}.START"), (f"{proc}.DONE", f"Module.{upper}_DONE"),
                       (f"{proc}.FAILED", f"Module.{upper}_FAILED")]
        else:
            events.append((f"Module.RUN_{upper}", f"Module.{upper}_DONE"))
    # Module level skills come last: one added online extends the INIT chain at its end.
    for i, name in enumerate(spec.composites):
        module_skill(net, spec, name, 2000 + i * 5000, 9000)
        chain.append(name)
    events += [(a + ".INITO", z + ".INIT") for a, z in zip(chain, chain[1:])]
    connections(net, events, data)
    return app


def group_layout(net, spec: ModuleSpec):
    """Arrange the application's blocks in one group each, stacked from top to bottom: module level,
    module level skills, procedures, a catalogue of skill primitives, equipment IO."""
    arrange(net, [
        ("ModuleLevel", "Module level: occupation, PackML state manager, start-up and the target's IO lines",
         ["Boot", "GpioLines", "PwmLines", "Occupation", "Module"], 5, 5000, 3000),
        ("ModuleLevelSkills", "Module level skills: Control, Sequences (Execute, Stop) of skill primitives and "
         "Release; OPC UA /Skills/<name>", list(spec.composites), 4, 5000, 2200),
        ("Procedures", "Procedures the module state manager runs while Resetting and Stopping",
         ["Resetting", "Stopping"], 4, 5000, 2200),
        ("SkillPrimitives", "Skill primitives: one equipment command until a sensor or a time; OPC UA /Skills/<name>",
         [n for n, s in spec.skills.items() if s.offered], 4, 5500, 3800),
        ("EquipmentIO", "Equipment IO: the only owners of the IO points; skills send them output values over "
         "local channels", list(spec.equipment), 4, 6500, 5000)])


def hide_init_connections(root):
    """Hide the INIT chains and the start-up connections: they only order the initialisation and
    clutter the diagram (the IDE shows a hidden connection as a label at both ends)."""
    for ec in root.iter("EventConnections"):
        for conn in ec:
            src, dst = conn.get("Source"), conn.get("Destination")
            if (src.split(".")[-1] in ("INITO", "COLD", "WARM") or dst.split(".")[-1] == "INIT"
                    or src == "INIT"):
                elem(conn, "Attribute", Name="Visible", Value="false")      # a system attribute: no Type


def make_system(p: Project, spec: ModuleSpec):
    """Write the .sys: per target, the module application mapped to resource RES of the target's device."""
    root = ET.Element("System", Name=p.name, Comment=f"Module {spec.module}, generated from its module specification")
    elem(root, "Identification", Standard="61499-2")
    apps = {target: application(root, spec, target) for target in spec.targets}
    for node in root.iter("FB"):
        p.use(node.get("Type"))               # the module level skills use generic comm FBs directly
    for app in apps.values():
        group_layout(app.find("SubAppNetwork"), spec)
    hide_init_connections(root)
    for i, (target, t) in enumerate(spec.targets.items()):
        device = elem(root, "Device", Name=device_name(target), Type=STD["FORTE_PC"], x=1000 + i * 3000, y=1000)
        elem(device, "Parameter", Name="MGR_ID", Comment="Device manager socket ID", Value=wstr(f"{t.host}:{t.port}"))
        elem(device, "Attribute", Name="Profile", Type="STRING", Value="HOLOBLOC")
        elem(device, "Attribute", Name="Color", Type="STRING", Value="255,190,111")  # required by the IDE
        res = elem(device, "Resource", Name="RES", Type=STD["EMB_RES"], x=0, y=0)
        # As the IDE writes it: the resource network holds only resource-local FBs, and each mapped
        # element is a Mapping to the resource; the IDE rebuilds the mapped copies itself. Copies
        # in the resource network make the IDE's system editor fail ("Could not load system").
        elem(res, "FBNetwork")
    for target, app in apps.items():
        for child in app.find("SubAppNetwork"):
            if child.tag in ("FB", "SubApp"):
                elem(root, "Mapping", From=f"{app.get('Name')}.{child.get('Name')}", To=f"{device_name(target)}.RES")
    save(root, p.root / f"{p.name}.sys")


def make_module(p: Project, spec: ModuleSpec):
    """Write the module's equipment, skill and control types and its system."""
    for name, eq in spec.equipment.items():
        make_equipment(p, spec.package, name, eq)
        make_equipment_commands(p, spec.package, name, eq)
        make_equipment_view(p, spec.package, name, eq)
    for name, skill in spec.skills.items():
        make_skill(p, spec.package, name, skill, spec.equipment[skill.equipment] if skill.equipment else None)
    make_system(p, spec)
