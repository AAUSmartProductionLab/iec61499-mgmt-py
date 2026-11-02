# Repositories

All of AASPIRE's parts that the lab builds still share one repository,
[iec61499-mgmt-py](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py). Each top-level folder
there is a future repository of the GitHub organization `ap2030-project`, or part of one. The split
waits until after the CIRP paper (18 November 2026); until then the folder is where the code is.

<figure markdown="span">
  [![Each folder of the repository today, an arrow to the repositories it becomes, coloured by
  pillar](../figures/repository-map.png)](../figures/repository-map.png)
  <figcaption>Folders today (left) and the repositories they become (right), in their pillars'
  colours. Submodules are other repositories already; aaspire is the main repository, with this site.</figcaption>
</figure>

| Folder | Becomes | Pillar | Language | Page |
| --- | --- | --- | --- | --- |
| `aas-model/` (submodule) | aas-model | AAS | Python | [aas-model](../aas/aas-model.md) |
| `ontology/` | ontologies | AAS | Turtle, SHACL | [Ontologies](../aas/ontologies.md) |
| `iec61499-skill-lib/` | iec61499-skill-lib; skill-model (`modgen.spec`) | Reconfiguration; AAS | Python, 4diac XML | [Skill library](../reconfiguration/skill-lib.md) |
| `aas61499-tools/` | modsync, modplan, registration-service (`modreg`); skill-model | Reconfiguration, Planning, Integration | Python | [modsync](../reconfiguration/modsync.md), [modplan](../planning/modplan.md), [registration](../integration/registration.md) |
| `iec61499-mgmt-py/` | iec61499-mgmt-py | Reconfiguration | Python | [Management library](../reconfiguration/mgmt.md) |
| `runtime/` | forte-runtime; deploy-module (`install.sh`, the kit) | Reconfiguration; Deployment | PowerShell, C++ patches | [FORTE runtime](../reconfiguration/runtime.md) |
| `aas-camel-dmp/` (submodule) | aas-camel-dmp | Integration | Java | [DMP](../integration/dmp.md) |
| `iec61499-opcua-hmi/` (submodule) | modlink (the HMI repository is then archived) | Integration | Python | [modlink](../integration/modlink.md) |
| `line-agents/` | lineagents | Execution | Python | [Line agents](../execution/agents.md) |
| `planar-controller/` (submodule) | planar-controller | Execution | Python | [Planar controller](../execution/planar-controller.md) |
| `basyx-aas-web-ui/` (submodule) | basyx-aas-web-ui (a fork) | Interfaces | Vue, TypeScript | [Web UI](../interfaces/web-ui.md) |
| `deploy/` | deploy-server (`aas/`), deploy-module (`pi/`, `pi.py`) | Deployment | Compose, Python | [Deployment](../deployment/deploy.md) |
| `cell/` | aseptic-line | Lines | Python, YAML | [The aseptic line](../lines/aseptic-line.md) |
| `docs/` | aseptic-line (the working notes) | Lines | Markdown | below |
| `aaspire/` | aaspire (this site) | main | Markdown, draw.io | [This site](../how-to/this-site.md) |

## How they will come together

- **Only `aaspire` has submodules**, one level deep, in folders by pillar. Every other repository
  depends on the others by version: Python packages by tag, the ontologies as a package, container
  images by tag, FORTE by release.
- **One Python environment for development**: `aaspire` as a workspace with every Python part
  installed editable; the C++, Java and TypeScript parts build as images.
- **One command for the line in simulation**: a `compose.yaml` that starts the server stack, the
  simulated modules and one orchestrator.
- **Versions**: the parts by SemVer, `aaspire` by date (`2026.11` with the CIRP paper, `2027.01` with
  the demo).

Pinned, not the lab's: Eclipse 4diac FORTE, BaSyx's images, BehaviorTree.CPP, Groot2,
unified-planning, the IDTA templates. The project's first stack, AP2030-UNS (PackML stations over MQTT
run by behaviour trees), is AASPIRE's predecessor and is archived once what is still of use is copied
out.

## The working notes

The repository's `docs/` folder holds the notes the work was done by: what was built and learnt
([work.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/work.md)), the
design log, the plan ([next-steps.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/next-steps.md)),
the decisions, the papers' drafts and the figures. They stay with the line; this site is written from
them for a reader who was not there. The plan for the framework, its repositories and this site is
[framework-plan.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/framework-plan.md).
