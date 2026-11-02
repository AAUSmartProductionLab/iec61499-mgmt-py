# Execution: running the line

<span class="pillar execution">Execution</span> A product is made by running its recipe's steps on the
line's resources. Which resource does which step, and when, is the orchestrator's decision. AASPIRE
runs one line with two orchestrators, and only the orchestration differs between them.

| Orchestrator | How it decides | Built by |
| --- | --- | --- |
| **Centralized** | FOND-AAS plans a policy for the order with PDDL from the AASs; the BT controller runs it as a behaviour tree (watched in Groot2) | the colleagues (Schwörer et al.) |
| **Multi-agent** | A product agent per unit asks for one step at a time; the resources' agents bid; the product agent chooses ([line agents](agents.md)) | this repository (`lineagents`) |

## What both share

| Shared | What it is |
| --- | --- |
| The models | The resource, product and process AASs: skills, capabilities, interfaces, variables; the product's recipe. Both start from the same order |
| The modules | ModLib's behaviour in IEC 61499: occupation, the PackML module state, each skill's state machine, the skills as OPC UA methods |
| Running a skill | The same five steps, by the same route (below) |
| Integration | Registration and discovery; the DMP |
| Reconfiguration | A planned or described skill created online by modsync before it runs |
| The line | The same modules, the [planar table](planar-controller.md), the simulators |

## Running a skill

Every orchestrator runs a skill on a module the same way, straight over OPC UA
([modlink](../integration/modlink.md)) or through the AAS server and the [DMP](../integration/dmp.md):

1. **occupy** the module with a session id: from then on only that session commands it;
2. **bring it to Execute** (Clear, Reset, Start, as its PackML state needs);
3. **start the skill** with its values; the module answers at once whether it accepts;
4. **wait for its end**: Succeeded, Failed or Aborted, with an error id and the results;
5. **release** the module.

Occupation is also the handover between the two orchestrators: whoever holds a module commands it, so
the line passes from one to the other between orders, once every module is released.

## One scenario for both

The comparison planned for the journal paper: one scenario of orders and events (a module failing, a
rush order, a module plugged in), run by both orchestrators and measured the same way: the time to
finish the orders, the reaction to a failure, the time until a module plugged in is used, and the work
to set each up.

Read further: [framework-plan.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/framework-plan.md),
section 1; [agents.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/agents.md).
