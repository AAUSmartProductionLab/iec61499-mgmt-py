# The Control Configuration: in the AAS or in the backend?

Proposal of 27 Oct 2026. **Decided the same day: option C, and built** (ARSO 0.10; `RuleSet` and
`Deployment` in the Skills submodel; the record kept by `modsync --records` in a folder or by the
registration service at `/build/<idShort>`). The question was: should a module's AAS keep the
Control Configuration submodel, or can it live in a backend that only modgen and modsync use?

**Recommendation in short:** keep two facts in the AAS: the rule set the program follows, and
whether each skill is built or only described. Move everything else into the integrator's backend
and take the Control Configuration submodel out of the AAS. Verifying, operating and changing a
module then need nothing from the backend, so the paper's claim still holds.

## 1. What it holds today and who uses each part

The submodel as `modreg` writes it ([profile.py](../aas61499-tools/modreg/profile.py),
`control_configuration`) and `modsync record` updates it
([desired.py](../aas61499-tools/modsync/desired.py), `record`), against ARSO's module
[control-configuration.ttl](../ontology/ARSO/Modules/control-configuration.ttl):

| Element | Holds | Written by | Read by | Needed for |
| --- | --- | --- | --- | --- |
| `Runtime/ManagementEndpoint` (and `Name`, `Resource`) | Where the module's FORTE is managed (`192.168.0.203:61499`) | modreg | `modsync verify` and `reconfigure`, as the default for `--host` (`desired.endpoint`) | Finding the module. It is the site's address, not something the vendor knows |
| `Rules` | The rule set the program is built by (`.../rules/module/1`) | modreg | Nobody yet | Saying that the program can be read back and changed online by the rules: the precondition of the whole method |
| `Instances` (`InstancePath`, `FBType`, `TypeHash`, `Skill`) | Which block is which skill or step | modreg; modsync record | modsync (`instances`): which composite skills are **built**, and a check that the recorded instances, types and hashes are still there; the projection (`50-resources.rq`): a skill is built when an instance refers to it; from that, `Availability = AfterReconfiguration` in the derived capabilities | The built-or-described distinction (used). The type and hash check (used, but see below) |
| `Types` (`Name`, `Hash`) | Every block type with the hash FORTE reports | modreg (from a read program) | Nobody | Nothing yet |
| `ModuleSpec`, `Target`, `Generator`, `ProgramDigest` | The spec file (a path in this repository), the target, "modgen", the digest of the generated program | modreg | Nobody | Provenance on the vendor's side. A delivered module has no spec, so these say nothing to anyone else |
| `SyncState`, `ReadAt`, `Differences` | Whether the program was what the spec generates when it was last read | modreg; modsync record | Nobody | A live state written into a description |
| `ChangeLog` | One entry per change: time, trigger, what was done | modsync record | Nobody | A history of changes |
| `ActiveProcedure` (in ARSO only) | A process AAS and the hashes of what is active | Nobody | Nobody | Planned, never built |

No client reads the submodel: not `modlink`, the HMI, the planner or the skill editor. Only modsync
and the capability derivation do, and the derivation only needs one bit per skill.

Two observations:

1. **The hashes never come from the vendor.** Every `TypeHash` in the AAS was read from a running
   FORTE (modreg reads it through modsync; record reads it after a change). A hash check therefore
   proves "unchanged since the last record", which is the integrator's own bookkeeping, not
   something the delivered module promises.
2. **The instance map follows from the rules.** A module level skill is the subapplication named
   like the skill, its steps are the instances named by their `NodeId`
   ([module-rules.md](module-rules.md), sections 3 and 5). `modsync` reads a program back by these
   rules without the map; the map only repeats them.

## 2. Three options

| | A. Keep it in the AAS | B. All of it in the backend | C. Two facts in the AAS, the rest in the backend |
| --- | --- | --- | --- |
| In the AAS | As today | Nothing about the build | The rule set; per skill whether it is built |
| In the backend | Nothing | Everything | Instances, types and hashes, endpoint, sync state, change log, provenance |
| The paper's claim | Holds | Holds for verifying and changing. But a client, the planner above all, can no longer tell a described skill from a built one without asking the backend | Holds; the AAS still says what can be changed and what is offered after a reconfiguration |
| The AAS | Carries implementation detail of IEC 61499 that only one tool reads, and site and repository details that do not belong in a delivered description | Technology-neutral | Technology-neutral but for one property that names the rule set |
| History of changes | Travels with the AAS | Only in the backend | Only in the backend (see section 4) |
| Work | None | Medium | Medium (section 5) |

