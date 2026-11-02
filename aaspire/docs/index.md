# AASPIRE

**AAS-based Planning, Integration, Reconfiguration and Execution.** Plug and produce with the Asset
Administration Shell.

AASPIRE is the framework of the AP2030 project at the AAU Smart Production Lab. A production line is
described, planned, plugged together, changed and run from the Asset Administration Shells (AASs) of
its products, processes and resources. The line's modules run IEC 61499 programs on Eclipse 4diac
FORTE, each on a Raspberry Pi. Each module comes with an AAS that says what it offers and how it is
called; the tools read that AAS to operate the module, to check it and to change it while it runs.

<figure markdown="span">
  [![The framework: the web UI's apps on top; the AAS server with the product, process and resource AASs in
  the middle; Planning, Integration, Reconfiguration and Execution around it; the line's modules and the
  planar table below](figures/framework.png)](figures/framework.png)
  <figcaption>The AAS server holds the models every part reads and writes. Planning decides what to do,
  Integration plugs a resource in, Reconfiguration changes a running module, Execution runs the line. Click
  a figure to see it at full size.</figcaption>
</figure>

## The pillars

| Pillar | What it does | Parts |
| --- | --- | --- |
| <span class="pillar aas">AAS</span> | Describe what a resource, a product and a process are | [aas-model](aas/aas-model.md), [the ontologies](aas/ontologies.md) |
| <span class="pillar planning">Planning</span> | Decide what to do from capabilities | [modplan](planning/modplan.md); FOND-AAS (the colleagues') |
| <span class="pillar integration">Integration</span> | Plug in: register, discover, connect, map data | [registration service](integration/registration.md), [DMP](integration/dmp.md), [modlink](integration/modlink.md) |
| <span class="pillar reconfiguration">Reconfiguration</span> | Change a running resource from its AAS | [modsync](reconfiguration/modsync.md), [skill library](reconfiguration/skill-lib.md), [management library](reconfiguration/mgmt.md), [FORTE runtime](reconfiguration/runtime.md) |
| <span class="pillar execution">Execution</span> | Produce: run a product's steps on the line | [line agents](execution/agents.md), [planar controller](execution/planar-controller.md); the BT controller (the colleagues') |

Three more hold everything together: <span class="pillar interfaces">Interfaces</span> the [web UI's
apps](interfaces/web-ui.md), <span class="pillar deployment">Deployment</span> the [server stack and the
module on a Pi](deployment/deploy.md), and <span class="pillar lines">Lines</span>, a line built with
all of it: the [aseptic line](lines/aseptic-line.md).

## One line, two orchestrators

The same line is run in two ways, and only the orchestration differs: **centralized**, where a planner
(FOND-AAS) makes a policy for the order from the AASs and a behaviour tree runs it, and **multi-agent**,
where a product agent per unit asks for one step at a time and the resources' agents bid. Everything
below the orchestration is shared: the models, the modules, the way a skill is run, the integration
and the reconfiguration. [Execution](execution/index.md) says more.

## What the work shows

> A module that is delivered with an IEC 61499 program and an AAS can be verified, operated and
> changed online from those two alone, without the files it was generated from; new skills are
> planned from its skill and capability models and created online the same way.

That is the claim of the CIRP CMS paper (November 2026). The tools behind it are on this site:
[modsync](reconfiguration/modsync.md) verifies and changes, [modlink](integration/modlink.md) operates,
[modplan](planning/modplan.md) plans, and the [module rules](reconfiguration/index.md) are the contract
they share.

## Where to start

- **New to it:** this page, then a pillar's page; the [glossary](overview/glossary.md) has the words.
- **See a module run:** [run a module on a PC](how-to/simulation.md), with its IO simulated.
- **Put one on hardware:** [a module on a Raspberry Pi](how-to/raspberry-pi.md).
- **Change one while it runs:** [change a skill online](how-to/change-a-skill.md).
- **Find the code:** [repositories](overview/repositories.md) maps every part to its folder today and
  to its repository after the split.

!!! note "The state of this site"
    This is the first version of AASPIRE's documentation, written in November 2026 from the working
    notes in the repository's `docs/` folder. The parts still share one repository,
    [iec61499-mgmt-py](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py); the organization
    `ap2030-project` and its repositories are planned. Each page says what is built and what is not.
