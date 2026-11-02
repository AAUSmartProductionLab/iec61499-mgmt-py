# Planning: deciding from capabilities

<span class="pillar planning">Planning</span> Planning decides what to do from what the AASs say:
what a product's steps require and what the resources offer. It happens at two levels.

| Level | Question | Planner | Reads | Gives |
| --- | --- | --- | --- | --- |
| **The line** | Which resource does which step of an order, and in which order? | FOND-AAS (the colleagues'): FOND planners on PDDL | The resource AASs, the product's recipe | A policy, run as a behaviour tree by the centralized orchestrator |
| **A module** | The module offers the capability but has no skill for these values: which of its components' primitives, in which order? | [modplan](modplan.md): HTN with goal regression (GTPyhop) | The module's Capability Description | A new composite skill, described in the module's AAS, then created online by [modsync](../reconfiguration/modsync.md) |

The multi-agent orchestrator does the first by bidding instead of planning ahead
([line agents](../execution/agents.md)); a bid can rest on a skill that modplan plans and modsync
creates first.

## Capabilities as the planning domain

A module's Capability Description is enough to plan with. Besides what the module offers (Filling,
0.5 to 10 mL, realized by the skill Dispensing), it holds what each of its components' primitives can
do, each with what it needs, does and keeps: preconditions, postconditions and invariants as IDTA
02020 constraints. The lab's vocabulary says what each kind of capability does wherever it is used.
A capability the module could offer after a reconfiguration is therefore found from its AAS alone:
offered now, offered after a reconfiguration (by which description), or not offered.

## The parts

| Part | State |
| --- | --- |
| [modplan](modplan.md) | built: plan, check, discover, export to PDDL and HDDL |
| FOND-AAS | the colleagues'; to read the same resource AASs and take its goal from the same recipe |
| The Planner (web UI) | built: matches a recipe's steps to the resources and binds them ([web UI](../interfaces/web-ui.md)) |

Read further: [skill-planning.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/skill-planning.md).
