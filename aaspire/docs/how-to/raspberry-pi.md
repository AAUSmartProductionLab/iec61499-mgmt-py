# Put a module on a Raspberry Pi

A Raspberry Pi 4 or 5 running a module's IEC 61499 program on its real IO.

!!! danger "Motion"
    A module's Reset and Home drive its axis to the limit switch, and its skills move it. Send them only
    with someone at the machine who can stop it.

## 1. The Pi

- A 64-bit Linux (Raspberry Pi OS or Ubuntu), on the network.
- Login with your PC's SSH key; the user in the groups `docker` and, on Ubuntu, `dialout` (the GPIO
  lines).
- The module's spec names it: the `pi` target in `cell/modules/<module>.yaml` has its `host`, `user`
  and `board` (`pi5` for a Raspberry Pi 5, whose PWM channels are numbered differently).

## 2. FORTE on the Pi

On the Pi, once, as a user with sudo:

```bash
curl -fsSL https://raw.githubusercontent.com/AAUSmartProductionLab/iec61499-mgmt-py/main/runtime/install.sh | bash
```

It installs Docker if it is missing and starts FORTE in a container with the GPIO lines and the PWM
channels; reboot once for the PWM. Or from the PC, on a Pi that has Docker:

```powershell
python deploy/pi.py install --spec cell/modules/stoppering.yaml --forte runtime/bin/forte-aarch64
```

A changed block type needs a new FORTE: `runtime/build-pi.ps1`, commit `runtime/bin`, install again
([FORTE runtime](../reconfiguration/runtime.md)).

## 3. The module's program

```powershell
python deploy/pi.py module --spec cell/modules/stoppering.yaml --print   # look at the boot file first
python deploy/pi.py module --spec cell/modules/stoppering.yaml           # deploy it; FORTE restarts
python deploy/pi.py log --spec cell/modules/stoppering.yaml
```

The program becomes FORTE's boot file and FORTE restarts, so the module comes back after a reboot.
Keep a copy of the boot file before you replace one (`~/forte/boot/forte.fboot`). The module starts
Stopped and free.

## 4. Check it

```powershell
python -m modsync pull --host <the Pi's address>     # which module runs there, its drift from its spec, its AAS
```

With the registration service running with `--discover`, the module is found and registered by
itself ([register](register.md)). From then on it is operated over OPC UA at `opc.tcp://<Pi>:4840` like
the [simulated one](simulation.md).
