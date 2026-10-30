# FORTE kit: your own block types on a Raspberry Pi

This kit builds 4diac FORTE 3.3.0 for a Raspberry Pi 4 or 5 (64-bit Linux) with the block types
of your 4diac project compiled in. You need it when you have made new block types (basic,
simple, composite or service FBs, data types). A FORTE can only create blocks whose types were
compiled into it; a changed application or new connections need no new FORTE.

The FORTE it builds is the one the lab's Pis run (same patches, same settings: OPC UA, GPIO,
PWM), with the lab's module types already in it (`.cache/modules`). So it also runs the lab's
module programs, and you can install it on a lab Pi.

## What you need, once

- **Windows** with PowerShell and **git**.
- **The 4diac IDE 3.3** (4diac-ide_3.3.x). It must be 3.3: the IDE writes the C++ for your types,
  and it has to match FORTE 3.3.0.
- **The 4diac FORTE Build Environment (FBE)** in `C:\4diac-fbe`:

  ```powershell
  git clone https://github.com/eclipse-4diac/4diac-fbe C:\4diac-fbe
  ```

  The first build downloads its compilers, including the cross compiler for the Pi.
  That takes a while, once.

Unzip the kit to a folder whose path has no spaces, for example `C:\forte-kit`. Windows blocks
scripts that came from a zip; unblock them once:

```powershell
cd C:\forte-kit
Get-ChildItem -Recurse | Unblock-File
```

If PowerShell still refuses to run scripts, start the commands below with
`powershell -ExecutionPolicy Bypass -File` instead of `.\`.

## Build

Tell the kit where the IDE is, then build with your project folder (the folder that holds
`<Project>.sys` and `Type Library`):

```powershell
$env:FORDIAC_IDE = 'C:\path\to\4diac-ide\4diac-idec.exe'
.\build-project.ps1 -Project C:\path\to\MyProject
```

Close your project in the IDE first, or at least save everything: the kit reads the files on disk.

This takes four steps:

1. It fetches the FORTE 3.3.0 source into `fbe\4diac-forte` and applies the patches in
   `forte-patches`.
2. The IDE runs without a window. It loads your project, checks every type and the system, and
   exports the types as C++ to `.cache\modules\<project>`. The log is
   `.cache\validate-<Project>.log`. A type that is a copy of a FORTE standard block (E_CTU, E_SR, ...)
   is left out, since FORTE has it already.
3. The FBE cross-compiles FORTE with your types and the lab's.
4. The result is stripped into `bin\forte-aarch64`, with its checksum in `bin\forte-aarch64.sha256`.

The first build takes long (the compilers, then open62541 and the other libraries). Later builds
take a minute or two. Several projects: `-Project C:\a\One, C:\b\Two`.

Options:

- `-Alone`: only your types, without the lab's modules. That FORTE cannot run the lab's module
  programs.
- `-Config modules-win`: a FORTE for this PC instead, to test with. It is
  `fbe\build\modules-win\output\bin\forte.exe`. Start it and deploy to `localhost:61499`. GPIO and
  PWM blocks then only answer `QO = FALSE`.
- `-Ide <path>`: the IDE, instead of `FORDIAC_IDE`.

To run only the IDE's checks on a project (nothing is built):
`.\check-project.ps1 -ProjectDir C:\path\to\MyProject`.

## Put it on the Pi

From this PC, over the local network, with the Pi's login and address (SSH enabled on the Pi):

```powershell
.\install-pi.ps1 -Pi pi@192.168.0.42
```

It copies the installer, `bin\forte-aarch64` with its checksum, the container files (`pi\`) and the
base images (`images\`) to `~/forte-kit` on the Pi with `scp`, and runs the installer there over
`ssh`. Both come with Windows (the "OpenSSH Client" feature). They ask for the Pi's password,
and the installer asks for the sudo password.

Nothing is downloaded when the Pi already has Docker, as the lab's Pis do. On a fresh Pi,
the installer still has to download Docker itself, so that Pi needs internet once. It also tries
fake-hwclock, which keeps the clock across restarts; without internet it says so and goes on.

The installer checks the checksum and runs FORTE in a Docker container that starts with the Pi.
It also gives FORTE the GPIO lines and enables the two PWM channels; reboot once after the first
install. FORTE then listens on port 61499. Deploy your application from the IDE as usual.

Running the installer again replaces FORTE and keeps the program that is on the Pi
(`~/forte/boot/forte.fboot`). On a lab module's Pi, ask first: the module's program starts again
when FORTE restarts, and it may move an axis.

## When it goes wrong

- **"4diac IDE not found"**: set `FORDIAC_IDE` to `4diac-idec.exe` (with a `c`, the console version).
- **"4diac validation failed"** or **"IDE loading/export errors"**: a type does not load, or ST has an
  error. The IDE treats warnings as errors. Read `.cache\validate-<Project>.log`, or run
  `check-project.ps1` for a list. Every type must be in your project's `Type Library`.
- **"has no <Project>.sys"**: `-Project` must be the project folder itself.
- **The FBE build fails**: the log is `fbe\build\modules-pi\forte.log`. A changed setting has no
  effect until `fbe\build\modules-pi\forte\build\CMakeCache.txt` is deleted.
- **"fbe/4diac-forte is at ..."** or **a patch does not apply**: delete `fbe\4diac-forte` and build again.
- **The Pi refuses to create your block** (unknown type, or a hash mismatch): the Pi's FORTE was
  built from another version of the type. Build and install again after every change to a type.
