# Glossary

One word for one thing. The words in the left column are the ones this site uses; the right column
lists what the same thing was called in older notes, papers and code. The glossary is to be settled
with the colleagues who build the centralized orchestrator.

## The line and its parts

| Word | Means | Also called |
| --- | --- | --- |
| **resource** | Anything with an AAS that offers skills: a line, a module, a component, the planar table | asset, station, module |
| **module** | A resource with its own controller: an IEC 61499 program on FORTE, operated over OPC UA. The filling and the stoppering module are modules | station |
| **component** | A part of a module with its own AAS: a linear axis, a pump, a scale | equipment |
| **equipment item** | In the program, the block that owns a component's IO points (`EQ_<Item>`) | equipment IO block |
| **transfer point** | A place on the line where a product is handed over, e.g. a shuttle's pose at a module | station |
| **shuttle** | An xbot of the planar table, a resource of its own that carries a product | xbot, mover |
| **line** | The resources together, with an AAS of its own (`ProductionSystem`) | cell, production system |

## Skills and capabilities

| Word | Means | Also called |
| --- | --- | --- |
| **capability** | What a resource can do (offered) or what a product's step needs (required), with properties and their ranges: Filling with FillVolume 0.5 to 10 mL | function |
| **skill** | How a capability is invoked: commands (Start, Stop, Abort, Reset) with parameters and results, and a state | service |
| **skill primitive** | A skill of a component: one equipment command until a sensor or a time. A block type in the program (`SK_<Skill>`) | primitive, building block |
| **composite skill** | A skill made of other skills: a flow of primitives. In the program a subapplication of library and primitive instances | module level skill |
| **resource commands** | Occupy, Release, Reset, Start, Stop, Abort, Clear: the module's own commands, skills of the kind ModuleControl | module skills |
| **Built, Described** | Whether the running program carries a composite skill out (`Deployment` in the Skills submodel), or only its AAS describes it | deployed, planned |
| **occupation** | Who may command a module now: a session that occupies it, until it releases it | lock, reservation |

## Products, processes and orders

| Word | Means | Also called |
| --- | --- | --- |
| **recipe** | A product's steps without bindings: which capabilities, in which order, with which values (the Production Sequence of the product AAS) | plan, process sequence |
| **process** | The recipe bound to one line's resources and skills; its AAS is the process AAS | plan, production task |
| **order** | How many of a product, now: it starts a product agent per unit | job |
| **orchestrator** | What decides which resource does which step, and when: centralized (behaviour trees) or multi-agent (the agents) | controller, MES |

## Descriptions

| Word | Means | Also called |
| --- | --- | --- |
| **AAS** | Asset Administration Shell (IEC 63278): a resource's, product's or process's digital twin as submodels | shell, digital twin |
| **profile** | An AAS as the pydantic dump of its aas-model type, without what the type says anyway; what a vendor writes and the registration service builds from | description, minimal JSON configuration |
| **module spec** | The YAML a vendor-side generator makes a module from (`cell/modules/*.yaml`). Not needed once the module is delivered | spec, description |
| **module rules** | How a module's program is built so the tools can read and change it; a module names its rule set in its AAS (`RuleSet`) | contract |
| **the integrator's record** | What was built, in detail: every instance with its block type and type hash, the change log. Kept beside the AAS | Control Configuration |

## IEC 61499 and the runtime

| Word | Means |
| --- | --- |
| **FORTE** | Eclipse 4diac's IEC 61499 runtime; here built with every module's block types, for Windows and for the Raspberry Pi |
| **function block** | A block of an IEC 61499 program: basic (an ECC and algorithms), composite (a network inside) or a service interface block |
| **application, resource** | An IEC 61499 program (one per module) and the part of a device it runs on (`RES`) |
| **management protocol** | FORTE's port 61499: create, connect, write, read, start, query. How programs are deployed and changed online |
| **boot file** | The commands FORTE runs at start (`forte.fboot`): a module's program as deployed |
| **PackML** | The ISA-TR88.00.02 state machine a module follows: Stopped, Resetting, Idle, Execute, Stopping, Aborted, ... |

## Services

| Word | Means |
| --- | --- |
| **AAS server** | Eclipse BaSyx: the AAS environment, registries and discovery, where every part finds the AASs |
| **registration service** | Builds an AAS from a profile, checks it against the ontology, publishes it; finds modules on the network (`modreg serve`) |
| **DMP** | The data-mapping processor: carries an AAS Operation to a module's OPC UA method and the module's values to InfluxDB (`aas-camel-dmp`) |
| **AID, AIMC** | Asset Interfaces Description (where the endpoint and each action and property are) and Asset Interfaces Mapping Configuration (which interface element feeds which data), IDTA submodels |
| **Variables** | aas-model's submodel of a resource's state, measurements and log as time series, the values in InfluxDB |
