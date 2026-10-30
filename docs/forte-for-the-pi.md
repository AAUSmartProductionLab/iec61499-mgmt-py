# Building FORTE for the Raspberry Pi

A Pi runs 4diac FORTE, cross-compiled on the Windows PC for aarch64 (64-bit Linux, Pi 4 and 5).
A FORTE can only run programs whose block types were compiled into it, so it is rebuilt whenever
a block type changes: a new or changed skill, equipment or library block. A changed program
(a new `.sys`, other connections, other parameters) needs no new FORTE; it is only deployed.

The build uses the 4diac FORTE Build Environment (FBE), not a plain FORTE checkout with CMake: the
FBE brings the compilers (also the aarch64 cross compiler) and builds open62541 and the other
libraries, linked statically into one binary. One binary holds every module's types and serves
every Pi; each Pi deploys only its own module's program.

## In one command

```powershell
runtime/build-pi.ps1                 # modgen, IDE export, cross-compile, package
runtime/build-pi.ps1 -SkipValidate   # reuse the last export (no modgen, no IDE): only compile and package
```

It ends by saying whether `runtime/bin/forte-aarch64` changed. If it did: commit it together with
`runtime/bin/forte-aarch64.sha256`, then install it on the Pi (step 6). `-NoPackage` leaves
`runtime/bin` alone; the new FORTE is then only at `runtime/fbe/build/modules-pi/output/bin/forte`.

## Someone else's block types: the kit

To let someone build FORTE with block types from their own 4diac project, without this
repository:

```powershell
runtime/build-pi.ps1 -SkipValidate   # first, so the lab's exports in runtime/.cache/modules are current
runtime/make-kit.ps1                 # runtime/dist/forte-kit.zip (-NoLabModules: without the lab's modules)
```

Send them `forte-kit.zip`; its README ([runtime/kit/README.md](../runtime/kit/README.md)) is their
guide. They run `build-project.ps1 -Project <their project folder>`. It exports their project next
to the lab's modules, cross-compiles, and packages `bin/forte-aarch64`. `install-pi.ps1 -Pi
user@address` copies it with `install.sh`, the container files and the arm64 base images (in the
kit; Docker needed on the PC that makes it, or `-NoImages`) to the Pi over SSH and installs it
there. The Pi needs no internet unless Docker is missing. For a Pi that already runs FORTE,
`update-pi.ps1 -Pi user@address -Project <folder>` builds, sends the binary, rebuilds the container
and waits until FORTE is up (the old binary stays as `~/forte/forte.old`). That FORTE still runs the lab's module
programs. The same script works here:
`runtime/build-project.ps1 -Project <folder>` adds a project to this repository's build (its
export stays in `runtime/.cache/modules` until the next `build-modules.ps1`).

## What is needed once

1. **The 4diac IDE 3.3** for the headless export. Its path is the default of `-Ide` in
   `runtime/validate.ps1`; change it there if yours is elsewhere. The IDE's version must match the
   FORTE release (3.3.0, `-ForteTag` in `runtime/build-runtime.ps1`).
2. **The FBE** in `C:\4diac-fbe`: `git clone https://github.com/eclipse-4diac/4diac-fbe C:\4diac-fbe`.
   The first build runs its `toolchains\etc\install.cmd`, which downloads the toolchains; the first
   Pi build also downloads the aarch64 cross compiler (`aarch64-linux-musl`). Both take a while,
   once.
3. **Python** with the repository installed (`python -m pip install -e ".[test]"`), for `modgen`.
4. **git**, which fetches the FORTE source (step 3).

## Step by step

What `runtime/build-pi.ps1` does, and how to run each step alone.

1. **Generate the projects** from the module specs (`cell/modules/*.yaml`) and the library:

   ```powershell
   python -m modgen
   ```

   This writes `iec61499-skill-lib/ModLib` and `cell/control/<Module>`, each with a
   `types-manifest.json` listing its types.

