Interface declarations of the standard 4diac types used by the generated projects (ModLib and the
module projects), copied unchanged from the 4diac IDE 3.3 type libraries (`core`, `events`, `io`,
`net`, `system` 3.0.0; EPL-2.0, see the headers), and `io/PWMChip.fbt`, the declaration of the
sysfs PWM block that our FORTE patch adds (`runtime/forte-patches/0002-pwmsysfs-module.patch`).
The generator copies them to `Type Library/Std` because the headless IDE check does not resolve
library dependencies; the `net/PUBLISH_*` here are not copied, since it writes its own. FORTE
implements these types itself, so they are excluded from the C++ export (`types-manifest.json`,
`exported: false`).
