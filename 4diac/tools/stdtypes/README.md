Interface declarations of the standard 4diac types used by the filling-cell project, copied
unchanged from the 4diac IDE 3.3 type libraries (`core`, `events`, `io`, `net` 3.0.0;
EPL-2.0, see the headers). The generator copies them to `Type Library/Std` because the
headless IDE check does not resolve library dependencies. FORTE implements these types
itself, so they are excluded from the C++ export (`types-manifest.json`, `exported: false`).
