// GD-028/029: evidence trace file for packaged runs. Only flow events are
// written; tokens/passwords never enter trace lines (GD-028: no sensitive
// logging). Path override: -S08Trace=<absolute path>.
#pragma once

#include "CoreMinimal.h"

class UNMATCHED_API FS08Trace {
public:
  static void Open();
  static void Write(const FString& Line);
  static void Close();

private:
  static FString Path;
  static bool bOpen;
};
