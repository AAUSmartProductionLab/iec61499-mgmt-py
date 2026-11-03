# FORTE kit: your 4diac project on a Raspberry Pi

This kit puts your 4diac project on a Raspberry Pi 4 or 5 with one command. It builds the
Pi's runtime, FORTE, with your block types inside, and sends it to the Pi together with your
program. After that you work in the 4diac IDE as usual: deploy, watch and force values.

## 1. Set up your PC (once)

You need:

- **Windows 10 or 11.**
- **git**: <https://git-scm.com/download/win>.
- **The 4diac IDE 3.3.** It must be 3.3: other versions do not match this FORTE.
- **The FORTE build environment** in `C:\4diac-fbe`. Open PowerShell and run:

  ```powershell
  git clone https://github.com/eclipse-4diac/4diac-fbe C:\4diac-fbe
  ```

Then:

1. **Unzip the kit** to `C:\forte-kit`. Use a folder whose path has no spaces.
2. **Allow the kit's scripts.** In PowerShell:

   ```powershell
   cd C:\forte-kit
   Get-ChildItem -Recurse | Unblock-File
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```

   Answer `Y` if PowerShell asks.
3. **Tell the kit where the IDE is.** Use the path of `4diac-idec.exe`: the one with a **c**,
   in your IDE folder.

   ```powershell
   [Environment]::SetEnvironmentVariable('FORDIAC_IDE', 'C:\path\to\4diac-ide\4diac-idec.exe', 'User')
   ```

   Then close PowerShell and open a new one. The setting is kept from now on.

## 2. Put your project on the Pi

**In the IDE:**

1. In your System, the device for your Pi (e.g. `FORTE_PI`) must have the Pi's address in
   `MGR_ID`, e.g. `"192.168.0.42:61499"`.
2. Your application must be mapped to that device's resource (right-click the blocks or the
   application, **Map to**).
3. Save everything (**Ctrl+Shift+S**).

**In PowerShell:**

```powershell
cd C:\forte-kit
.\deploy-pi.ps1 -Pi admin@192.168.0.42 -Project C:\path\to\MyProject
```

- `admin@192.168.0.42` is the Pi's login and address.
- `C:\path\to\MyProject` is your project folder: the one with `MyProject.sys` and `Type Library`
  in it. In the IDE: right-click the project, **Properties**, **Location**.

The script asks once whether FORTE may restart: type `y`. Then type the Pi's password when it
asks, twice. The first time takes long, half an hour or more, because the kit downloads and
builds what FORTE needs. After that it takes two or three minutes.

**It worked** when the last line says:

```
FORTE runs the new build with the program from MyProject-program.fboot on admin@192.168.0.42 and answers on 192.168.0.42:61499.
```

FORTE now runs your program, and starts it again whenever the Pi starts.

> On a lab module's Pi, ask first: when FORTE restarts, the module's program starts again, and it
> may move an axis.

## 3. Working on your project

| You changed ... | Then |
|---|---|
| the application: blocks placed, connections, parameters | **Deploy** in the IDE: right-click your Pi's device, **Deploy** |
| a block type: a new type, its pins, its algorithm | `.\deploy-pi.ps1 ...` as in step 2: FORTE must be built with the new type |
| nothing, you want to watch or force values | **Monitor** in the IDE, as usual |

**Good to know:** after a reboot, the Pi runs the program that `deploy-pi.ps1` put there, not the
last one deployed from the IDE. To make your current program the one the Pi starts with:

```powershell
.\deploy-pi.ps1 -Pi admin@192.168.0.42 -Project C:\path\to\MyProject -SkipBuild
```

`-SkipBuild` skips building FORTE (use it only when no block type changed). It takes about 15 s.

## 4. A Pi that has never run FORTE

Do this once, before step 2. The Pi needs SSH turned on, and internet the first time if it has no
Docker yet.

```powershell
cd C:\forte-kit
.\build-project.ps1 -Project C:\path\to\MyProject
.\install-pi.ps1 -Pi admin@192.168.0.42
```

`install-pi.ps1` asks for the Pi's password and then for its sudo password (often the same).
Restart the Pi once when it is done. Then put your project on it with `deploy-pi.ps1 ... -SkipBuild`
(step 2).

## 5. Start from the lab's module projects

`projects\` has the lab's current module projects: `FillingModule` and `StopperingModule`.

1. In the IDE: **File > Import > General > Existing Projects into Workspace**, choose
   `C:\forte-kit\projects\FillingModule`, and tick **Copy projects into workspace**.
2. Set `MGR_ID` of the device `FORTE_PI` to your Pi's address.
3. Put it on the Pi as in step 2, with the project in your workspace as `-Project`.

An older project of your own works as well. If it has its own older copies of the lab's blocks
(`SKILL_Core`, `IO_DI`, ...), the build stops and names them; then add `-Alone` to the command.

## 6. When something goes wrong

The scripts say what went wrong. Find the message here:

| The message says ... | What to do |
|---|---|
| `running scripts is disabled` | Step 1.2 again |
| `4diac IDE not found` | Step 1.3 again; the file is `4diac-idec.exe`, with a **c** |
| `has no MyProject.sys` | `-Project` must be the project folder itself (step 2) |
| `no device has MGR_ID ...` | Set your Pi's address in the device's `MGR_ID` (step 2), and save |
| `Nothing of ... is mapped to that device` | Map your application to the device's resource, and save |
| `4diac validation failed` | A type has an error; the IDE counts warnings as errors too. Run `.\check-project.ps1 -ProjectDir C:\path\to\MyProject` for the list, fix them in the IDE, save, try again |
| `... differs from the one in modlib` | Your project has an older copy of a lab block: add `-Alone` |
| `uses a block type FORTE lacks` | Run `deploy-pi.ps1` without `-SkipBuild` |
| `No folder ~/forte on the Pi` | The Pi has no FORTE yet: step 4 |
| `scp ... failed` or `ssh ... failed` | Check the Pi's address and login, that it is on the network, and that SSH is on |
| `Removed START from ...` | Not an error: the kit fixed your project. Close the project in the IDE without saving, and open it again |
| `Waiting until port 61499 is free` | Not an error: the IDE was connected. The script waits up to a minute |
| `typed subapplication` | Make the program in the IDE (right-click the device, **Create FORTE Boot-Files**), then `.\update-pi.ps1 -Pi admin@192.168.0.42 -Project C:\path\to\MyProject -Program C:\path\to\FORTE_PI.fboot` |

In the IDE:

| The IDE says ... | What to do |
|---|---|
| `Could not connect to device FORTE_PC` (or another device) | Another device in your System has no FORTE running. Deploy only your Pi: right-click its device, **Deploy** |
| `UNSUPPORTED_TYPE` for one of your own blocks | FORTE on the Pi was built without that version of the type: run `deploy-pi.ps1` (step 2) |

Still stuck? Send your teacher the whole PowerShell output.

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

**Where to look:**

- The IDE's check: `.cache\validate-MyProject.log`.
- The FORTE build: `fbe\build\modules-pi\forte.log`. After changing a build setting, delete
  `fbe\build\modules-pi\forte\build\CMakeCache.txt`.
- If a patch does not apply, or the message names `fbe/4diac-forte`: delete the folder
  `fbe\4diac-forte` and run again.
- FORTE's log on the Pi: `ssh admin@192.168.0.42 "cd ~/forte && docker compose logs --tail 50 forte"`.
