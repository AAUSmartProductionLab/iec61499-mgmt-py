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
   `.cache\validate-<Project>.log`. A type that is a copy of a FORTE standard block (E_CTU, E_SR,
   GPIOChip, ...) or of one the kit has (ModLib's) is left out, since FORTE has it already. A
   project that is a copy of a lab module (the same package, e.g. `filling` in `FillingModule`)
   replaces the kit's export of that module.
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
install. FORTE then listens on port 61499. Put your project on it with `deploy-pi.ps1`, below.

Running the installer again replaces FORTE and keeps the program that is on the Pi
(`~/forte/boot/forte.fboot`). On a lab module's Pi, ask first: the module's program starts again
when FORTE restarts, and it may move an axis.

## Put your project on the Pi

One command takes your project as it is on disk and puts it on the Pi, from fresh:

```powershell
.\deploy-pi.ps1 -Pi pi@192.168.0.42 -Project C:\path\to\MyProject
```

1. It makes the program from the project's `.sys`: what is mapped to the device whose `MGR_ID` is
   the Pi's address (e.g. `FORTE_PI` with `"192.168.0.42:61499"`), with its parameters and
   connections, as a boot file (`.cache\<Project>-program.fboot`). `-Device <name>` picks the
   device by name instead.
2. It builds FORTE with the project's block types, as `build-project.ps1` does.
3. On the Pi it stops and deletes the FORTE container, puts the new FORTE and the program in
   place, builds the image and runs a new container. FORTE starts with your program, and again
   after every reboot.

Save the project in the IDE first. When no block type changed, `-SkipBuild` sends the last build
and the new program in about 15 s. Watching and forcing values in the IDE work as usual.

**Deploy** in the IDE works as well, once FORTE is on the Pi: after a change to the application,
deploy as usual. Only the program `deploy-pi.ps1` put there starts again after a reboot; one
deployed from the IDE is gone then (FORTE starts with the boot file). Run `deploy-pi.ps1
-SkipBuild` to make your current program the one the Pi starts with. A new or changed block type
always needs `deploy-pi.ps1` (or `update-pi.ps1 -Project`): FORTE can only create the types it was
built with.

The program can also come from the IDE: right-click the device in the System Explorer, **Create
FORTE Boot-Files**, then `.\update-pi.ps1 -Pi pi@192.168.0.42 -Program C:\path\to\FORTE_PI.fboot`
(with `-Project` too when block types changed). `deploy-pi.ps1` cannot make the program of a
typed subapplication; it says so, and then this is the way. `.\make-bootfile.ps1 -Project <folder>
-Device <name>` makes only the program, to look at.

The scripts ask once before FORTE restarts (`-Force`: they do not ask). They keep what they replace
(`~/forte/forte.old`, `~/forte/boot/forte.fboot.old`), and it checks that FORTE comes up, that the
program loads and that FORTE answers on port 61499 from this PC:

- **"uses a block type FORTE lacks"** (`Boot file error ... UNSUPPORTED_TYPE` in the log): the
  program has a block whose type is not in FORTE, or changed since FORTE was built. Nothing of the
  program runs. Run again without `-SkipBuild`.
- **"no device has MGR_ID ..."**: no device in the project has the Pi's address. Set the device's
  `MGR_ID` in the IDE, or give `-Device`.
- **"joins ... to a block elsewhere"**: a connection goes to a block mapped to another device; it is
  left out of this program.
- **"Waiting until port 61499 is free"**: the IDE was connected (watching values) when FORTE
  stopped, and Linux holds the port for up to a minute. The script waits.

### FORTE alone

`-Project` without `-Program` builds and sends only FORTE; `-SkipBuild` sends the last build
without building again. FORTE then starts with the program kept on the Pi
(`~/forte/boot/forte.fboot`), which the last `-Program` or `modsync push` put there. If that program
uses a block type your build lacks, the script says so. `-NoProgram` starts FORTE without a
program (the old one is kept as `boot/forte.fboot.old`).

The same by hand. The image copies `forte` in when it is built, so `docker compose restart` alone
would keep the old binary:

```powershell
scp bin\forte-aarch64 pi@192.168.0.42:forte/forte
ssh pi@192.168.0.42 "cd ~/forte && docker compose up -d --build --force-recreate forte && docker compose ps"
ssh pi@192.168.0.42 "cd ~/forte && docker compose logs --tail 20 forte"
```

The log should say `FORTE is up and running`. The program on the Pi is kept and starts again.

## When it goes wrong

- **"4diac IDE not found"**: set `FORDIAC_IDE` to `4diac-idec.exe` (with a `c`, the console version).
- **"4diac validation failed"** or **"IDE loading/export errors"**: a type does not load, or ST has an
  error. The IDE treats warnings as errors. Read `.cache\validate-<Project>.log`, or run
  `check-project.ps1` for a list. Every type must be in your project's `Type Library`.
- **"has no <Project>.sys"**: `-Project` must be the project folder itself.
- **"... differs from the one in modlib (the kit's)"**: your project has its own version of a type
  the kit has as well, changed. Give your version its own name or package, or build with `-Alone`.
- **The FBE build fails**: the log is `fbe\build\modules-pi\forte.log`. A changed setting has no
  effect until `fbe\build\modules-pi\forte\build\CMakeCache.txt` is deleted.
- **"fbe/4diac-forte is at ..."** or **a patch does not apply**: delete `fbe\4diac-forte` and build again.
- **The Pi refuses to create your block** (unknown type, or a hash mismatch): the Pi's FORTE was
  built from another version of the type. Build and install again after every change to a type.
