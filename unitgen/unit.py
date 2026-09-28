"""Unit-specific types and system: one equipment CFB per equipment item, one skill CFB per skill.

Equipment ``EQ_<Name>`` owns its IO points (FORTE binds one FB per IO point), turns commands
from its local ``cmd`` channel into outputs (break before make) and publishes its inputs on
its ``state`` channel and over OPC UA.

Skill ``SK_<Name>`` is a behaviour-tree node: START -> SUCCESS or FAILURE(ErrorID). It holds one
equipment command while running, checks Requires/Invariant/Ensures on every equipment sample and
owns its parameters: each instance starts with its defaults (the instance's input values) and
offers ``SetParameters(Session, ...)`` over OPC UA, answered [Accepted, ErrorID] and refused
unless the caller holds the occupation, the values are in range and the skill is not running.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from .fbxml import STD, Basic, Composite, Project, connections, elem, fb, save, subapp, wstr
from .library import ERRORS, SKILL_STATES, cat, lit, loc, q
from .spec import Equipment, Skill, UnitSpec

IO_TYPE = {"BOOL": "DI", "LREAL": "AI"}


def make_equipment(p: Project, pkg: str, name: str, eq: Equipment):
    """EQ_<name> and its logic EL_<name>."""
    ins, outs = eq.inputs, list(eq.outputs)
    on = {o: [eq.code(c) for c, switched in eq.commands.items() if o in switched] for o in outs}
    targets = "\n".join(f"N_{o} := {' OR '.join(f'(Command = {c})' for c in on[o]) or 'FALSE'};" for o in outs)
    pub = []
    for i, s in enumerate(ins):
        pub += ["UaRoot", lit(f"/Equipment/") , "Name", lit(f"/{s}" + (";" if i < len(ins) - 1 else "]"))]
    b = Basic(p, pkg, f"EL_{name}",
              f"{name} logic: command -> outputs (break before make), inputs -> state channel",
              {"INIT": (["Unit", "Name", "UaRoot"], "EInit"), "CMD": ["Command"],
               "SAMPLE": [f"I_{s}" for s in ins], "DRIVEN": []},
              {"INITO": (["IdCmd", "IdState", "IdPub"], "EInit"), "DRIVE": [f"O_{o}" for o in outs],
               "STATE": list(ins)},
              {"Unit": "WSTRING", "Name": "WSTRING", "UaRoot": "WSTRING", "Command": "USINT",
               **{f"I_{s}": i.type for s, i in ins.items()}},
              {"IdCmd": "WSTRING", "IdState": "WSTRING", "IdPub": "WSTRING", **{f"O_{o}": "BOOL" for o in outs},
               **{s: i.type for s, i in ins.items()}},
              {f"N_{o}": "BOOL" for o in outs}, folder="Equipment/Base")
    b.state("START")
    b.state("Init", f"IdCmd := {cat(lit('loc['), 'Unit', lit('/'), 'Name', lit('/cmd]'))};\n"
                    f"IdState := {cat(lit('loc['), 'Unit', lit('/'), 'Name', lit('/state]'))};\n"
                    f"IdPub := {cat(lit('opc_ua[WRITE;'), *pub)};", "INITO")
    # Like a PLC scan, the output image is rewritten every cycle: FORTE's Modbus client drops a
    # write sent while it is not connected, and a cyclic write heals that and reconnects.
    b.state("Sample", "\n".join(f"{s} := I_{s};" for s in ins), "STATE", ["DRIVE"])
    # Outputs that stay on are kept, all others switched off first; then the new set is switched on.
    b.state("Break", targets + "\n" + "\n".join(f"O_{o} := O_{o} AND N_{o};" for o in outs), "DRIVE")
    b.state("Make", targets + "\n" + "\n".join(f"O_{o} := N_{o};" for o in outs), "DRIVE")
    b.trans("START", "Init", "INIT")
    b.trans("START", "Sample", "SAMPLE")
    b.trans("START", "Break", "CMD")
    b.trans("Init", "START", "1")
    b.trans("Sample", "START", "1")
    b.trans("Break", "Make", "DRIVEN")
    b.trans("Make", "START", "DRIVEN")
    b.write()

    iv = {"Unit": "WSTRING", "Name": ("WSTRING", wstr(name)), "UaRoot": "WSTRING", "UaEnable": "BOOL",
          "IoBackend": ("USINT", "2"), "CycleTime": ("TIME", "T#50ms")}
    for s, i in ins.items():
        iv[f"{s}_Modbus"], iv[f"{s}_Gpio"] = "WSTRING", "STRING"
        if i.type == "LREAL":
            iv[f"{s}_Scale"] = ("LREAL", repr(i.scale))
    for o in outs:
        iv[f"{o}_Modbus"], iv[f"{o}_Gpio"] = "WSTRING", "STRING"
    c = Composite(p, pkg, f"EQ_{name}", (eq.description or name) + "; owns its IO points; commands "
                  + ", ".join(f"{k}={eq.code(k)}" for k in eq.commands),
                  {"INIT": (list(iv), "EInit")}, {"INITO": ([], "EInit")}, iv, {}, folder="Equipment")
    c.fb("Logic", f"{pkg}::EL_{name}")
    c.fb("SubCmd", p.subscribe(1), QI="TRUE")
    c.fb("PubState", p.publish(len(ins)), QI="TRUE")
    c.fb("PubUa", p.publish(len(ins)))
    for s, i in ins.items():
        c.fb(f"In_{s}", q("IO_" + IO_TYPE[i.type]))
    for o in outs:
        c.fb(f"Out_{o}", q("IO_DO"))
    c.fb("Cycle", STD["E_CYCLE"])
    c.chain("INIT", ["Logic", "SubCmd", "PubState", "PubUa", *[f"In_{s}" for s in ins], *[f"Out_{o}" for o in outs]],
            ["Cycle.START", "INITO"])
    for v in ["Unit", "Name", "UaRoot"]:
        c.da(v, "Logic." + v)
    c.da("Logic.IdCmd", "SubCmd.ID")
    c.da("Logic.IdState", "PubState.ID")
    c.da("Logic.IdPub", "PubUa.ID")
    c.da("UaEnable", "PubUa.QI")
    c.da("CycleTime", "Cycle.DT")
    c.ev("SubCmd.IND", "Logic.CMD")
    c.da("SubCmd.RD_1", "Logic.Command")
    reads = [f"In_{s}" for s in ins]
    c.ev("Cycle.EO", reads[0] + ".REQ")
    for a, z in zip(reads, reads[1:]):
        c.ev(a + ".CNF", z + ".REQ")
    c.ev(reads[-1] + ".CNF", "Logic.SAMPLE")
    for k, (s, i) in enumerate(ins.items(), 1):
        c.da("IoBackend", f"In_{s}.Backend")
        c.da(f"{s}_Modbus", f"In_{s}.ModbusId")
        c.da(f"{s}_Gpio", f"In_{s}.GpioName")
        if i.type == "LREAL":
            c.da(f"{s}_Scale", f"In_{s}.Scale")
        c.da(f"In_{s}.IN", f"Logic.I_{s}")
        c.da(f"Logic.{s}", f"PubState.SD_{k}", f"PubUa.SD_{k}")
    c.ev("Logic.STATE", "PubState.REQ", "PubUa.REQ")
    writes = [f"Out_{o}" for o in outs]
    c.ev("Logic.DRIVE", writes[0] + ".REQ")
    for a, z in zip(writes, writes[1:]):
        c.ev(a + ".CNF", z + ".REQ")
    c.ev(writes[-1] + ".CNF", "Logic.DRIVEN")
    for o in outs:
        c.da("IoBackend", f"Out_{o}.Backend")
        c.da(f"{o}_Modbus", f"Out_{o}.ModbusId")
        c.da(f"{o}_Gpio", f"Out_{o}.GpioName")
        c.da(f"Logic.O_{o}", f"Out_{o}.OUT")
    c.write()


def make_skill(p: Project, pkg: str, name: str, skill: Skill, eq: Equipment):
    """SK_<name> and its logic SL_<name>."""
    params, ins = skill.parameters, eq.inputs
    st, e = SKILL_STATES, ERRORS
    base = cat("UaRoot", "UaPath")
    pub = [base, lit("/State;"), base, lit("/ErrorID")]
    for n in params:
        pub += [lit(";"), base, lit(f"/Parameters/{n}")]
    ranges = [f"(S_{n} >= {pr.literal(pr.minimum)})" for n, pr in params.items() if pr.minimum is not None]
    ranges += [f"(S_{n} <= {pr.literal(pr.maximum)})" for n, pr in params.items() if pr.maximum is not None]
    stop, drive = eq.code(next(iter(eq.commands))), eq.code(skill.command)
    b = Basic(p, pkg, f"SL_{name}",
              f"{name}: Requires {skill.requires}; Ensures {skill.ensures}; Invariant {skill.invariant}; "
              f"holds {skill.equipment}.{skill.command} while running",
              {"INIT": (["Unit", "UaRoot", "UaPath", "Equipment", *[f"D_{n}" for n in params]], "EInit"),
               "OWNER_CHG": ["Owner"], "SETP": ["Session", *[f"S_{n}" for n in params]], "START": [],
               "SAMPLE": list(ins), "TIMEOUT": []},
              {"INITO": (["IdSetp", "IdPub", "IdEqState", "IdEqCmd"], "EInit"), "CMD": ["Command"],
               "WD_START": [], "WD_STOP": [], "PUB": ["State", "ErrorID", *params],
               "RSP_SETP": ["Accepted", "SetpError"], "SUCCESS": [], "FAILURE": ["ErrorID"]},
              {"Unit": "WSTRING", "UaRoot": "WSTRING", "UaPath": "WSTRING", "Equipment": "WSTRING",
               **{f"D_{n}": pr.type for n, pr in params.items()}, "Owner": "WSTRING", "Session": "WSTRING",
               **{f"S_{n}": pr.type for n, pr in params.items()}, **{s: i.type for s, i in ins.items()}},
              {"IdSetp": "WSTRING", "IdPub": "WSTRING", "IdEqState": "WSTRING", "IdEqCmd": "WSTRING",
               "Command": "USINT", "State": "USINT", "ErrorID": "UINT", "Accepted": "BOOL", "SetpError": "UINT",
               **{n: (pr.type, pr.literal()) for n, pr in params.items()}},
              {"Owned": "BOOL", "InRange": "BOOL"}, folder="Skills/Logic")
    b.state("START")
    b.state("Init", f"IdSetp := {cat(lit('opc_ua[CREATE_METHOD;'), base, lit('/SetParameters]'))};\n"
                    f"IdPub := {cat(lit('opc_ua[WRITE;'), *pub, lit(']'))};\n"
                    f"IdEqState := {cat(lit('loc['), 'Unit', lit('/'), 'Equipment', lit('/state]'))};\n"
                    f"IdEqCmd := {cat(lit('loc['), 'Unit', lit('/'), 'Equipment', lit('/cmd]'))};\n"
                    + "".join(f"{n} := D_{n};\n" for n in params)
                    + f"State := {st['Idle']};\nErrorID := 0;", "INITO")
    b.state("Setp", 'Owned := (Session = Owner) AND (Owner <> "");\n'
                    f"InRange := {' AND '.join(ranges) or 'TRUE'};\nAccepted := FALSE;\n"
                    f"IF NOT Owned THEN\n  SetpError := {e['NotPermitted']};\n"
                    f"ELSIF NOT InRange THEN\n  SetpError := {e['OutOfRange']};\nELSE\n"
                    + "".join(f"  {n} := S_{n};\n" for n in params)
                    + "  Accepted := TRUE;\n  SetpError := 0;\nEND_IF;", "RSP_SETP", ["PUB"])
    b.state("SetpBusy", f"Accepted := FALSE;\nSetpError := {e['Busy']};", "RSP_SETP")
    b.state("Check")
    b.state("Rejected", f"State := {st['Failed']};\nErrorID := {e['PreconditionViolated']};", "FAILURE", ["PUB"])
    b.state("Run", f"Command := {drive};\nState := {st['Running']};\nErrorID := 0;", "CMD", ["WD_START", "PUB"])
    b.state("Running")
    b.state("Succeeded", f"Command := {stop};\nState := {st['Succeeded']};\nErrorID := 0;",
            "CMD", ["WD_STOP", "SUCCESS", "PUB"])
    b.state("Unsafe", f"Command := {stop};\nState := {st['Failed']};\nErrorID := {e['InvariantViolated']};",
            "CMD", ["WD_STOP", "FAILURE", "PUB"])
    b.state("TimedOut", f"Command := {stop};\nState := {st['Failed']};\nErrorID := {e['Timeout']};",
            "CMD", ["FAILURE", "PUB"])
    b.trans("START", "Init", "INIT")
    b.trans("START", "Setp", "SETP")
    b.trans("START", "Check", "START")
    b.trans("Check", "Rejected", f"NOT ({skill.requires})")
    b.trans("Check", "Succeeded", skill.ensures)          # already there: succeed without driving
    b.trans("Check", "Run", "1")
    b.trans("Run", "Running", "1")
    b.trans("Running", "Unsafe", f"SAMPLE[NOT ({skill.invariant})]")
    b.trans("Running", "Succeeded", f"SAMPLE[{skill.ensures}]")
    b.trans("Running", "TimedOut", "TIMEOUT")
    b.trans("Running", "SetpBusy", "SETP")
    b.trans("SetpBusy", "Running", "1")
    for s in ["Init", "Setp", "Rejected", "Succeeded", "Unsafe", "TimedOut"]:
        b.trans(s, "START", "1")
    b.write()

    iv = {"Unit": "WSTRING", "UaRoot": "WSTRING", "UaPath": "WSTRING", "UaEnable": "BOOL",
          "Equipment": ("WSTRING", wstr(skill.equipment)), "Timeout": ("TIME", skill.timeout),
          **{n: (pr.type, pr.literal()) for n, pr in params.items()}}
    desc = "; ".join(f"{n} [{pr.unit or '-'}] {pr.minimum}..{pr.maximum}, default {pr.default}"
                     for n, pr in params.items()) or "none"
    c = Composite(p, pkg, f"SK_{name}", f"{skill.description or name} (parameters: {desc}). START -> SUCCESS or "
                  "FAILURE; OPC UA SetParameters(Session, ...) -> [Accepted, ErrorID]; parameter inputs are the "
                  "instance's defaults", {"INIT": (list(iv), "EInit"), "START": []},
                  {"INITO": ([], "EInit"), "SUCCESS": [], "FAILURE": ["ErrorID"]}, iv,
                  {"State": "USINT", "ErrorID": "UINT"}, folder="Skills")
    c.fb("Logic", f"{pkg}::SL_{name}")
    c.fb("Owner", q("UNIT_OwnerView"))
    c.fb("Setp", p.server(2, 1 + len(params)))
    c.fb("EqState", p.subscribe(len(ins)), QI="TRUE")
    c.fb("EqCmd", p.publish(1), QI="TRUE")
    c.fb("Wd", STD["E_DELAY"])
    c.fb("PubUa", p.publish(2 + len(params)))
    c.chain("INIT", ["Logic", "Owner", "Setp", "EqState", "EqCmd", "PubUa"], ["PubUa.REQ", "INITO"])
    for v in ["Unit", "UaRoot", "UaPath", "Equipment"]:
        c.da(v, "Logic." + v)
    for n in params:
        c.da(n, f"Logic.D_{n}")
    c.da("Unit", "Owner.Unit")
    c.ev("Owner.CHG", "Logic.OWNER_CHG")
    c.da("Owner.Owner", "Logic.Owner")
    c.da("Logic.IdSetp", "Setp.ID")
    c.da("UaEnable", "Setp.QI", "PubUa.QI")
    c.ev("Setp.IND", "Logic.SETP")
    c.da("Setp.RD_1", "Logic.Session")
    for k, n in enumerate(params, 2):
        c.da(f"Setp.RD_{k}", f"Logic.S_{n}")
    c.ev("Logic.RSP_SETP", "Setp.RSP")
    c.da("Logic.Accepted", "Setp.SD_1")
    c.da("Logic.SetpError", "Setp.SD_2")
    c.da("Logic.IdEqState", "EqState.ID")
    c.ev("EqState.IND", "Logic.SAMPLE")
    for k, s in enumerate(ins, 1):
        c.da(f"EqState.RD_{k}", f"Logic.{s}")
    c.da("Logic.IdEqCmd", "EqCmd.ID")
    c.ev("Logic.CMD", "EqCmd.REQ")
    c.da("Logic.Command", "EqCmd.SD_1")
    c.da("Timeout", "Wd.DT")
    c.ev("Logic.WD_START", "Wd.START")
    c.ev("Logic.WD_STOP", "Wd.STOP")
    c.ev("Wd.EO", "Logic.TIMEOUT")
    c.da("Logic.IdPub", "PubUa.ID")
    c.ev("Logic.PUB", "PubUa.REQ")
    c.da("Logic.State", "PubUa.SD_1", "State")
    c.da("Logic.ErrorID", "PubUa.SD_2", "ErrorID")
    for k, n in enumerate(params, 3):
        c.da(f"Logic.{n}", f"PubUa.SD_{k}")
    c.ev("START", "Logic.START")
    c.ev("Logic.SUCCESS", "SUCCESS")
    c.ev("Logic.FAILURE", "FAILURE")
    c.write()


def application(root, spec: UnitSpec):
    """The unit application: occupation, state manager, equipment and one subapp per procedure."""
    pkg, ua = spec.package, wstr(spec.opcua_root)
    unit = wstr(spec.unit)
    app = elem(root, "Application", Name=spec.unit, Comment=f"Unit {spec.unit} (generated by unitgen)")
    net = elem(app, "SubAppNetwork")
    # Wide spacing: the IDE checks for overlapping blocks, including the resource's own START
    # block at the origin, and a mapped block keeps its application coordinates.
    fb(net, "Boot", STD["E_RESTART"], 2000, 200)
    fb(net, "Occupation", q("UNIT_Occupation"), 5000, 200, Unit=unit, UaRoot=ua, UaEnable="TRUE")
    fb(net, "Unit", q("UNIT_StateManager"), 9000, 200, Unit=unit, UaRoot=ua, UaEnable="TRUE")
    chain = ["Occupation", "Unit"]
    for i, (name, eq) in enumerate(spec.equipment.items()):
        io = {}
        for s, inp in eq.inputs.items():
            io[f"{s}_Modbus"] = wstr(spec.modbus_id(inp.modbus, write=False))
            io[f"{s}_Gpio"] = f"'{name}_{s}'"
        for o, out in eq.outputs.items():
            io[f"{o}_Modbus"] = wstr(spec.modbus_id(out.modbus, write=True))
            io[f"{o}_Gpio"] = f"'{name}_{o}'"
        fb(net, name, f"{pkg}::EQ_{name}", 2000 + i * 5000, 3000, Unit=unit, UaRoot=ua, UaEnable="TRUE", **io)
        chain.append(name)
    events, data = [("Boot.COLD", "Occupation.INIT"), ("Boot.WARM", "Occupation.INIT")], []
    for x, (state, steps) in enumerate(spec.procedures.items()):
        _, inner = subapp(net, state, 2000 + x * 5000, 7000, f"PackML {state} procedure: skill instances chained "
                          "SUCCESS -> START; any FAILURE fails the procedure",
                          {"INIT": ([], "EInit"), "START": []}, {"INITO": ([], "EInit"), "DONE": [], "FAILED": []})
        ev = [("INIT", steps[0] + ".INIT"), ("START", steps[0] + ".START"),
              (steps[-1] + ".INITO", "INITO"), (steps[-1] + ".SUCCESS", "DONE")]
        for i, s in enumerate(steps):
            fb(inner, s, f"{pkg}::SK_{s}", 1000 + i * 4000, 1000, Unit=unit, UaRoot=ua,
               UaPath=wstr(f"/{state}/{s}"), UaEnable="TRUE")
            ev.append((s + ".FAILURE", "FAILED"))
        for a, z in zip(steps, steps[1:]):
            ev += [(a + ".INITO", z + ".INIT"), (a + ".SUCCESS", z + ".START")]
        connections(inner, ev, [])
        chain.append(state)
        upper = state.upper()
        events += [(f"Unit.{upper}", f"{state}.START"), (f"{state}.DONE", f"Unit.{upper}_DONE"),
                   (f"{state}.FAILED", f"Unit.{upper}_FAILED")]
    events += [(a + ".INITO", z + ".INIT") for a, z in zip(chain, chain[1:])]
    connections(net, events, data)
    return app


def make_system(p: Project, spec: UnitSpec):
    """Write the .sys: the unit application mapped to resource RES of one FORTE_PC device."""
    root = ET.Element("System", Name=p.name, Comment=f"Unit {spec.unit}, generated from its unit specification")
    elem(root, "Identification", Standard="61499-2")
    app = application(root, spec)
    device = elem(root, "Device", Name="FORTE_PC", Type=STD["FORTE_PC"], x=1000, y=1000)
    elem(device, "Parameter", Name="MGR_ID", Value=wstr("localhost:61499"))
    elem(device, "Attribute", Name="Profile", Type="STRING", Value="HOLOBLOC", Comment="device profile")
    elem(device, "Attribute", Name="Color", Type="STRING", Value="255,190,111")  # required by the IDE
    res = elem(device, "Resource", Name="RES", Type=STD["EMB_RES"], x=0, y=0)
    # As the IDE writes it: the resource network holds only resource-local FBs, and each mapped
    # element is a Mapping to the resource; the IDE rebuilds the mapped copies itself. Copies
    # in the resource network make the IDE's system editor fail ("Could not load system").
    elem(res, "FBNetwork")
    for child in app.find("SubAppNetwork"):
        if child.tag in ("FB", "SubApp"):
            elem(root, "Mapping", From=f"{spec.unit}.{child.get('Name')}", To="FORTE_PC.RES")
    save(root, p.root / f"{p.name}.sys")


def make_unit(p: Project, spec: UnitSpec):
    """Write the unit's equipment and skill types and its system."""
    for name, eq in spec.equipment.items():
        make_equipment(p, spec.package, name, eq)
    for name, skill in spec.skills.items():
        make_skill(p, spec.package, name, skill, spec.equipment[skill.equipment])
    make_system(p, spec)
