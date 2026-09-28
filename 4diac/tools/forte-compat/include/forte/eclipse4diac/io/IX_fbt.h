// Compatibility shim: the 4diac IDE 3.2 exporter references the process-interface variant
// (stdfblib/io, forte::eclipse4diac::io::FORTE_IX), but FORTE builds with modular IO
// (FORTE_IO + e.g. GPIOCHIP) provide the same registered type "eclipse4diac::io::IX" as
// forte::io::FORTE_IX in forte/io/IX_fbt.h. Copied into the export by validate.ps1.
#pragma once

#include "forte/io/IX_fbt.h"

namespace forte::eclipse4diac::io {
  using FORTE_IX = forte::io::FORTE_IX;
}
