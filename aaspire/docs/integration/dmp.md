# DMP

<span class="pillar integration">Integration</span> The data-mapping processor, `aas-camel-dmp`: it
makes a published AAS run. An Operation invoked at the AAS server calls the module's OPC UA method,
and the module's values become rows in InfluxDB, without a configuration file. Java with Apache Camel
4, a fork of the Eclipse BaSyx DataBridge. Submodule `aas-camel-dmp/`.

<figure markdown="span">
  [![The module's AAS with its interface description, mapping configuration, skills and variables; the
  DMP's four steps; the module, InfluxDB and the stack on the right](../figures/dmp.png)](../figures/dmp.png)
  <figcaption>The DMP builds its routes from the mapping configurations on the AAS server (1, 2), runs
  them (3) and follows the server's events, so a module published a moment ago is mapped (4).</figcaption>
</figure>

## How it works

1. **Discover**: at start, the DMP lists the Asset Interfaces Mapping Configurations (AIMC) on the AAS
   server by their semanticId and reads each submodel they reference once: an interface description
   whole, any other submodel only where it is referenced. Shells are never read.
2. **Compile**: each mapping becomes one bundle of Apache Camel routes. Transformations arrive as Lua
   in the AIMC and are compiled in memory; a referenced element's value type types the values.
3. **Run**: an Operation invoked at the AAS server calls the module's OPC UA method; the module's
   values are written to the time series the module's Variables name; every call is logged in the
   module's Log series.
4. **Follow** the server's events (MQTT or Kafka): an event that can change a mapping re-reads only the
   changed submodel and recompiles only what depends on it; unchanged mappings keep their routes.

A client therefore needs nothing but the AAS server to run a skill: the agents' DMP executor, a
behaviour tree, a script in any language.

## In the lab's stack

The DMP is built into the stack's `dmp` image and starts with BaSyx, InfluxDB and Mosquitto
([Deployment](../deployment/deploy.md)):

```powershell
python deploy/aas.py up                          # the stack, the DMP on :8085
python deploy/aas.py status FillingModuleAAS     # what the DMP made of a module's mappings, and why one does not run
python deploy/aas.py rows FillingModuleAAS       # the latest row of each of the module's series
python -m pytest cell/tests/test_dmp_live.py --module-forte-exe <forte.exe>    # a module on FORTE through the DMP
```

The upstream DMP is Tristan Schwörer's; the submodule follows the user's fork with the lab's modules
(branch `lab-modules`) until it is merged. Its own README describes every mapping it can run.
