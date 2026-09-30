// Compatibility shim: the 4diac IDE 3.2 exporter references the process-interface variant
// (stdfblib/io, forte::eclipse4diac::io::FORTE_QW), but FORTE builds with modular IO
// (FORTE_IO + e.g. GPIOCHIP) provide the same registered type "eclipse4diac::io::QW" as
// forte::io::FORTE_QW in forte/io/QW_fbt.h. Copied into the export by validate.ps1.
#pragma once

#include "forte/io/QW_fbt.h"

namespace forte::eclipse4diac::io {
  using FORTE_QW = forte::io::FORTE_QW;
}
