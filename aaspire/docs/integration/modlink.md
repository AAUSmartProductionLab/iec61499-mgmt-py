# modlink

<span class="pillar integration">Integration</span> Runs a module's skills from its AAS over OPC UA. It
reads the AAS as plain JSON, follows its references to the OPC UA nodes, and calls the module the way
every module is called: occupy, bring it to Execute, start the skill, wait for its end, release. In the
HMI repository for now (submodule `iec61499-opcua-hmi/`); becomes the `modlink` repository.

<figure markdown="span">
  [![The four AAS submodels modlink follows by reference, modlink's Resource, Link and a run in six
  steps, and the module's OPC UA nodes below /Objects/Filling](../figures/modlink.png)](../figures/modlink.png)
  <figcaption>The AAS is resolved by references and meanings, never by names (1 to 4); one OPC UA
  connection per endpoint; a run in six steps.</figcaption>
</figure>

## Resolving by reference

1. **Capability Description**: each offered capability with its properties and ranges, and the skill
   that realizes it.
2. **Skills**: each skill's commands, each with its reference to an action of the interface; the Start
   Operation's inputs are the parameters, its outputs the results. The module's own commands (Occupy,
   Release, Reset, Start, Stop, Abort, Clear) are skills too.
3. **Asset Interfaces Description**: the endpoint and the browse path of every action and property.
4. **Mapping Configuration and Variables**: which property shows a skill's state, its error and each
   result.

A skill built online is found as soon as modsync has recorded its interface; no client changes.

## A run

The `Link` keeps one OPC UA connection per endpoint: it finds every node by its browse path (FORTE
numbers its nodes anew at every start), subscribes to every variable, reconnects with back-off and
makes one call at a time. A `Module` stands for one module and one occupation session:

1. occupy the module with a session id;
2. Clear, Reset and Start as its state needs, so the module is in Execute;
3. listen to the skill's State before anything is sent;
4. call `Skills/<Skill>/Start(Session, values)`; FORTE answers `[Accepted, ErrorID]` at once, and a refusal
   (NotReady, NotPermitted, Busy, OutOfRange) is raised;
5. the first end state after the start (Succeeded, Failed, Aborted) ends the run;
6. the results are read from the subscribed values; release.

`run_capability` asks which skill realizes a capability and runs it with the given values and the
skill's defaults for the rest.

## Who uses it

- **The HMI** (FastAPI): the modules from their AAS, their PackML state, skills with parameters and
  results, the sensors; operated through methods only.
- **The agents**' OPC UA executor ([line agents](../execution/agents.md)).
- Scripts and tests.

```powershell
cd iec61499-opcua-hmi
python run.py --aas http://localhost:8081        # every module registered there, at the endpoint its AAS names
python run.py --simulate filling,stoppering      # without a machine: a stand-in serves the same address space
```

modlink writes nothing into the AAS and never uses FORTE's management protocol: operating a module
never changes it. It does not plan, and it leaves the range check to the module, which refuses a value
out of range itself.

Read further: [tools.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/tools.md), section 4.