2. **Export the types as C++ into the FBE's module folder.** For ModLib and every module, the 4diac
   IDE runs headless (`runtime/validate.ps1`): it loads every type and the system, and exports the
   C++ to `runtime/.cache/modules/<package>` (`modlib`, `filling`, `stoppering`, `filler`). The
   script then tidies the export for FORTE: it removes the generic communication blocks (FORTE has
   them as `GEN_SERVER` etc.), copies the IO header shims (`runtime/forte-compat`) and links each
   module to the library and the IO modules. The FBE configuration points at this folder
   (`FBE_EXTERNAL_MODULES_DIR` in `runtime/fbe/configurations/pi/modules-pi.txt`), so every folder
   in it is compiled in.

   Exporting by hand in the IDE (*File > Export > 4diac FORTE*) gives the same C++, but without
   the tidying the build fails; use the script.

3. **Get the FORTE source and patch it.** `runtime/build-runtime.ps1` clones FORTE 3.3.0 into
   `runtime/fbe/4diac-forte` (the FBE builds that checkout instead of its own) and applies
   `runtime/forte-patches/*.patch` in order: the IO handle fix, the sysfs PWM module and the IO
   stand-ins for Windows. Patches already applied are skipped.

4. **Cross-compile with the FBE**, from `runtime/fbe`:

   ```powershell
   runtime/build-modules.ps1 -Config pi/modules-pi -SkipValidate   # steps 3 and 4 on the last export
   ```

   This calls the FBE's `scripts/compile.sh` with the configuration `pi/modules-pi`. The configuration
   sets `ARCH=aarch64-linux-musl`, OPC UA single-threaded, GPIO through `/dev/gpiochip`, the PWM
   module, larger event queues, mDNS announcement, and an 8 MiB thread stack (musl's default
   is too small for open62541). The result, with debug symbols, is
   `runtime/fbe/build/modules-pi/output/bin/forte`; the log is `runtime/fbe/build/modules-pi/forte.log`.

5. **Package it into the repository:**

   ```powershell
   runtime/package-runtime.ps1
   ```

   It strips the binary with the cross toolchain's `strip` (73 MB to 14 MB) into
   `runtime/bin/forte-aarch64` and writes its SHA-256 next to it. The Pi's installer takes it from
   there. Commit both files.

6. **Install it on a Pi**, with someone at the module: the program starts again and may move the
   axis.

   ```powershell
   python deploy/pi.py install                                     # the Filling Pi (cell/modules/filling.yaml)
   python deploy/pi.py install --spec cell/modules/stoppering.yaml # the Stoppering Pi
   python deploy/pi.py module                                      # deploy the module's program again
   python deploy/pi.py status
   ```

   `install` copies FORTE and its container definition (`deploy/pi/`) to `~/forte` on the Pi and
   restarts the container; the program in `~/forte/boot/forte.fboot` is kept. It sends the build
   folder's FORTE (with symbols); `--forte runtime/bin/forte-aarch64` sends the packaged one. On a fresh Pi,
   `runtime/install.sh` (see the README) does the same from the committed binary.

## When it goes wrong

- **A setting in `modules-pi.txt` seems to have no effect.** The FBE hands its settings to CMake only
  on a fresh cache. `build-runtime.ps1` deletes the cache when the configuration file is newer;
  otherwise delete `runtime/fbe/build/modules-pi/forte/build/CMakeCache.txt` yourself.
- **"Expected N exported types, got M"** or IDE loading errors: a type does not load in the IDE.
  The log is `runtime/.cache/validate-<Project>.log`. `runtime/check-project.ps1 -ProjectDir <folder>`
  runs only the IDE's checks.
- **"fbe/4diac-forte is at ..., expected 3.3.0"**: delete `runtime/fbe/4diac-forte`; the next build
  fetches and patches it again.
- **A patch does not apply**: the checkout has local changes. Delete `runtime/fbe/4diac-forte` as above.
- **A changed open62541 recipe** (`runtime/fbe/dependencies/recipes/open62541@1.5`) is used only on a
  fresh recipe folder: delete `runtime/fbe/build/modules-pi/etc/cget/recipes/open62541*` and
  `runtime/fbe/build/modules-pi/cget/pkg/open62541`.
- **FORTE on the Pi refuses to create a block** ("unknown type" or a hash mismatch): the Pi runs an
  older FORTE than the program's types. Build, commit, and install again.
