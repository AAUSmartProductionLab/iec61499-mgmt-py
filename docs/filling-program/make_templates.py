"""Make the templates students start a new piece of equipment and a new primitive from.

    python docs/filling-program/make_templates.py      (from the repository's root)

For each module students work on, modgen generates, from a copy of the module's spec, a neutral piece
of equipment `Template` (one input `MyInput`, one output `MyOutput`, the commands `Stop` and
`MyCommand`) and two primitives on it: `TemplateUntil` runs until `MyInput` says it is done (as
`Home`), `TemplateTimed` for the time its parameter `MyParameter` gives (as `Crimp`). Its types are
then marked: every pin, block, line and size that a student makes their own says YOUR OWN; the rest
is the same in every type of its kind and stays as copied. They go to
templates/<Project>/Type Library/ (next to templates/README.md, for the students), in the folders of
the project's own Type Library, with the sizes of PUBLISH, SUBSCRIBE and SERVER the templates use
that the project does not declare yet.
"""
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "iec61499-skill-lib"))
import modgen  # noqa: E402

OUT = ROOT / "docs/filling-program/templates"
MODULES = {"StopperingModule": "stoppering", "CappingModule": "capping"}

EQUIPMENT = {
    "description": "A piece of equipment to make your own: one input, one output, one command besides Stop",
    "inputs": {"MyInput": {"modbus": "d9", "gpio": {"line": 24, "bias": "pull_up", "active_low": True}}},
    "outputs": {"MyOutput": {"modbus": "c9", "gpio": 22}},
    "commands": {"Stop": {}, "MyCommand": ["MyOutput"]},
}
SKILLS = {
    "TemplateUntil": {"description": "A primitive to make your own: MyCommand until MyInput says it is done",
                      "equipment": "Template", "command": "MyCommand", "postcondition": "MyInput", "timeout": "2s"},
    "TemplateTimed": {"description": "A primitive to make your own: MyCommand for the time MyParameter gives",
                      "equipment": "Template", "command": "MyCommand", "after": "MyParameter",
                      "parameters": {"MyParameter": {"unit": "s", "minimum": 0.0, "maximum": 5.0, "default": 1.0,
                                                     "description": "How long it runs"}}},
}

OWN = "YOUR OWN"
TOP = {
    "EC": "the command table of your equipment, EC_<Equipment>",
    "EL": "the rules of your equipment, EL_<Equipment>",
    "EV": "the report form of your equipment, EV_<Equipment>",
    "EQ": "your equipment block, EQ_<Equipment>",
    "EP": "the port of your equipment, EP_<Equipment>",
    "SC": "the contract of your primitive, SC_<Primitive>",
    "SK": "your primitive, SK_<Primitive>",
}
PER = {"MyInput": "one per input pin", "MyOutput": "one per output pin", "MyParameter": "one per parameter"}

# The contract's two algorithms are its own, line by line (section 8.5 of the guide).
CONTRACT = {
    "Run.Timed": "TRUE: the time RunTime ends the run; FALSE: Run.Post ends it, and RunTime is its timeout",
    "Run.RunTime": "how long it runs (Timed) or may run (not Timed)",
    "Run.Command": "the command to send: its number in EC_, in the order of its table (0 Stop, 1 MyCommand, ...)",
    "Run.Arg": "the command's argument, e.g. a position; 0.0 for none",
    "Run.StopCommand": "the command sent when the run ends: 0 Stop (all off), or another",
    "Run.Pre": "the precondition: may it start?",
    "Run.Post": "the postcondition: is it done?",
    "Run.Inv": "the invariant: may it go on?",
}
IDPUB_TWO = ('with two inputs A and B: IdPub := CONCAT(CONCAT(CONCAT(CONCAT(CONCAT(CONCAT(CONCAT(CONCAT(CONCAT('
             '"opc_ua[WRITE;", UaRoot), "/Equipment/"), Name), "/A;"), UaRoot), "/Equipment/"), Name), "/B"), "]"); '
             'with none: IdPub := "";')

