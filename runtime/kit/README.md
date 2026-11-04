# FORTE kit: your 4diac project on a Raspberry Pi

This kit puts your 4diac project on a Raspberry Pi 4 or 5 with one command. It builds the
Pi's runtime, FORTE, with your block types inside, and sends it to the Pi together with your
program. After that you work in the 4diac IDE as usual: deploy, watch and force values.

**What you do:**

1. Set up your PC: once.
2. Set up the Pi: once, and only for a Pi that has never run FORTE.
3. Put your project on the Pi: one command.
4. Work in the 4diac IDE as usual.

**Before you start, three things to know:**

- **Commands go into PowerShell.** To open it: Start menu, type `PowerShell`, press Enter. Copy a
  command from here, right-click in PowerShell to paste it, press Enter.
- **Change the examples in the commands to yours:**
  - `admin@192.168.0.42`: your Pi's login and address.
  - `C:\path\to\MyProject`: your project folder, the one with `MyProject.sys` in it. To find it
    in the IDE: right-click the project, **Properties**, **Resource**, **Location**.
- **Passwords don't show while you type them.** That is normal: type it and press Enter.

## 1. Set up your PC (once)

1. **Install git** from <https://git-scm.com/download/win>, with the default settings.
2. **Install the 4diac IDE 3.3** from <https://eclipse.dev/4diac/download/>: under **Latest
   Release**, the **4diac IDE** for **Windows 64-bit**. Unzip it to a folder of your choice. It must
   be 3.3, not the 3.4 Early Access: another version does not match this FORTE.
3. **Get the FORTE build environment.** In PowerShell:

   ```powershell
   git clone https://github.com/eclipse-4diac/4diac-fbe C:\4diac-fbe
   ```

4. **Unzip the kit to `C:\`**: right-click `forte-kit.zip`, **Extract All...**, type `C:\` as the
   folder, **Extract**. You now have the folder `C:\forte-kit`. Leave it there: in a deeper folder
   (Downloads, OneDrive) the build's file paths get too long for Windows.
5. **Allow the kit's scripts.** In PowerShell:

   ```powershell
   cd C:\forte-kit
   Get-ChildItem -Recurse | Unblock-File
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```

   Answer `Y` if PowerShell asks.
6. **Tell the kit where the IDE is.** Put in the path of `4diac-idec.exe` (with a **c** at the end)
   from the IDE folder of step 2:

   ```powershell
   [Environment]::SetEnvironmentVariable('FORDIAC_IDE', 'C:\path\to\4diac-ide\4diac-idec.exe', 'User')
   ```

   Then close PowerShell and open a new one. The setting stays from now on.

## 2. Set up the Pi (once, only for a new Pi)

Skip this if the Pi runs FORTE already, e.g. a lab module's Pi. Not sure? Run this:

```powershell
ssh admin@192.168.0.42 ls forte
```

If it says `No such file or directory`, do this step. If it lists files, skip to step 3.

The Pi needs Raspberry Pi OS (64-bit), SSH turned on, and the network. The first time it also
needs the internet, to install Docker.

```powershell
cd C:\forte-kit
.\install-pi.ps1 -Pi admin@192.168.0.42
```

It asks for the Pi's password, and then for its sudo password, which is often the same. When it is
done, restart the Pi:

```powershell
ssh admin@192.168.0.42 sudo reboot
```

Wait a minute until the Pi is back, then go on to step 3.

## 3. Put your project on the Pi

**First, in the IDE:**

1. Open your System. The device for your Pi (e.g. `FORTE_PI`) must have the Pi's address in
   `MGR_ID`, e.g. `"192.168.0.42:61499"`.
2. Map your application to that device's resource: right-click the blocks or the application,
   **Map to**.
3. Save everything: **Ctrl+Shift+S**.

**Then, in PowerShell:**

```powershell
cd C:\forte-kit
.\deploy-pi.ps1 -Pi admin@192.168.0.42 -Project C:\path\to\MyProject
```

1. It asks whether FORTE may restart: type `y` and press Enter.
2. It asks for the Pi's password, twice.
3. Wait. **The first time takes half an hour or more**, because it downloads and builds
   everything FORTE needs. After that it takes two or three minutes.

**It worked** when the last line says:

```
FORTE runs the new build with the program from MyProject-program.fboot on admin@192.168.0.42 and answers on 192.168.0.42:61499.
```

FORTE now runs your program. It also starts the program again whenever the Pi starts.

> **On a lab module's Pi, ask first.** When FORTE restarts, the module's program starts again, and
> it may move an axis.

## 4. Work on your project

| You changed ... | Then |
|---|---|
| the application: blocks placed, connections, parameters | **Deploy** in the IDE: right-click your Pi's device, **Deploy** |
| a block type: a new type, its pins, its algorithm | Run `.\deploy-pi.ps1 ...` as in step 3: FORTE must be built again with the new type |
| nothing; you want to watch or force values | **Monitor** in the IDE, as usual |

**Good to know:** after a restart, the Pi runs the program that `deploy-pi.ps1` put there, not the
last one you deployed from the IDE. To make your current program the one the Pi starts with:

```powershell
.\deploy-pi.ps1 -Pi admin@192.168.0.42 -Project C:\path\to\MyProject -SkipBuild
```

`-SkipBuild` doesn't build FORTE again, so it takes only about 15 seconds. Use it only when no block
type changed.

## 5. Start from the lab's module projects

The folder `C:\forte-kit\projects` has the lab's current module projects: `FillingModule`,
`StopperingModule` and `CappingModule`.

1. In the IDE: **File > Import > General > Existing Projects into Workspace**. Choose
   `C:\forte-kit\projects\FillingModule` and tick **Copy projects into workspace**.
2. Set `MGR_ID` of the device `FORTE_PI` to your Pi's address, and save.
3. Put it on the Pi as in step 3. `-Project` is the copy in your workspace (see its **Location**).

An older project of your own works too. If it has its own older copies of the lab's blocks
(`SKILL_Core`, `IO_DI`, ...), the build stops with `... differs from the one in modlib`. Then add
`-Alone` to the command.

## 6. When something goes wrong

The scripts say what went wrong. Find the message here:

| The message says ... | What to do |
|---|---|
| `running scripts is disabled` | Do step 1.5 again |
| `This folder's path is too long` or `Filename too long` | The kit must be in `C:\forte-kit` (step 1.4). Move it there and run the command from there |
| `4diac IDE not found` | Do step 1.6 again. The file is `4diac-idec.exe`, with a **c** |
| `has no MyProject.sys` | `-Project` must be the project folder itself: the one with `MyProject.sys` in it |
| `no device has MGR_ID ...` | Put your Pi's address in the device's `MGR_ID` (step 3), and save |
| `Nothing of ... is mapped to that device` | Map your application to the device's resource (step 3), and save |
| `4diac validation failed` | One of your types has an error. The IDE counts warnings as errors too. For the list, run `.\check-project.ps1 -ProjectDir C:\path\to\MyProject`. Fix them in the IDE, save, try again |
| `... differs from the one in modlib` | Your project has an older copy of a lab block: add `-Alone` to the command |
| `uses a block type FORTE lacks` | Run `deploy-pi.ps1` without `-SkipBuild` |
| `No folder ~/forte on the Pi` | The Pi has no FORTE yet: do step 2 |
| `scp ... failed` or `ssh ... failed` | Check the Pi's address and login, that the Pi is on the network, and that SSH is on |
| `Removed START from ...` | Not an error: the kit repaired your project. In the IDE, right-click the project, **Close Project**, then **Open Project** |
| `Waiting until port 61499 is free` | Not an error: the IDE was still connected. The script waits up to a minute |
| `typed subapplication` | Make the program in the IDE: right-click the device, **Create FORTE Boot-Files**. Then run `.\update-pi.ps1 -Pi admin@192.168.0.42 -Project C:\path\to\MyProject -Program C:\path\to\FORTE_PI.fboot` |

