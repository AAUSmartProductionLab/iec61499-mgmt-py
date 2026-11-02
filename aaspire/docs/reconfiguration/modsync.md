# modsync

<span class="pillar reconfiguration">Reconfiguration</span> Keeps a running IEC 61499 program and its AAS
in step. It reads what runs over FORTE's management protocol, compares it with what the AAS describes,
changes the program online where the module rules allow it, verifies the change and records it. Folder
`aas61499-tools/modsync`; becomes the `modsync` repository.

<figure markdown="span">
  [![The module's AAS on the left, modsync's six steps in the middle, FORTE and its boot file on the
  right](../figures/modsync.png)](../figures/modsync.png)
  <figcaption>What runs (1) and what is wanted (2) are compared (3); what may change online is guarded
  (4), applied (5), verified and recorded (6). BottomUpFilling is described in the AAS and created
  while the module runs.</figcaption>
</figure>

## The six steps

1. **Read** what runs: one snapshot over the management protocol (every instance with its type,
   every connection, every type's hash, values on demand), read back by the module rules into the
   module's structure: equipment, offered primitives, composite skills and their flows, procedures.
2. **Describe** what is wanted: the module's AAS and its components' AASs as a module spec without
   wiring. Refused already here: a step that runs a skill no component has, a constant outside the
   primitive's limits, two parallel branches on one component, a kind of step the rules do not know.
3. **Compare** and sort every difference: *create* (a skill described but not built), *write* (a
   constant, a default, a limit), *restart* (another flow or order: refused online), *record* (the
   integrator's record names what the program lacks: refused, the record is wrong).
4. **Guard**: values are written only while the module is Stopped, Idle or Aborted and nobody occupies
   it; a new skill is created in any state. A block type FORTE lacks means a new FORTE build: nothing
   is sent.
5. **Apply online**: write the changed values; create, write, connect and start the new skill's
   instances, built by modgen's own pattern; run INIT once through it, so its OPC UA nodes come up.
6. **Verify and record**: read back and compare with the AAS again; append the commands to the boot
   file, so a restart brings the changed program up; in the AAS, `Deployment = Built` and the new
   skill's interface (actions, properties, mappings), so clients find it; the integrator's record gets
   every instance with its block type and hash.

**modsync project** goes the other way: FORTE keeps the program, not the 4diac project, so the program
read back by the rules becomes an IDE project again, with the layout arranged in the IDE.

## What an online change costs

| Skill | Flow | Instances | Connections | Management commands |
| --- | --- | --- | --- | --- |
| Dispensing | 4 steps | 13 | 63 | 142 |
| DoubleDose | 5 steps | 15 | 73 | 165 |
| Checked | 6 steps, two decisions | 23 | 98 | 224 |
| Ready | a parallel block of two steps | 5 | 31 | 64 |

DoubleDose was created in 0.04 s on a PC and in 1.6 s in all on a Raspberry Pi 5, most of it the boot
file over SSH, while another skill ran. Verifying a module against its AAS takes about 0.15 s over the
network.

## Use it

```powershell
python -m modsync verify aas --host 192.168.0.203                 # is the module what its AAS describes?
python -m modsync verify aas --host 192.168.0.203 --record        # ... and write down what was found
python -m modsync reconfigure http://localhost:8081 --shell FillingModuleAAS --dry-run   # what would change
python -m modsync reconfigure aas --host 192.168.0.203            # change it online, verify, record
python -m modsync project --host 192.168.0.203                    # the 4diac project of what runs (projects/)
python -m modsync pull --host 192.168.0.203                       # which module runs there, its drift, its AAS
```

The AASs are a folder of AAS files or an AAS server; `reconfigure` puts the changed submodels back where
they came from, and the record goes to `--records` (a folder, `records/` by default, or the registration
service). Without `--host`, the record says where the module is managed. `--force` writes values even
while the module runs or is occupied.

The Python functions behind the commands are in `modsync/desired.py` (`load`, `read`, `differences`,
`reconfigure`, `record`, `store`); the agents call them to create a skill before they run it.

## What it does not do

It never calls a skill ([modlink](../integration/modlink.md) does). It never removes or reorders anything
online: that needs a restart, and the AAS does not hold the wiring of the rest of the program from
which a whole boot file could be made. It changes no block types.

Beside the AAS mode, modsync has an older mode against a module spec (`pull`, `push`, `watch`), the
vendor's and the lab's development tool; it is to be folded into the AAS mode.

Read further: [tools.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/tools.md),
section 3; [mapping.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/mapping.md).
