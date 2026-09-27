// Compatibility shim: the 4diac IDE 3.2 exporter references the process-interface variant
// (stdfblib/io, forte::eclipse4diac::io::FORTE_QX), but FORTE builds with modular IO
// (FORTE_IO + e.g. GPIOCHIP) provide the same registered type "eclipse4diac::io::QX" as
// forte::io::FORTE_QX in forte/io/QX_fbt.h. Copied into the export by validate.ps1.
#pragma once

#include "forte/io/QX_fbt.h"

namespace forte::eclipse4diac::io {
  using FORTE_QX = forte::io::FORTE_QX;
}
