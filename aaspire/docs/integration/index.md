# Integration: plugging a resource in

<span class="pillar integration">Integration</span> A resource is plugged in when the line knows it:
its AAS is on the AAS server, checked, and its interface is mapped, so that anyone can call its skills
and read its values. Integration is the path from a module on the network to that state, and the two
ways in which a client then reaches the module.

## From a module on the network to a known resource

1. A module starts: FORTE runs its program and announces its OPC UA server on the network (mDNS).
2. The [registration service](registration.md) finds it, fetches the module's manifest (the profiles of
   its AAS and its components' AASs, served beside FORTE), builds the AASs, checks them against ARSO
   and publishes them on the AAS server.
3. The AAS server announces the new shell over MQTT. The [DMP](dmp.md) maps the module's interface; the
   agent manager starts the module's [resource agent](../execution/agents.md).

A module can also be registered by hand: a vendor or an engineer sends the profiles to the service.

## Two ways to call a module

| Way | How | For | Against |
| --- | --- | --- | --- |
| **Straight over OPC UA** | [modlink](modlink.md) reads the module's interface from its AAS and calls its methods: occupy, bring it to Execute, start the skill, follow its state, release | Fast; the state as it changes | What is done is not in the AAS's log |
| **Through the AAS server** | The client invokes the skill's Operation at the AAS server; the [DMP](dmp.md) calls the module's method and writes the values to InfluxDB | One way in for every client and language; every call logged | Slower: two services in between, the state read from the database |

Both orchestrators can use either; which one is a setting per resource. The proposal for the demo is
to go through the DMP for its log and to keep the direct way for speed.

## The parts

| Part | What | State |
| --- | --- | --- |
| [Registration service](registration.md) (`modreg serve`) | Builds, checks, discovers and publishes AASs; checks and plans for the Skill Editor; writes process AASs | built; its own and the colleagues' registration service to be joined into one |
| [DMP](dmp.md) (`aas-camel-dmp`) | Runs the mappings of the published AASs | built, in the lab's AAS stack |
| [modlink](modlink.md) | Runs a module's skills from its AAS over OPC UA | built; in the HMI repository for now |
| mqtt-schemas | The MQTT messages' JSON schemas | the colleagues'; kept if still needed |
