# FORTE runtime

<span class="pillar reconfiguration">Reconfiguration</span> Eclipse 4diac FORTE built with every module's
block types: for Windows (the modules with simulated IO) and for the Raspberry Pi (aarch64, real IO).
The scripts that check and export the 4diac projects, patch and build FORTE, package it and put it on a
Pi. Folder `runtime/`; becomes the `forte-runtime` repository.

<figure markdown="span">
  [![The 4diac projects on the left, four steps to a FORTE binary in the middle, and where it runs on
  the right](../figures/runtime.png)](../figures/runtime.png)
  <figcaption>Check and export (1), patch FORTE (2), build with the 4diac FORTE Build Environment (3),
  package (4); then a PC, a fresh Pi, a running Pi, or someone else's PC with the kit.</figcaption>
</figure>

A FORTE runs only programs whose block types it was built with. A new or changed block type (a skill,
an equipment item, a library block) means a new FORTE; a changed program (other instances,
connections, values) does not: it is only deployed. One binary holds every module's types and serves
every Pi; each Pi deploys only its own module's program.

## The steps

1. **Check and export** (`validate.ps1`): the 4diac IDE 3.3, headless, checks every type and system and
   exports the types as C++; the library is compiled once.
2. **Patch FORTE 3.3.0** (`forte-patches/`, a stack of patches; header shims in `forte-compat/`): the IO
   handles fixed, a sysfs PWM module, stand-ins for GPIOChip and PWMChip where FORTE has no GPIO
   (Windows).
3. **Build** with the 4diac FORTE Build Environment (FBE, `C:\4diac-fbe`): `modules-win` gives
   `forte.exe`, `pi/modules-pi` the aarch64 binary; open62541 and the rest linked statically; the FBE
   brings the cross compiler.
4. **Package** (`build-pi.ps1`): `runtime/bin/forte-aarch64` with its checksum, committed, so the
   installer finds it.

```powershell
runtime/build-modules.ps1                 # modgen's projects checked and exported, FORTE for Windows
runtime/build-pi.ps1                      # FORTE for the Pi, packaged into runtime/bin
runtime/build-pi.ps1 -SkipValidate        # reuse the last export: only compile and package
runtime/check-project.ps1 -ProjectDir cell/control/FillingModule   # only the IDE's checks
```

Needed once: the 4diac IDE 3.3 (its version must match FORTE's; elsewhere set `FORDIAC_IDE`), the FBE
cloned into `C:\4diac-fbe`, Python with the repository installed, and git.

## Where it runs

| Where | How |
| --- | --- |
| This PC | `forte.exe` with the IO simulated over Modbus: [run a module on a PC](../how-to/simulation.md), the live tests, the evaluation |
| A fresh Raspberry Pi | `runtime/install.sh`: Docker, FORTE in a container with the GPIO chip and the PWM channels, `fake-hwclock`; run again to update, the program is kept ([on a Pi](../how-to/raspberry-pi.md)) |
| A Pi that runs FORTE | `runtime/update-pi.ps1 -Pi user@address`: build, send the binary, rebuild the container, wait until FORTE answers |
| Someone else's PC | `runtime/make-kit.ps1` makes `forte-kit.zip`: `build-project.ps1 -Project <their folder>` builds FORTE with their own block types, `install-pi.ps1 -Pi user@address` installs it over SSH, even on a Pi without internet |

Read further: [forte-for-the-pi.md](https://github.com/AAUSmartProductionLab/iec61499-mgmt-py/blob/main/docs/forte-for-the-pi.md).
