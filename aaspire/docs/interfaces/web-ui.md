# Web UI

<span class="pillar interfaces">Interfaces</span> `basyx-aas-web-ui`: the Eclipse BaSyx AAS web UI,
forked, with the lab's apps beside BaSyx's own views of the AASs: the Planner, the Skill Editor and the
Configurator, and to come the HMI and Orders. Vue and TypeScript. Submodule `basyx-aas-web-ui/` (the
user's fork, branch `feat/process-sequence-pharma`).

<figure markdown="span">
  [![The four apps on top, and what they read and write below: the AAS server with the product, process
  and resource AASs, the registration service and modsync](../figures/web-ui.png)](../figures/web-ui.png)
  <figcaption>The apps work on the AASs on the server; the registration service checks, plans and writes
  process AASs for them; modsync builds what the Skill Editor saved.</figcaption>
</figure>

## The apps

| App | Does | Where in the fork |
| --- | --- | --- |
| **Planner** | A product's recipe (its Production Sequence) as a graph, also in BPMN; each step's required capability matched against the resources' offered capabilities; a step bound to a resource, a skill and its inputs. Saving has the registration service write the process AAS | `src/pages/modules/ProcessSequence`, `ProcessSequenceBpmn` |
| **Skill Editor** | A module's composite skill as a flow of its components' primitives: sequences, parallel blocks, decisions; values within the primitives' limits; a new skill from an existing one. It asks the registration service to check a skill and to plan one, and saves it to the Skills submodel as `Described` | `ProcessSequence/skills` |
| **Configurator** | Products assembled from their parts; a line laid out on the planar table's grid (read from the table's AAS); the shuttles' routing kept in the line's AAS; a process AAS written for a product on the line | `src/pages/modules/Configurator` |
| **HMI** (to come) | The modules operated from their AAS, as the Python HMI does today with [modlink](../integration/modlink.md) | |
| **Orders** (to come) | An order sent to either orchestrator | |

Every change is a draft until it is reviewed and saved; existing AASs are read again and compared
before they are written, and only what changed is saved.

## Running it

The lab's AAS stack starts the web UI as an image, on `http://localhost:3000`, beside the AAS server
([Deployment](../deployment/deploy.md)). The Planner and the Skill Editor need the registration
service's address (`modreg serve`, port 8090), set in the Process Sequence editor.

To work on the apps themselves, the fork's own README and AGENTS.md describe the tooling (Node 24,
pnpm) and the checks (eslint, vitest, vue-tsc).

Read further: [skill-authoring.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/skill-authoring.md)
(the Skill Editor and the Planner, as decided), [locations-and-layout.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/locations-and-layout.md)
(the planar table's layout).
