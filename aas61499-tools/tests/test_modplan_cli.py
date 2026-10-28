"""python -m modplan on a folder of AAS files: plan, write the planned skill back, check it."""
import json
from pathlib import Path
import sys

from modgen import load
from modsync.aasjson import at, submodel

from modplan.__main__ import main

sys.path.insert(0, str(Path(__file__).parent))
from test_modsync_desired import aas                                                 # noqa: E402

SPECS = Path(__file__).resolve().parents[2] / "cell" / "modules"


def test_a_skill_is_planned_written_into_the_aas_and_checked(tmp_path, capsys):
    module, components = aas(load(SPECS / "filling.yaml"), "pi")
    for env in [module, *components]:
        (tmp_path / f"{env['assetAdministrationShells'][0]['idShort']}.json").write_text(json.dumps(env), encoding="utf-8")
    assert main(["plan", str(tmp_path), "--capability", "Filling", "--value", "FillVolume=2.0", "--result", "FillWeight",
                 "--name", "FillTwo", "--write"]) == 0
    said = capsys.readouterr().out
    assert "MoveAxis(Position=40.0)" in said and "FillTwo described" in said
    written = json.loads((tmp_path / "FillingModuleAAS.json").read_text(encoding="utf-8"))
    assert at(submodel(written, "Skills"), "FillTwo", "Deployment")["value"] == "Described"
    assert main(["check", str(tmp_path)]) == 0                                       # Dispensing and FillTwo hold
    assert "FillTwo: nothing that does not hold" in capsys.readouterr().out
    assert main(["plan", str(tmp_path), "--capability", "Filling", "--value", "FillVolume=2.0", "--result", "Nothing"]) == 1
