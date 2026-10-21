// Compatibility shim: the 4diac IDE exporter includes GPIOChip from here (a block that contains one,
// e.g. modlib::IO_DI). FORTE declares it in its gpiochip module (gpiochip_config_fb.h, Linux), or
// the stand-in of forte-patches/0003-io-stand-ins.patch elsewhere: the same class either way.
// Copied into the export by validate.ps1.
#pragma once

#include "gpiochip_config_fb.h"
