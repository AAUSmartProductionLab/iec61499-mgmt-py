# Registration service

<span class="pillar integration">Integration</span> `modreg serve`: builds a resource's AAS from its
profile, checks it against the resource ontology, publishes it on the AAS server, and finds new
modules on the network by itself. Folder `aas61499-tools/modreg`; becomes the `registration-service`
repository.

<figure markdown="span">
  [![A Raspberry Pi announcing its OPC UA server and serving its manifest; the service's five steps
  from Discover to Publish; the AAS server and those who read it](../figures/registration.png)](../figures/registration.png)
  <figcaption>A module is found (1), its profiles fetched from beside FORTE (2), built into AASs (3),
  checked against ARSO (4) and published (5). A profile can also be sent by hand.</figcaption>
</figure>

## What it does

1. **Discover** (`--discover`): FORTE announces its OPC UA server by mDNS when it starts; the service
   notices a server it does not know.
2. **Fetch** the module's manifest from beside FORTE (`http://<Pi>:8088/manifest.json`): the profiles of
   the module's AAS and of its components' AASs. Or a profile arrives by hand: `POST /profiles`, or
   `modreg register`.
3. **Build**: each profile is read into its aas-model type, and the AAS is made from it.
4. **Check** against ARSO, closed: a broken restriction refuses the module; `--strict` also refuses
   what the ontology does not describe.
5. **Publish** to the AAS server, with the offered capabilities derived from the skills. A profile
   registered again unchanged is not published again.

The service keeps each profile, its AAS and the integrator's record in its store folder.

## Its endpoints

| Endpoint | For |
| --- | --- |
| `POST /profiles`, `GET /profiles`, `GET /profiles/<id>[/profile\|/aas\|/registration]`, `DELETE /profiles/<id>` | Registering, reading and removing a resource |
| `POST /check/<module>` | The Skill Editor: is this skill buildable on this module? |
| `POST /plan/<module>` | The Skill Editor and the Planner's Match and plan: plan a skill for a requirement ([modplan](../planning/modplan.md)); written, the offered capabilities derived anew |
| `POST /match` | The Planner's Match resources and Match and plan: which resources offer what a step requires, with the one matcher the agents, the plan check and the evaluation use (`modreg.match`) |
| `POST /capabilities/<module>` | The offered capabilities derived from the skills |
| `POST /process/<product>` | The Planner and the Configurator: the product's process AAS on a line, from the bindings, with the plan check's result |
| `GET /build/<id>`, `PUT /build/<id>` | The integrator's record of what was built |
| `GET /discovered`, `GET /health` | What discovery found; whether it runs |

## Use it

```powershell
python -m pip install -e ".[registration]"
python -m modreg serve --ontology ontology/ARSO --basyx http://localhost:8081 --discover   # on :8090
python -m modreg register filling --target pi --service http://localhost:8090   # a profile by hand
python -m modreg register filling --target pi --service http://localhost:8090 --check   # only check
python -m modsync pull --host 192.168.0.203 --register http://localhost:8090    # what runs on a module
```

`--register` also works with `modsync describe`, `push` and `watch`: a module is registered when it
comes online or changes. The plain `Resource` export of the lab's MQTT stations goes through the same
service.

!!! warning "The lab's AAS server"
    The lab's shared AAS server holds the live shells of the lab's stations; an AAS with the same ids
    would overwrite them. Publish there only with the lab's agreement. For work, run the
    [stack on your own PC](../deployment/deploy.md).

Read further: [aas-models.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/aas-models.md),
[agents.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/agents.md), section 2 (discovery).
