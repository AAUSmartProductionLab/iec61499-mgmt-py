# The aseptic line

<span class="pillar lines">Lines</span> The AP2030 line: an aseptic filling line for pharmaceutical
containers, built with AASPIRE. Its module specs and generated programs, the simulators, the AASs of
its resources, products and processes, and the evaluation. Folder `cell/`; becomes the `aseptic-line`
repository, with the working notes.

<figure markdown="span">
  [![The folders of cell/: modules, control and sim on the left; the example line's AASs and the
  evaluation in the middle; the AAS server, FORTE and the tests on the right](../figures/aseptic-line.png)](../figures/aseptic-line.png)
  <figcaption>Specs become programs (control/) and AASs (examples/); the simulator stands in for the
  hardware; the evaluation times each change online and by a restart.</figcaption>
</figure>

## The line

A planar motor table carries the containers on shuttles between the modules:

| Module | Does | State |
| --- | --- | --- |
| Filling | Doses a volume through a needle on a linear axis: a stepper motor through a TB6600 driver, a pump, a scale (simulated) | runs on its Raspberry Pi 5, the axis moving |
| Stoppering | Brings its head down onto the container with a linear axis; a small actuator presses the stopper in | runs on FORTE with simulated IO; its Raspberry Pi 5 named, its runtime and wiring next |
| Capping | Crimps a cap: a linear axis like filling's, the crimper simulated | planned |
| Inspection | A camera, triggered over OPC UA; the images to a store beside the AAS server | planned |
| Loading, unloading | A KUKA robot each, behind a Raspberry Pi that starts the robot's jobs | planned |

The products: a 2 mL vial, a prefilled syringe of 1 mL and a cartridge of 3 mL, each with its recipe,
and the process of each on the line.

## The folders

| Folder | Holds |
| --- | --- |
| `modules/` | The module specs (`filling.yaml`, `stoppering.yaml`; `planned/`: capping, inspection) |
| `control/` | The generated 4diac projects (`FillingModule`, `StopperingModule`), with the layouts arranged in the IDE |
| `sim/` | `module_sim.py`: a module's IO simulated over Modbus (axes, steppers, a servo); `run_module.py`: simulator, FORTE and the module at once; `module_ua.py`: a small OPC UA client |
| `examples/` | `example_line.py`: every AAS of the line built by modreg (the line, the planar table and its shuttles, the four modules and their components, the products, a process each), each process checked (`plan_check.py`), published with `--publish`; `precedence/`: the Production Sequence 4.0 examples; `describe.py`: the class diagrams |
| `eval/` | The paper's evaluation: `scenarios.py` (plug a module in; change a value; a written skill; a planned skill; the changeover to the syringe, each online and by a restart), `planners.py`, `figures.py`, `effort.py`, `results/` |
| `tests/` | The modules live on FORTE and against a Pi, through the DMP, the example line built and checked |

```powershell
python cell/sim/run_module.py cell/modules/filling.yaml          # a module with simulated IO
python cell/examples/example_line.py --out aas --publish http://localhost:8081
python cell/eval/scenarios.py --forte <forte.exe> --runs 5       # the evaluation
```

Read further: [modules.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/modules.md)
(the two modules and their hardware), [demo-modules.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/demo-modules.md)
(the other four), [aas-examples.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/aas-examples.md).
