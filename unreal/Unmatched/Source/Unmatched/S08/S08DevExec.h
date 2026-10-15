// Interactive dev loop (-DevExec=<dir>, S08DevExec.cpp, tools/dev/DEV-LOOP.md).
#pragma once

#include "CoreMinimal.h"

namespace S08DevExec {
/** True while the -DevExec command server runs. The driver's input is synthetic Slate events to a window that is
 *  usually NOT the OS foreground window, so focus gates (ViewportHasFocus) treat the game as focused. */
UNMATCHED_API bool Active();
}  // namespace S08DevExec