**Why not A.** The submodel mixes three things: a statement the vendor makes (the rule set), the
integrator's record of what it built (instances, hashes, change log) and site and repository
details (the endpoint, the spec's path). Only the first belongs in what is delivered. The rest
makes every module's AAS carry IEC 61499 bookkeeping that no client reads, and a resource that is
not an IEC 61499 module (the ACOPOS 6D table, a Kuka robot) would have nothing to put there.

**Why not B.** The built-or-described bit is needed by clients: the planner's matching answers
"offered after a reconfiguration" from it, and an agent later bids on it. It has to be in the AAS.

## 3. Option C in detail

**In the AAS, in the Skills submodel:**

| Element | Where | Values | Written by | Read by |
| --- | --- | --- | --- | --- |
| `RuleSet` (xs:anyURI) | The Skills submodel, once | `https://smartproductionlab.aau.dk/rules/module/1` | The vendor (modreg) | modsync: refuses to change a module that names no rule set it knows |
| `Deployment` (xs:string) | Each skill of the kind Composite | `Described` (in the AAS, not in the program), `Built` | The skill editor writes `Described` for a new skill; `modsync record` writes `Built` | The derivation (`Availability`), the planner, the skill editor's overview, an agent |

This also answers an open question of [next-steps.md](next-steps.md) ("does a described skill get a
state of its own that a client can read?"): yes, `Deployment`.

A smaller variant without a new element: "built" is "has an `InterfaceReference`", since recording
a built skill gives it its interface (`modreg.offer`). It breaks for a built skill that is
deliberately not offered (`offered: false` in a spec; none exists today). The explicit property is
clearer.

**In the backend** (the integrator's record, one per module, keyed by the AAS id; kept by the
registration service `modreg serve` next to the profiles it already keeps):

- the management endpoint (or given on the command line, as `--host` is today);
- the instances with block types and hashes, as last read;
- the sync state and when it was read;
- the change log;
- for a module generated here, the provenance (spec, target, generator, program digest), which is
  really modgen's and could stay in the vendor's build output instead.

## 4. What is given up, and what to watch

- **The history of changes no longer travels with the module.** In pharmaceutical production,
  documented change control matters (GMP). That argues for a change record in an AAS eventually,
  but more likely in the process AAS or an AAS of its own for the line's changes than in each
  module's description. After the paper.
- **Another integrator's tool** would not see our record. It would read the program back by the
  rules and start its own, which is what modsync does on first contact anyway.
- **ARSO changes**: the Control Configuration module leaves ARSO (or stays as the schema of the
  backend's record), and two elements join the Skills module. ARSO is authoritative: this needs
  your go.

## 5. The work for option C

About one to two days, with tests passing after each step:

| # | Change | Where |
| --- | --- | --- |
| 1 | `RuleSet` and `Deployment` in ARSO's Skills module; the Control Configuration module out of the resource's submodels | `ontology/ARSO` (your go) |
| 2 | modreg writes `RuleSet` and `Deployment`, no Control Configuration | `modreg/model.py`, `profile.py`, templates regenerated |
| 3 | The backend's record: a JSON file per module in the service's folder; `GET` and `PUT /build/<shell>` | `modreg/service.py` |
| 4 | modsync: built skills from `Deployment` (with the program read back as the check); the record and the change log to the backend; `--host` or the backend for the endpoint | `modsync/desired.py`, `__main__.py` |
| 5 | The projection: a skill is built when its `Deployment` is `Built` | `ontology/PPRL/projection/50-resources.rq` |
| 6 | The skill editor writes `Deployment = Described` for a new skill; the planner reads it | web UI fork |
| 7 | The AASs on the local server and the test data rebuilt; docs and figures (`ppr-models.drawio`, `module-tools.drawio`) | |

If you choose C, it should be done before the paper's figures of a module's AAS are final, since
those figures list the submodels.
