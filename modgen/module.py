"""Module-specific types and system, generated from a module specification.

Equipment IO CFB ``EQ_<Name>`` (logic ``EL_<Name>``): owns its IO points (FORTE binds one FB per
IO point), runs commands from its local ``cmd`` channel as timed phases with break before make,
grants the equipment to one holder at a time, switches off when the module aborts, and publishes
its inputs and holder on its ``state`` channel and its inputs over OPC UA.

Skill primitive ``SK_<Name>``: the shared ``SKILL_Control`` state machine, the parameters block
``SP_<Name>`` (range check and latching) and the execution ``SL_<Name>`` (one equipment command
until ``ensures`` or ``after``; contract, timeout, lock), with OPC UA methods Start(Session,
parameters...), Stop, Abort, Reset and variables State, ErrorID, Parameters/*, Results/*.

Module level skill (composite): a subapp with ``Control`` (``SC_<Name>``: SKILL_Control,
parameters, OPC UA, equipment release) and ``Execute``/``Stop`` subapps holding private skill
primitive instances in sequence.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from .fbxml import STD, Basic, Composite, Project, Simple, connections, elem, fb, save, subapp, wstr
from .library import ERRORS, KEEP, cat, lit, loc, q, ua
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
# Equipment IO
# --------------------------------------------------------------------------------------------

def targets_code(eq: Equipment) -> str:
    """ST computing the target outputs N_*/NE_* and the phase timing of (Command, Phase)."""
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


def make_equipment(p: Project, pkg: str, name: str, eq: Equipment):
    """EQ_<name> and its logic EL_<name>."""
    ins, outs = eq.inputs, eq.outputs
    bools = [o for o, x in outs.items() if x.type == "BOOL"]
    reals = [o for o, x in outs.items() if x.type == "LREAL"]
    pub = []
    for i, s in enumerate(ins):
        pub += ["UaRoot", lit("/Equipment/"), "Name", lit(f"/{s}" + (";" if i < len(ins) - 1 else ""))]
    drive = [f"O_{o}" for o in outs] + [f"E_{o}" for o in reals]
    b = Basic(p, pkg, f"EL_{name}",
              f"{name}: commands -> outputs in timed phases (break before make); one holder at a time; "
              "all off when the module aborts; inputs -> state channel",
              {"INIT": (["Module", "Name", *(["UaRoot"] if ins else [])], "EInit"),
               "CMD": ["C_Holder", "C_Command", "C_Arg", "C_Release"],
               "SAMPLE": [f"I_{s}" for s in ins], "REFRESH": [], "DRIVEN": [], "PHASE_T": [], "MOD_CHG": ["ModState"]},
              {"INITO": (["IdCmd", "IdState", "IdPub"], "EInit"), "DRIVE": drive,
               "STATE": [*ins, "Holder", "ActiveCommand", "ActiveArg"],
               "PHASE_START": ["PhaseDT"], "PHASE_STOP": []},
              {"Module": "WSTRING", "Name": "WSTRING", **({"UaRoot": "WSTRING"} if ins else {}),
               "C_Holder": "WSTRING", "C_Command": "USINT",
               "C_Arg": "LREAL", "C_Release": "BOOL", **{f"I_{s}": i.type for s, i in ins.items()}, "ModState": "USINT"},
              {"IdCmd": "WSTRING", "IdState": "WSTRING", "IdPub": "WSTRING",
               **{f"O_{o}": x.type for o, x in outs.items()}, **{f"E_{o}": "BOOL" for o in reals},
               **{s: i.type for s, i in ins.items()}, "Holder": "WSTRING", "ActiveCommand": "USINT", "ActiveArg": "LREAL",
               "PhaseDT": "TIME"},
              {"Command": "USINT", "Phase": "USINT", "Arg": "LREAL", "Changed": "BOOL",
               "Timed": "BOOL", "Publish": "BOOL", "Beat": "USINT", "LastHolder": "WSTRING", "Pending": "BOOL",
               "AbortPending": "BOOL",
               **{f"L_{s}": i.type for s, i in ins.items()},
               **{f"N_{o}": x.type for o, x in outs.items()}, **{f"NE_{o}": "BOOL" for o in reals}},
              folder="Equipment/Base")
    targets = targets_code(eq)
    b.state("START")
    b.state("Init", f"IdCmd := {cat(lit('loc['), 'Module', lit('/'), 'Name', lit('/cmd]'))};\n"
                    f"IdState := {cat(lit('loc['), 'Module', lit('/'), 'Name', lit('/state]'))};\n"
                    + (f"IdPub := {ua('WRITE', *pub)};" if ins else 'IdPub := "";'), "INITO")
    # The state is published only when an input or the holder changed, and every 20 samples as a
    # heartbeat (for skills added online): every Modbus poll delivers a sample, and publishing each
    # to every skill overran FORTE's external event queue.
    changed = " OR ".join([*[f"({s} <> L_{s})" for s in ins], "(Holder <> LastHolder)", "(Beat >= 20)"])
    b.state("Sample", "\n".join([*[f"{s} := I_{s};" for s in ins], f"Publish := {changed};", "Beat := Beat + 1;",
                                 "ActiveCommand := Command;", "ActiveArg := Arg;"]))
    b.state("Publish", "\n".join([*[f"L_{s} := {s};" for s in ins], "LastHolder := Holder;", "Beat := 0;"]), "STATE")
    # Like a PLC scan, the output image is rewritten every cycle: FORTE's Modbus client drops a
    # write sent while it is not connected, and a cyclic write heals that and reconnects.
    b.state("Refresh", None, "DRIVE")
    # The same command with the same argument again does not restart its phases.
    b.state("Cmd", "Holder := C_Holder;\n"
                   f"Changed := (C_Command <> {KEEP}) AND ((C_Command <> Command) OR (C_Arg <> Arg));\n"
                   "IF Changed THEN\n  Command := C_Command;\n  Phase := 0;\n  Arg := C_Arg;\nEND_IF;\n"
                   'IF C_Release THEN\n  Holder := "";\nEND_IF;')
    b.state("Report", "LastHolder := Holder;\nBeat := 0;", "STATE")
    b.state("NextPhase", "Phase := Phase + 1;")
    b.state("Safe", 'Command := 0;\nPhase := 0;\nHolder := "";\nAbortPending := FALSE;')
    # Outputs that stay on are kept, all others switched off first; then the new set is switched on.
    b.state("Break", targets + "\n" + "\n".join(f"O_{o} := O_{o} AND N_{o};" for o in bools), "DRIVE")
    b.state("Make", "\n".join([f"O_{o} := N_{o};" for o in outs] + [f"E_{o} := NE_{o};" for o in reals]) or None,
            "DRIVE")
    b.state("BreakW")
    b.state("MakeW")
    # A command or an abort arriving while the outputs are written would be dropped (no transition
    # for it there); it is marked and handled once the outputs are settled. Its data (C_*) is the
    # latest message, which is the one that counts.
    for w in ["B", "M"]:
        b.state(f"Queue{w}", "Pending := TRUE;")
        b.state(f"Abort{w}", "AbortPending := TRUE;")
    b.state("CmdPend", "Pending := FALSE;")
    b.state("Settled")
    b.state("PhaseGo", None, "PHASE_START", ["STATE"])
    b.state("PhaseEnd", None, "PHASE_STOP", ["STATE"])
    b.trans("START", "Init", "INIT")
    b.trans("START", "Sample", "SAMPLE")
    b.trans("START", "Refresh", "REFRESH")
    b.trans("START", "Cmd", 'CMD[(Holder = "") OR (C_Holder = Holder)]')
    b.trans("START", "NextPhase", "PHASE_T")
    b.trans("START", "Safe", "MOD_CHG[(ModState = 8) OR (ModState = 9)]")   # Aborting or Aborted
    b.trans("Init", "START", "1")
    b.trans("Sample", "Publish", "Publish")
    b.trans("Sample", "START", "1")
    b.trans("Publish", "START", "1")
    b.trans("Refresh", "START", "1")
    b.trans("Cmd", "Break", "Changed")
    b.trans("Cmd", "Report", "1")
    b.trans("Report", "START", "1")
    b.trans("NextPhase", "Break", "1")
    b.trans("Safe", "Break", "1")
    b.trans("Break", "BreakW", "1")
    b.trans("BreakW", "Make", "DRIVEN")
    b.trans("Make", "MakeW", "1")
    b.trans("MakeW", "Settled", "DRIVEN")
    for w, wait in [("B", "BreakW"), ("M", "MakeW")]:
        b.trans(wait, f"Queue{w}", "CMD")
        b.trans(wait, f"Abort{w}", "MOD_CHG[(ModState = 8) OR (ModState = 9)]")
        b.trans(f"Queue{w}", wait, "1")
        b.trans(f"Abort{w}", wait, "1")
    b.trans("Settled", "Safe", "AbortPending")
    b.trans("Settled", "CmdPend", "Pending")
    b.trans("CmdPend", "Cmd", '(Holder = "") OR (C_Holder = Holder)')
    b.trans("CmdPend", "PhaseGo", "Timed")
    b.trans("CmdPend", "PhaseEnd", "1")
    b.trans("Settled", "PhaseGo", "Timed")
    b.trans("Settled", "PhaseEnd", "1")
    b.trans("PhaseGo", "START", "1")
    b.trans("PhaseEnd", "START", "1")
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
    c = Composite(p, pkg, f"EQ_{name}", (eq.description or name) + "; equipment IO: owns its IO points; commands "
                  + ", ".join(f"{k}={eq.code(k)}" for k in eq.commands),
                  {"INIT": (list(iv), "EInit")}, {"INITO": ([], "EInit")}, iv, {}, folder="Equipment")
    c.fb("Logic", f"{pkg}::EL_{name}")
    c.fb("Mode", q("MOD_StateView"))
    c.fb("SubCmd", p.subscribe(4), QI="TRUE")
    c.fb("PubState", p.publish(len(ins) + 1), QI="TRUE")
    if ins:
        c.fb("PubUa", p.publish(len(ins)))
    for s, i in ins.items():
        c.fb(f"In_{s}", q("IO_" + IO_TYPE[("in", i.type)]))
    for o, x in outs.items():
        c.fb(f"Out_{o}", q("IO_" + IO_TYPE[("out", x.type)]))
    c.fb("Cycle", STD["E_CYCLE"])
    c.fb("PhaseT", STD["E_DELAY"])
    c.chain("INIT", ["Logic", "Mode", "SubCmd", "PubState", *(["PubUa"] if ins else []),
                     *[f"In_{s}" for s in ins], *[f"Out_{o}" for o in outs]], ["Cycle.START", "INITO"])
    for v in ["Module", "Name", *(["UaRoot"] if ins else [])]:
        c.da(v, "Logic." + v)
    c.da("Module", "Mode.Module")
    c.da("Logic.IdCmd", "SubCmd.ID")
    c.da("Logic.IdState", "PubState.ID")
    if ins:
        c.da("Logic.IdPub", "PubUa.ID")
        c.da("UaEnable", "PubUa.QI")
    c.da("CycleTime", "Cycle.DT")
    c.ev("SubCmd.IND", "Logic.CMD")
    for k, v in enumerate(["C_Holder", "C_Command", "C_Arg", "C_Release"], 1):
        c.da(f"SubCmd.RD_{k}", f"Logic.{v}")
    c.ev("Mode.CHG", "Logic.MOD_CHG")
    c.da("Mode.State", "Logic.ModState")
    reads = [f"In_{s}" for s in ins]
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
    writes = [f"Out_{o}" for o in outs]
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
    c.ev("Logic.PHASE_START", "PhaseT.START")
    c.da("Logic.PhaseDT", "PhaseT.DT")
    c.ev("Logic.PHASE_STOP", "PhaseT.STOP")
    c.ev("PhaseT.EO", "Logic.PHASE_T")
    c.write()


# --------------------------------------------------------------------------------------------
# Skill parameters, skill primitives and module level skills
# --------------------------------------------------------------------------------------------

def make_params(p: Project, pkg: str, name: str, params: dict[str, Parameter], results: list[str],
                release: list[str] | None = None):
    """SP_<name>: OPC UA IDs of parameters/results (and equipment release), range check, latching.

    INIT publishes the defaults (P := D); CHECK tests the Start arguments S_*; LATCH_UA takes them,
    LATCH_DEF takes the defaults or what the parent passes in (D_*).
    """
    base = cat("UaRoot", "UaPath")
    ua_ids = bool(params or results)
    code = []
    if not ua_ids:
        pass
    elif params:
        pub = []
        for i, n in enumerate(params):
            pub += [base, lit(f"/Parameters/{n}" + (";" if i < len(params) - 1 else ""))]
        code.append(f"IdParams := {ua('WRITE', *pub)};")
    else:
        code.append('IdParams := "";')
    if not ua_ids:
        pass
    elif results:
        pub = []
        for i, r in enumerate(results):
            pub += [base, lit(f"/Results/{r}" + (";" if i < len(results) - 1 else ""))]
        code.append(f"IdResults := {ua('WRITE', *pub)};")
    else:
        code.append('IdResults := "";')
    for eq in release or []:
        code.append(f"IdRel_{eq} := {loc('Module', eq, 'cmd')};")
    code += [f"P_{n} := D_{n};" for n in params]
    ranges = [f"(S_{n} >= {pr.literal(pr.minimum)})" for n, pr in params.items() if pr.minimum is not None]
    ranges += [f"(S_{n} <= {pr.literal(pr.maximum)})" for n, pr in params.items() if pr.maximum is not None]
    ids = [*(["IdParams", "IdResults"] if ua_ids else []), *[f"IdRel_{e}" for e in release or []]]
    ei = {"INIT": ([*(["Module"] if release else []), *(["UaRoot", "UaPath"] if ua_ids else []),
                    *[f"D_{n}" for n in params]], "EInit")}
    eo = {"INITO": ([*ids, *[f"P_{n}" for n in params]], "EInit")}
    algs = {"INIT": ("\n".join(code), "INITO")}
    if params:
        ei.update({"CHECK": [f"S_{n}" for n in params], "LATCH_UA": [], "LATCH_DEF": [f"D_{n}" for n in params]})
        eo.update({"CHECKED": ["InRange"], "LATCHED": [f"P_{n}" for n in params]})
        algs["CHECK"] = (f"InRange := {' AND '.join(ranges) or 'TRUE'};", "CHECKED")
        algs["LATCH_UA"] = ("\n".join(f"P_{n} := S_{n};" for n in params), "LATCHED")
        algs["LATCH_DEF"] = ("\n".join(f"P_{n} := D_{n};" for n in params), "LATCHED")
    desc = "; ".join(f"{n} [{pr.unit or '-'}] {pr.minimum}..{pr.maximum}, default {pr.default}"
                     for n, pr in params.items()) or "none"
    Simple(p, pkg, f"SP_{name}", f"{name} parameters ({desc}): OPC UA IDs, range check and latching",
           ei, eo,
           {**({"Module": "WSTRING"} if release else {}), **({"UaRoot": "WSTRING", "UaPath": "WSTRING"} if ua_ids else {}),
            **{f"D_{n}": pr.type for n, pr in params.items()},
            **{f"S_{n}": pr.type for n, pr in params.items()}},
           {**{i: "WSTRING" for i in ids}, **{f"P_{n}": pr.type for n, pr in params.items()},
            **({"InRange": "BOOL"} if params else {})},
           algs, folder="Skills/Parameters").write()


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
    """SL_<name>: executes one run of a skill primitive."""
    params, e = skill.parameters, ERRORS
    ins = eq.inputs if eq else {}
    drive = eq.code(skill.command) if eq else None
    stop = eq.code(skill.stop) if eq and skill.stop else 0
    timed = skill.after is not None
    after = skill.after if isinstance(skill.after, str) else num(skill.after or 0)
    has_eq = eq is not None
    used = used_inputs(skill, eq)
    init = (["Module", "Equipment", "Token", "LastUse"] if has_eq else []) + ([] if timed else ["Timeout"])
    ei = {"INIT": (init, "EInit"), "START": list(params), "HALT": [], "ABORT": [], "TIMER": []}
    eo = {"INITO": (["IdEqState", "IdEqCmd"] if has_eq else [], "EInit"), "DONE": [f"R_{r}" for r in skill.results],
          "FAILED": ["ErrorID"], "HALTED": ["ErrorID"], "TIMER_START": ["TimerDT"], "TIMER_STOP": []}
    types = {"Module": "WSTRING", "Equipment": "WSTRING", "Token": "WSTRING", "LastUse": "BOOL", "Timeout": "TIME"}
    iv = {**{v: types[v] for v in init}, **{n: pr.type for n, pr in params.items()}}
    ov = {"ErrorID": "UINT", "TimerDT": "TIME", **{f"R_{r}": ins[src].type for r, src in skill.results.items()}}
    if has_eq:
        # Only the inputs the skill uses (the equipment view EV_ receives the whole state channel).
        ei["SAMPLE"] = [*used, "Holder"]
        ei["WAIT_OVER"] = []
        eo["WAIT_START"], eo["WAIT_STOP"] = [], []
        eo["CMD"] = ["C_Holder", "C_Command", "C_Arg", "C_Release"]
        eo["EQ_FREE"] = ["EqFree"]
        iv.update({**{s: ins[s].type for s in used}, "Holder": "WSTRING"})
        ov.update({"IdEqState": "WSTRING", "IdEqCmd": "WSTRING", "C_Holder": "WSTRING", "C_Command": "USINT",
                   "C_Arg": "LREAL", "C_Release": "BOOL", "EqFree": "BOOL"})
    what = (f"holds {skill.equipment}.{skill.command} until {skill.ensures or f'{after} s'}" if has_eq
            else f"waits {after} s")
    b = Basic(p, pkg, f"SL_{name}", f"{name}: Requires {skill.requires}; {what}; Invariant {skill.invariant}",
              ei, eo, iv, ov, folder="Skills/Logic")

    # The final command releases the equipment when this is the last step using it (LastUse), in
    # the same message: a separate release could overwrite the stop on the local channel.
    def cmd(code, release="LastUse"):
        return f"C_Holder := Token;\nC_Command := {code};\nC_Arg := {arg};\nC_Release := {release};"

    arg = (skill.arg if isinstance(skill.arg, str) else num(skill.arg)) if skill.arg is not None else "0.0"
    busy = '(Holder <> "") AND (Holder <> Token)'
    b.state("Idle")
    b.state("Init", (f"IdEqState := {cat(lit('loc['), 'Module', lit('/'), 'Equipment', lit('/state]'))};\n"
               f"IdEqCmd := {cat(lit('loc['), 'Module', lit('/'), 'Equipment', lit('/cmd]'))};" if has_eq
               else None), "INITO")
    b.state("Check")
    b.state("Reject", f"ErrorID := {e['PreconditionViolated']};", "FAILED")
    results = "\n".join(f"R_{r} := {src};" for r, src in skill.results.items())
    timer = f"TimerDT := MUL_TIME(T#1s, {after});" if timed else "TimerDT := Timeout;"
    if has_eq:
        b.state("Sample", f'EqFree := (Holder = "") OR (Holder = Token);', "EQ_FREE")
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
        b.state("Unsafe", cmd(0) + f"\nErrorID := {e['InvariantViolated']};", "CMD", ["TIMER_STOP", "FAILED"])
        b.state("Lost", f"ErrorID := {e['Busy']};", "TIMER_STOP", ["FAILED"])
        b.state("Done", cmd(stop) + ("\n" + results if results else ""), "CMD", ["TIMER_STOP", "DONE"])
        if not timed:
            b.state("TimedOut", cmd(0) + f"\nErrorID := {e['Timeout']};", "CMD", ["FAILED"])
        b.state("Halt", cmd(stop) + f"\nErrorID := {e['Interrupted']};", "CMD", ["TIMER_STOP", "HALTED"])
        b.state("Abort", cmd(0), "CMD", ["TIMER_STOP"])
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
        for s in ["Busy", "Unsafe", "Lost", *([] if timed else ["AlreadyDone", "TimedOut"])]:
            b.trans(s, "Idle", "1")
    else:
        b.trans("Running", "Done", "TIMER")
    b.trans("Check", "Run", "1")
    b.trans("Run", "Running", "1")
    b.trans("Running", "Halt", "HALT")
    b.trans("Running", "Abort", "ABORT")
    for s in ["Reject", "Done", "Halt", "Abort"]:
        b.trans(s, "Idle", "1")
    b.write()


def wire_control(c: Composite, p: Project, params: dict, has_params_block: bool, eq_free_const: bool,
                 params_module: bool = False, params_ua: bool = True):
    """Shared part of SK_/SC_: SKILL_Control with its OPC UA methods, views, state and activity.

    Without parameters the range check is always passed; without an own equipment lock check
    (module level skills, primitives without equipment) the equipment is always free.
    """
    constants = {**({} if params else {"InRange": "TRUE"}), **({"EqFree": "TRUE"} if eq_free_const else {})}
    c.fb("Control", q("SKILL_Control"), **constants)
    if has_params_block:
        c.fb("Params", f"{c.package}::SP_{c.name[3:]}")
    c.fb("Owner", q("MOD_OwnerView"))
    c.fb("Mode", q("MOD_StateView"))
    # Method blocks are UaStart etc.: IEC names are case-insensitive, so "Start" clashes with START.
    c.fb("UaStart", p.server(2, 1 + len(params)))
    for m in ["Stop", "Abort", "Reset"]:
        c.fb(f"Ua{m}", p.server(2, 1))
    c.fb("PubState", p.publish(2))
    c.fb("Act", p.publish(1), QI="TRUE")
    c.da("Module", "Control.Module", "Owner.Module", "Mode.Module")
    c.da("UaRoot", "Control.UaRoot")
    c.da("UaPath", "Control.UaPath")
    if has_params_block:
        if params_module:
            c.da("Module", "Params.Module")
        if params_ua:
            c.da("UaRoot", "Params.UaRoot")
            c.da("UaPath", "Params.UaPath")
        for n in params:
            c.da(n, f"Params.D_{n}")
    c.da("Methods", "UaStart.QI", "UaStop.QI", "UaAbort.QI", "UaReset.QI")
    c.da("UaEnable", "PubState.QI")
    for m in ["Start", "Stop", "Abort", "Reset"]:
        c.da(f"Control.Id{m}", f"Ua{m}.ID")
        c.ev(f"Control.RSP_{m.upper()}", f"Ua{m}.RSP")
        c.da("Control.Accepted", f"Ua{m}.SD_1")
        c.da("Control.RspError", f"Ua{m}.SD_2")
        c.da(f"Ua{m}.RD_1", f"Control.S_{m}")
    for m in ["Stop", "Abort", "Reset"]:
        c.ev(f"Ua{m}.IND", f"Control.CMD_{m.upper()}")
    if params:
        c.ev("UaStart.IND", "Params.CHECK")
        for k, n in enumerate(params, 2):
            c.da(f"UaStart.RD_{k}", f"Params.S_{n}")
        c.ev("Params.CHECKED", "Control.CMD_START")
        c.da("Params.InRange", "Control.InRange")
    else:
        c.ev("UaStart.IND", "Control.CMD_START")
    c.ev("Owner.CHG", "Control.OWNER_CHG")
    c.da("Owner.Owner", "Control.Owner")
    c.ev("Mode.CHG", "Control.MOD_CHG")
    c.da("Mode.State", "Control.ModState")
    c.da("Control.IdPub", "PubState.ID")
    c.ev("Control.PUB", "PubState.REQ")
    c.da("Control.State", "PubState.SD_1", "State")
    c.da("Control.ErrorID", "PubState.SD_2", "ErrorID")
    c.da("Control.IdAct", "Act.ID")
    c.ev("Control.ACT", "Act.REQ")
    c.da("Control.Delta", "Act.SD_1")
    for ev in ["START", "HALT", "ABORT", "RESET"]:
        c.ev(ev, f"Control.{ev}")
    c.ev("Control.SUCCESS", "SUCCESS")
    c.ev("Control.FAILURE", "FAILURE")


def skill_interface(params: dict, extra_init: dict):
    """INIT inputs of SK_/SC_: identity and OPC UA placement, extras, then the parameter defaults."""
    iv = {"Module": "WSTRING", "UaRoot": "WSTRING", "UaPath": "WSTRING", "UaEnable": "BOOL", "Methods": "BOOL",
          "Token": "WSTRING", **extra_init, **{n: (pr.type, pr.literal()) for n, pr in params.items()}}
    return iv


def make_skill(p: Project, pkg: str, name: str, skill: Skill, eq: Equipment | None):
    """SK_<name>: skill primitive CFB."""
    params, results = skill.parameters, list(skill.results)
    make_skill_logic(p, pkg, name, skill, eq)
    has_sp = bool(params or results)
    if has_sp:
        make_params(p, pkg, name, params, results)
    extra = {"LastUse": ("BOOL", "TRUE")}
    if skill.ensures is not None:
        extra["Timeout"] = ("TIME", tlit(skill.timeout))
    iv = skill_interface(params, extra)
    ins = eq.inputs if eq else {}
    ov = {"State": "USINT", "ErrorID": "UINT", **{f"R_{r}": ins[s].type for r, s in skill.results.items()}}
    desc = "; ".join(f"{n} [{pr.unit or '-'}] {pr.minimum}..{pr.maximum}, default {pr.default}"
                     for n, pr in params.items()) or "none"
    c = Composite(p, pkg, f"SK_{name}", f"Skill primitive {name}: {skill.description or name} (parameters: {desc}). "
                  "OPC UA Start(Session, parameters...)/Stop/Abort/Reset(Session) -> [Accepted, ErrorID]; "
                  "START/HALT/ABORT/RESET from a parent -> SUCCESS or FAILURE(ErrorID)",
                  {"INIT": (list(iv), "EInit"), "START": list(params), "HALT": [], "ABORT": [], "RESET": []},
                  {"INITO": ([], "EInit"), "SUCCESS": [f"R_{r}" for r in results], "FAILURE": ["ErrorID"]},
                  iv, ov, folder="Skills")
    wire_control(c, p, params, has_sp, eq is None)
    c.fb("Logic", f"{pkg}::SL_{name}", **({"Equipment": wstr(skill.equipment)} if eq else {}))
    if params:
        c.fb("PubParams", p.publish(len(params)))
    if results:
        c.fb("PubResults", p.publish(len(results)))
    if eq:
        c.fb("EqState", p.subscribe(len(ins) + 1), QI="TRUE")
        c.fb("EqView", f"{pkg}::EV_{skill.equipment}")
        c.fb("WaitT", STD["E_DELAY"], DT="T#500ms")      # how long a step waits for another holder's release
        c.fb("EqCmd", p.publish(4), QI="TRUE")
    c.fb("Timer", STD["E_DELAY"])
    chain = ["Control", *(["Params"] if has_sp else []), "Logic", "Owner", "Mode", "UaStart", "UaStop", "UaAbort", "UaReset",
             "PubState", *(["PubParams"] if params else []), *(["PubResults"] if results else []), "Act",
             *(["EqState", "EqCmd"] if eq else [])]
    c.chain("INIT", chain, ["PubState.REQ", *(["PubParams.REQ"] if params else []), "INITO"])
    if eq:
        c.da("Module", "Logic.Module")
        c.da("Token", "Logic.Token")
        c.da("LastUse", "Logic.LastUse")
    if skill.ensures is not None:
        c.da("Timeout", "Logic.Timeout")
    if params:
        c.da("UaEnable", "PubParams.QI")
        c.da("Params.IdParams", "PubParams.ID")
        c.ev("Control.GO_UA", "Params.LATCH_UA")
        c.ev("Control.GO_PARENT", "Params.LATCH_DEF")
        c.ev("Params.LATCHED", "Logic.START", "PubParams.REQ")
        for k, n in enumerate(params, 1):
            c.da(f"Params.P_{n}", f"Logic.{n}", f"PubParams.SD_{k}")
    else:
        c.ev("Control.GO_UA", "Logic.START")
        c.ev("Control.GO_PARENT", "Logic.START")
    if results:
        c.da("UaEnable", "PubResults.QI")
        c.da("Params.IdResults", "PubResults.ID")
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
        c.ev("Logic.CMD", "EqCmd.REQ")
        c.ev("Logic.WAIT_START", "WaitT.START")
        c.ev("Logic.WAIT_STOP", "WaitT.STOP")
        c.ev("WaitT.EO", "Logic.WAIT_OVER")
        for k, v in enumerate(["C_Holder", "C_Command", "C_Arg", "C_Release"], 1):
            c.da(f"Logic.{v}", f"EqCmd.SD_{k}")
    c.ev("Logic.TIMER_START", "Timer.START")
    c.da("Logic.TimerDT", "Timer.DT")
    c.ev("Logic.TIMER_STOP", "Timer.STOP")
    c.ev("Timer.EO", "Logic.TIMER")
    c.write()


def make_composite_control(p: Project, pkg: str, name: str, spec: ModuleSpec):
    """SC_<name>: control of a module level skill (its children live in the Execute/Stop subapps)."""
    comp = spec.composites[name]
    params, results = comp.parameters, list(comp.results)
    equipment = spec.uses(name)
    make_params(p, pkg, name, params, results, equipment)
    iv = skill_interface(params, {})
    rtype = {r: result_type(spec, comp, r) for r in results}
    iv_all = {**iv, **{f"RI_{r}": t for r, t in rtype.items()}, "ExecError": "UINT"}
    ov = {"State": "USINT", "ErrorID": "UINT", **{f"P_{n}": pr.type for n, pr in params.items()}}
    c = Composite(p, pkg, f"SC_{name}", f"Control of module level skill {name}: OPC UA Start(Session, parameters...)/"
                  "Stop/Abort/Reset(Session) -> [Accepted, ErrorID]; GO starts the Execute sequence with the "
                  "parameters P_*; releases its equipment at the end",
                  {"INIT": (list(iv), "EInit"), "START": [], "HALT": [], "ABORT": [], "RESET": [],
                   "EXEC_DONE": [f"RI_{r}" for r in results], "EXEC_FAILED": ["ExecError"], "STOP_DONE": []},
                  {"INITO": ([], "EInit"), "GO": [f"P_{n}" for n in params], "HALT_O": [], "ABORT_O": [],
                   "RESET_O": [], "RUN_STOP": [], "SUCCESS": [], "FAILURE": ["ErrorID"]},
                  iv_all, ov, folder="Skills")
    wire_control(c, p, params, True, True, bool(equipment), bool(params or results))
    if params:
        c.fb("PubParams", p.publish(len(params)))
    if results:
        c.fb("PubResults", p.publish(len(results)))
    if equipment:
        c.fb("Release", q("SKILL_Release"))
        for eq in equipment:
            c.fb(f"Rel_{eq}", p.publish(4), QI="TRUE")
    chain = ["Control", "Params", "Owner", "Mode", "UaStart", "UaStop", "UaAbort", "UaReset", "PubState",
             *(["PubParams"] if params else []), *(["PubResults"] if results else []), "Act",
             *[f"Rel_{e}" for e in equipment]]
    c.chain("INIT", chain, ["PubState.REQ", *(["PubParams.REQ"] if params else []), "INITO"])
    if params:
        c.da("UaEnable", "PubParams.QI")
        c.da("Params.IdParams", "PubParams.ID")
        c.ev("Control.GO_UA", "Params.LATCH_UA")
        c.ev("Control.GO_PARENT", "Params.LATCH_DEF")
        c.ev("Params.LATCHED", "GO", "PubParams.REQ")
        for k, n in enumerate(params, 1):
            c.da(f"Params.P_{n}", f"P_{n}", f"PubParams.SD_{k}")
    else:
        c.ev("Control.GO_UA", "GO")
        c.ev("Control.GO_PARENT", "GO")
    if results:
        c.da("UaEnable", "PubResults.QI")
        c.da("Params.IdResults", "PubResults.ID")
        c.ev("EXEC_DONE", "PubResults.REQ")
        for k, r in enumerate(results, 1):
            c.da(f"RI_{r}", f"PubResults.SD_{k}")
    c.ev("EXEC_DONE", "Control.EXEC_DONE")
    c.ev("EXEC_FAILED", "Control.EXEC_FAILED")
    c.da("ExecError", "Control.ExecError")
    c.ev("STOP_DONE", "Control.STOP_DONE")
    c.ev("Control.RUN_STOP", "RUN_STOP")
    c.ev("Control.HALT_O", "HALT_O")
    c.ev("Control.ABORT_O", "ABORT_O")
    c.ev("Control.RESET_O", "RESET_O")
    if equipment:
        # On success the children have released the equipment (LastUse); on failure or abort the
        # skill releases it with the safe command, so a lost message still ends all off.
        c.ev("Control.FAILURE", "Release.REQ")
        c.ev("Control.ABORT_O", "Release.REQ")
        c.da("Token", "Release.Token")
        c.ev("Release.CNF", *[f"Rel_{e}.REQ" for e in equipment])
        for eq in equipment:
            c.da(f"Params.IdRel_{eq}", f"Rel_{eq}.ID")
            for k, v in enumerate(["Holder", "Command", "Arg", "Release"], 1):
                c.da(f"Release.{v}", f"Rel_{eq}.SD_{k}")
    c.write()


def result_type(spec: ModuleSpec, comp, result: str) -> str:
    """Type of a composite result (the type of the equipment input behind the step's result)."""
    step_name, _, res = comp.results[result].partition(".")
    step = next(s for s in comp.execute if s.name == step_name)
    skill = spec.skills[step.skill]
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
    rtypes = {}
    for r, src in results.items():
        st, _, res = src.partition(".")
        step = next(s for s in steps if s.name == st)
        sk = spec.skills[step.skill]
        rtypes[r] = spec.equipment[sk.equipment].inputs[sk.results[res]].type
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
    """Subapp of a module level skill: Control, Execute sequence and optional Stop sequence."""
    comp = spec.composites[name]
    _, inner = subapp(net, name, x, y, f"Module level skill {name}: {comp.description}".rstrip(": "),
                      {"INIT": ([], "EInit")}, {"INITO": ([], "EInit")})
    ua_root = wstr(spec.opcua_root)
    params = {"Module": wstr(spec.module), "UaRoot": ua_root, "UaPath": wstr(f"/Skills/{name}"), "UaEnable": "TRUE",
              "Methods": "TRUE" if comp.offered else "FALSE", "Token": wstr(name)}
    fb(inner, "Control", f"{spec.package}::SC_{name}", 1000, 1000, **params)
    sequence(inner, spec, "Execute", comp.execute, 8000, 1000, f"/Skills/{name}/Execute", name,
             f"{name}: execute sequence", comp.parameters, comp.results)
    ev = [("INIT", "Control.INIT"), ("Control.INITO", "Execute.INIT"), ("Control.GO", "Execute.START"),
          ("Control.HALT_O", "Execute.HALT"), ("Control.ABORT_O", "Execute.ABORT"), ("Control.RESET_O", "Execute.RESET"),
          ("Execute.DONE", "Control.EXEC_DONE"), ("Execute.FAILED", "Control.EXEC_FAILED")]
    da = [("Execute.ErrorID", "Control.ExecError")]
    da += [(f"Control.P_{n}", f"Execute.{n}") for n in comp.parameters]
    da += [(f"Execute.{r}", f"Control.RI_{r}") for r in comp.results]
    if comp.stop:
        # Published below .../Stopping: a "Stop" object would collide with the skill's Stop method.
        sequence(inner, spec, "Stop", comp.stop, 8000, 5000, f"/Skills/{name}/Stopping", name, f"{name}: stop sequence")
        ev += [("Execute.INITO", "Stop.INIT"), ("Stop.INITO", "INITO"), ("Control.RUN_STOP", "Stop.START"),
               ("Control.ABORT_O", "Stop.ABORT"), ("Control.RESET_O", "Stop.RESET"), ("Stop.DONE", "Control.STOP_DONE"),
               ("Stop.FAILED", "Control.STOP_DONE")]
    else:
        ev += [("Execute.INITO", "INITO"), ("Control.RUN_STOP", "Control.STOP_DONE")]
    connections(inner, ev, da)
    return name


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
    for i, name in enumerate(spec.composites):
        module_skill(net, spec, name, 2000 + i * 5000, 9000)
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
    events += [(a + ".INITO", z + ".INIT") for a, z in zip(chain, chain[1:])]
    connections(net, events, data)
    return app


# Groups of the application as the IDE shows them (the IDE 3.2 has no group colours): name, comment,
# columns and the grid pitch (x, y).
GROUPS = [
    ("ModuleLevel", "Module level: occupation, PackML state manager, start-up and the target's IO lines", 5, 5000, 3000),
    ("ModuleLevelSkills", "Module level skills: Control + Execute (+ Stop) sequences of skill primitives; OPC UA "
     "/Skills/<name>", 4, 5000, 2200),
    ("Procedures", "Procedures the module state manager runs while Resetting and Stopping", 4, 5000, 2200),
    ("SkillPrimitives", "Skill primitives: one equipment command until a sensor or a time; OPC UA /Skills/<name>", 4, 5500, 3800),
    ("EquipmentIO", "Equipment IO: the only owners of the IO points; skills command them over local channels", 4, 6500, 5000),
]
LEFT, TOP, GAP = 2800, 900, 1200     # room for parameter values left of a block, the group title, between groups


def group_layout(net, spec: ModuleSpec):
    """Arrange the application's blocks in one group each, stacked from top to bottom: module level,
    module level skills, procedures, a catalogue of skill primitives, equipment IO."""
    members = {
        "ModuleLevel": ["Boot", "GpioLines", "PwmLines", "Occupation", "Module"],
        "EquipmentIO": list(spec.equipment),
        "SkillPrimitives": [n for n, s in spec.skills.items() if s.offered],
        "ModuleLevelSkills": list(spec.composites),
        "Procedures": ["Resetting", "Stopping"],
    }
    blocks = {el.get("Name"): el for el in net if el.tag in ("FB", "SubApp")}
    y = 1000
    groups = []
    for name, comment, cols, dx, dy in GROUPS:
        names = [n for n in members[name] if n in blocks]
        if not names:
            continue
        rows = (len(names) + cols - 1) // cols
        width, height = LEFT + min(cols, len(names)) * dx, TOP + rows * dy
        groups.append(ET.Element("Group", Name=name, Comment=comment, x="1000", y=str(y), width=str(width),
                                 height=str(height), locked="false"))
        for i, n in enumerate(names):
            el = blocks[n]
            # A grouped block's position is relative to its group.
            el.set("x", str(LEFT + (i % cols) * dx))
            el.set("y", str(TOP + (i // cols) * dy))
            elem(el, "Attribute", Name="GroupName", Type="STRING", Value=name)
        y += height + GAP
    for i, g in enumerate(groups):
        net.insert(i, g)


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
    for app in apps.values():
        group_layout(app.find("SubAppNetwork"), spec)
    hide_init_connections(root)
    for i, (target, t) in enumerate(spec.targets.items()):
        device = elem(root, "Device", Name=device_name(target), Type=STD["FORTE_PC"], x=1000 + i * 3000, y=1000)
        elem(device, "Parameter", Name="MGR_ID", Value=wstr(f"{t.host}:{t.port}"))
        elem(device, "Attribute", Name="Profile", Type="STRING", Value="HOLOBLOC", Comment="device profile")
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
        make_equipment_view(p, spec.package, name, eq)
    for name, skill in spec.skills.items():
        make_skill(p, spec.package, name, skill, spec.equipment[skill.equipment] if skill.equipment else None)
    for name in spec.composites:
        make_composite_control(p, spec.package, name, spec)
    make_system(p, spec)