In the IDE:

| The IDE says ... | What to do |
|---|---|
| `Could not connect to device FORTE_PC` (or another device) | Another device in your System has no FORTE running. Deploy only your Pi: right-click its device, **Deploy** |
| `UNSUPPORTED_TYPE` for one of your own blocks | FORTE on the Pi was built without that version of the type: run `deploy-pi.ps1` (step 3) |

Still stuck? Send your teacher everything PowerShell printed.

## 7. More, for when you need it

**What `deploy-pi.ps1` does:**

1. It reads your project's `.sys` and takes what is mapped to the device whose `MGR_ID` is the Pi's
   address. It writes that as FORTE's program file (`.cache\MyProject-program.fboot`).
2. It builds FORTE with your block types and the lab's (`bin\forte-aarch64`).
3. On the Pi it stops and deletes the FORTE container, puts the new FORTE and the program in
   place, builds a new container and starts it.
4. It checks that FORTE starts, loads the program, and answers on port 61499.

What it replaces on the Pi is kept: `~/forte/forte.old` and `~/forte/boot/forte.fboot.old`.

**Options:**

- `deploy-pi.ps1 -Device FORTE_PI`: take this device, not the one found by its address.
- `deploy-pi.ps1 -Force`: do not ask before restarting FORTE.
- `build-project.ps1 -Project ... -Config modules-win`: a FORTE for your PC instead, to test with:
  `fbe\build\modules-win\output\bin\forte.exe`. Start it and deploy to `localhost:61499`; GPIO and
  PWM blocks then answer `QO = FALSE`.
- `make-bootfile.ps1 -Project ... -Device FORTE_PI`: only make the program file, to look at it.
- `update-pi.ps1 -Pi ... -Project ...`: send only FORTE and keep the program on the Pi;
  `-NoProgram`: start FORTE without a program; `-Program <file>`: a program file made in the IDE.
- `check-project.ps1 -ProjectDir ...`: only the IDE's checks, nothing is built.

`bin\forte-aarch64` comes with the kit as the lab's FORTE, without your types: `install-pi.ps1`
puts it on a new Pi. The first `deploy-pi.ps1` replaces it with a build that has your types.

**Where to look:**

- The IDE's check: `.cache\validate-MyProject.log`.
- The FORTE build: `fbe\build\modules-pi\forte.log`. After changing a build setting, delete
  `fbe\build\modules-pi\forte\build\CMakeCache.txt`.
- If a patch does not apply, or the message names `fbe/4diac-forte`: delete the folder
  `fbe\4diac-forte` and run again.
- FORTE's log on the Pi: `ssh admin@192.168.0.42 "cd ~/forte && docker compose logs --tail 50 forte"`.
