// Compatibility shim: the 4diac IDE exporter includes PWMChip from here (a block that contains one,
// e.g. modlib::IO_AO). FORTE declares it in the pwmsysfs module (forte-patches/0002, Linux), or the
// stand-in of forte-patches/0003-io-stand-ins.patch elsewhere: the same class either way.
// Copied into the export by validate.ps1.
#pragma once

#include "pwmsysfs_config_fb.h"