# The blocks inside a composite that are its own: (name, comment). The sizes count for equipment
# without a position.
BLOCKS = {
    "Logic": "Change Type to your EL_<Equipment>",
    "EqView": "Change Type to your EV_<Equipment>",
    "Driver": "Change Type to your EC_<Equipment>",
    "Contract": "Change Type to your SC_<Primitive>",
    "Port": "Change Type to your equipment's EP_<Equipment> (it is the same in every primitive of that equipment)",
    "SubCmd": "its size: SUBSCRIBE_<outputs + 2>",
    "PubState": "its size: PUBLISH_<inputs + 1>",
    "PubUa": "its size: PUBLISH_<inputs>; without inputs there is no PubUa",
    "EqState": "its size: SUBSCRIBE_<inputs + 1>",
    "EqCmd": "its size: PUBLISH_<outputs + 2>",
    "UaStart": "its size: SERVER_2_<1 + parameters>",
    "PubParams": "its size: PUBLISH_<parameters>; without parameters there is no PubParams",
}


def mine(name: str) -> str | None:
    """'one per input pin' and so on, for a name made from a placeholder."""
    return next((per for word, per in PER.items() if word in name), None)


def mark_algorithm(kind: str, name: str, text: str) -> str:
    lines = []
    for line in text.split("\n"):
        left = line.split(":=")[0].strip()
        if kind == "SC" and left in CONTRACT:
            lines.append(f"{line}  (* {OWN}: {CONTRACT[left]} *)")
        elif kind == "EL" and left == "IdPub":
            lines.append(f"(* {OWN}: the OPC UA variable of each input, {IDPUB_TWO} *)")
            lines.append(line)
        elif kind == "EC" and line.startswith(("IF ", "ELSIF ")):
            lines.append(f"{line}  (* {OWN}: one branch per command but Stop: IF Command = 1 for the first, "
                         f"ELSIF Command = 2 for the next, ... *)")
        elif kind == "EC" and line.startswith(" ") and mine(line):
            lines.append(f"{line}  (* {OWN}: the outputs this command switches on *)")
        elif kind == "EL" and left == "Publish":
            lines.append(f"{line}  (* {OWN}: one (X <> L_X) OR per input pin *)")
        elif "Template" in line:
            lines.append(f"{line}  (* {OWN}: the equipment item's name, as Name in EQ_ *)")
        elif mine(line):
            lines.append(f"{line}  (* {OWN}: {mine(line).replace('one per', 'one line per')} *)")
        else:
            lines.append(line)
    return "\n".join(lines)


def say(element, own: str) -> None:
    """Put what is the student's own in front of an element's comment."""
    element.set("Comment", f"{OWN}, {own}" + (f". {element.get('Comment')}" if element.get("Comment") else ""))


def mark(path: Path, kind: str) -> None:
    root = ET.parse(path).getroot()
    root.set("Comment", f"TEMPLATE for {TOP[kind]}: copy it under that name, then change what says {OWN}, "
                        f"and this comment; keep the rest as it is. " + root.get("Comment", ""))
    for var in root.iter():
        name = var.get("Name", "")
        if var.tag in ("VarDeclaration", "Event", "AdapterDeclaration") and mine(name):
            say(var, mine(name))
        elif var.tag == "VarDeclaration" and kind == "EQ" and name == "Name":
            say(var, "your equipment's name")
        elif var.tag == "VarDeclaration" and kind == "SK" and name == "Timeout":
            say(var, "how long a run may take")
        elif var.tag == "FB":
            own = (BLOCKS.get(name)
                   or name.startswith("In_") and f"{mine(name)}: IO_DI for a switch, IO_AI for an analog input"
                   or name.startswith("Out_") and f"{mine(name)}: IO_DO for a switched output, IO_AO for an analog one"
                   or mine(name) and f"{mine(name)}: SKILL_Param_<its type>")
            if own:
                say(var, own)
        elif var.tag == "Algorithm":
            st = var.find("ST")
            st.text = mark_algorithm(kind, name, st.text)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def main() -> None:
    for project, module in MODULES.items():
        if (OUT / project).exists():
            shutil.rmtree(OUT / project)
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch)
            spec = yaml.safe_load((ROOT / f"cell/modules/{module}.yaml").read_text(encoding="utf-8"))
            spec["equipment"]["Template"] = EQUIPMENT
            spec["skills"].update(SKILLS)
            (scratch / "spec.yaml").write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
            modgen.generate(modgen.load(scratch / "spec.yaml"), root=scratch, manifest=scratch / "types-manifest.json")
            made = scratch / "Type Library"
            have = ROOT / "cell/control" / project / "Type Library"
            for path in sorted(made.rglob("*.fbt")):
                rel = path.relative_to(made)
                generic = rel.parts[0] == "Generic" and not (have / rel).exists()
                if "Template" not in path.stem and not generic:
                    continue
                to = OUT / project / "Type Library" / rel
                to.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(path, to)
                if not generic:
                    mark(to, path.stem[:2])
                print(to.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
