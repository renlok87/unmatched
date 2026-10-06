#include "S08HudDebug.h"

#include "../S08ArtLook.h"

namespace S08HudDebug {
namespace {
// The commands whose toast is a bare echo "<command> sent" or "<command> sent (<detail>)" (S08FlowGameMode.cpp: the
// begin-maneuver, end-turn, resolve, scheme, attack, defense, pending-choice and lobby-return paths).
const TCHAR* const EchoCommands[] = {TEXT("begin maneuver"), TEXT("end turn"), TEXT("resolve"),
                                     TEXT("scheme"),         TEXT("attack"),   TEXT("defense"),
                                     TEXT("choice"),         TEXT("lobby return already")};
// The S09 auto driver ("AUTO maneuver: <fighter id> -> <space> (through the draft)", HD-01 of 01-inventory).
const TCHAR* const AutoPrefix = TEXT("AUTO ");
}  // namespace

bool IsDebugToast(const FString& Toast) {
  if (Toast.StartsWith(AutoPrefix, ESearchCase::CaseSensitive)) return true;
  for (const TCHAR* Command : EchoCommands) {
    const FString Echo = FString(Command) + TEXT(" sent");
    if (Toast.Equals(Echo, ESearchCase::CaseSensitive) || Toast.StartsWith(Echo + TEXT(" ("), ESearchCase::CaseSensitive)) {
      return true;
    }
  }
  return false;
}

FString PlayerToast(const FString& Toast, bool bMarkers) {
  return !bMarkers && IsDebugToast(Toast) ? FString() : Toast;
}

FString PlayerToast(const FString& Toast) { return PlayerToast(Toast, S08ArtLook::S08Markers()); }

EVisibility Visibility() { return S08ArtLook::S08Markers() ? EVisibility::Visible : EVisibility::Collapsed; }

}  // namespace S08HudDebug
