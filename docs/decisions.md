# Decisions

What was decided, in the order it happened. The plan itself is in
[next-steps.md](next-steps.md); what is built in [work.md](work.md).

| Decision | Answer |
| --- | --- |
| May ARSO be extended for building blocks and for what a skill's Contract, Step and Implementation contain? | Yes |
| Validator closed or open? | Closed, as the SHACL validation of the generation project is |
| Fill volume | A time at a fixed flow rate; the volume decides the time |
| Who executes plans | A multi-agent system: an agent per product and per resource, I4.0 bidding; resource agents use the skills, the AAS and the reconfiguration tools |
| Products | Prefilled syringe, cartridge or vial, as in the planner's examples |
| Planning | By hand in the planner's web UI for now; an automatic planner may write the same submodels later |
| Which skills need a capability? (7 Oct) | A composite skill does; a primitive is a building block and needs none; Occupy and Release are access control and need none |
| Where are a skill's parameters? (6 Oct) | With the skill: the inputs of its Operation. The Parameters submodel is optional and does not hold them |
| Capability element (6 Oct) | As IDTA 02020: the template's id, the meaning as a supplemental id |
| What does a step's binding hold? (7 Oct) | The smallest change: a parameter the skill hands down is a reference to that parameter of the skill (it was its name as a string); a constant stays a value. What a step runs with shows at the interface anyway; the planner's own bindings and the HMI are unchanged |
| Where do a contract's terms come from when there is no spec? (7 Oct) | From the AAS manifest the module's vendor provides: the descriptive half of step 1.2 is that manifest, not a file of our own |
| How is a product or a plan described? (7 Oct) | Like a module: an AAS type on the pydantic model (aas-model) and a profile that is its dump, built by the same tool. No description format of our own. Done for the product with its plan (`ProductTypeAAS`); the vial of the example line is such a profile |
| What does a module carry as its manifest? (7 Oct) | The pydantic dump (the profile). It is what `modreg profile` writes today, from the module spec (the YAML file a module's program is generated from) and the running program; storing it on the module is not built (step 1.3) |
| The planner reads its own skill catalog, the modules publish ARSO Skills. Which holds? (7 Oct) | The resource's skill definition. The web UI and the planner are adjusted to read it (step 2.2) |
| Is a plain wait (Dwell) kept, and is Dispense a skill of its own? (8 Oct) | Dwell is removed for now (its block types stay in the history); Dispense is offered like every other primitive |
| What has an AAS? (8 Oct) | The production system, each of its six modules (Loading, Filling, Stoppering, Capping, Inspection, Unloading) and every active component of a module: filling pump and linear axis; stoppering piston and linear axis; cap crimper and linear axis; top and side camera; Kuka robot and gripper (loading and unloading). The bill of material of the resources and the hierarchy of skills follow from these |
| What does a linear axis offer? (8 Oct) | The same two skills in every module: `MoveAxis(Position)` and `Home`. The axes are stepper motors with a limit switch, as on a 3D printer: the controller keeps the position itself (home at the switch, then the time it steps), and the direction follows from where the axis is and where it is to go. **Done 8 Oct** in the generator and in the filling and stoppering modules, run on FORTE with the simulator |
| Which way do capabilities and skills refer? (8 Oct) | One way: a capability names the skill that realizes it. A skill does not refer back |
| What is the stoppering module made of? (8 Oct) | As the others: a linear axis and one small linear actuator (the piston). **Done 8 Oct** |
| Is there a scale? (8 Oct) | Not physically. It is a part of the filling module with a simulated weight; it is tared when the module resets (**done**). The weight following what was dispensed is not built |
| How many robots? (8 Oct) | One Kuka for loading and one for unloading, each with a Raspberry Pi of its own. How 4diac controls them comes later (likely: start program 1, 2 or 3) |
| How is a component's AAS named? (8 Oct) | One per component as built in, with an id of its own (filling linear axis); what kind it is, is shared by all of that kind |
| How does a Raspberry Pi get its runtime? (8 Oct) | By one script, `runtime/install.sh`: Docker if missing, FORTE from the repository (`runtime/bin`), GPIO and PWM. **Done 8 Oct**, run on a Raspberry Pi 5 |
| Which Pi runs which module? (8 Oct) | The Raspberry Pi 5 (192.168.0.134) the filling module, the Raspberry Pi 4 (192.168.0.191) the stoppering module. The Pi 4 still has to be renamed and to get the new runtime |
| How are the axes driven and kept right? (8 Oct) | RepRap Stepper Motor Driver v2.3 (A3982): Step, Dir and an inverted Enable. An ordinary limit switch at the top goes straight to the Pi. The position is counted, so every operation ends by homing (**done 8 Oct**). Speed assumes an 8 mm screw and half steps until measured |
| Where do a skill's block type, instance and contract go? (8 Oct) | "Do what you need to make it work": block type, instance and hash are in the Control Configuration (Instances, each pointing at its skill or step); the contract stays with the primitive; what a primitive occupies is its component |
| How does a product's value reach a skill's parameter? (8 Oct) | No link from skill to capability. The parameter carries the meaning of the capability property it sets (a semantic id), as the product's parameter does; the plan's step binds the value |
| The Skills structure (7 and 8 Oct) | **Built 8 Oct as ARSO 0.7:** a skill is its commands (Start, Stop, Abort, Reset), each with its interface reference, an Operation named like it and its steps; the module's own commands are a submodel (Module); primitives are in the AAS of their component; the line, each module and each component is an AAS, told apart by its asset type. Published on the local AAS server |
| Are the agents part of the CIRP paper? (8 Oct) | No, or only as future work. The paper is the reconfiguration of a module from its AAS; the bidding system follows it |
| How does a vial move between the modules? (8 Oct) | On the ACOPOS 6D magnetic levitation table: shuttles carry it. They are controlled by Python code, not by IEC 61499, and need transport agents of their own |
| Where does a reconfiguration come from? (8 Oct) | The AAS is the desired state: a reconfiguration is a change to the module's AAS that the tools carry into the program. The scope is the changeover ("a good scoping for the reconfiguration"). The Skills submodel says what is wanted, the Control Configuration what was built. **Tried 8 Oct** (`modsync verify`, `reconfigure`) |
| Which stepper driver? (8 Oct) | A TB6600 (ordered) replaces the RepRap Stepper Motor Driver v2.3, which never energised the motor. Step, direction and enable as before, no change in the program |
| What is old? (8 Oct) | Removed or archived on the user's go-ahead: the superseded plans and figures (`docs/archive`), the HMI interface documents, the installers of the tools on a Pi, `modsync`'s own AAS builder; the generator's test module `filler` is with the skill library's tests |
