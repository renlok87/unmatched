// ART-004 opt-in live review: which isolated Medusa candidate the packaged
// -ArtPreview path loads. Only /Game/ArtPreview/Medusa candidates are listed;
// the production /Game/ART004 Medusa and SK_Medusa are never referenced here.
// Without -ArtPreviewMedusaVariant= the v2 candidate stays in use. An unknown
// value yields no mesh: the Cobble art board then stays grey, the ArtPreview
// evidence shot never fires and the run fails loudly instead of silently
// showing v2 under a v3 label.
#pragma once

#include "CoreMinimal.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

struct FS08MedusaCandidate {
  const TCHAR* Variant = TEXT("unknown");
  const TCHAR* MeshPath = nullptr;
  // Raw -ArtPreviewMedusaVariant= value, or "(default)" when the flag is
  // absent. Lets a trace prove the no-flag default path separately from an
  // explicit face-neck-v2 request (ART-004 T1.1 control run).
  FString Requested;
};

inline FS08MedusaCandidate S08SelectMedusaCandidate() {
  FString Requested;
  FParse::Value(FCommandLine::Get(), TEXT("ArtPreviewMedusaVariant="), Requested);
  const FString RequestedLabel = Requested.IsEmpty() ? FString(TEXT("(default)")) : Requested;
  if (Requested.IsEmpty() || Requested == TEXT("face-neck-v2")) {
    return {TEXT("face-neck-v2"),
            TEXT("/Game/ArtPreview/Medusa/Meshes/SK_Medusa_FaceNeck_v2Candidate"),
            RequestedLabel};
  }
  if (Requested == TEXT("head-tilt-v3")) {
    return {TEXT("head-tilt-v3"),
            TEXT("/Game/ArtPreview/Medusa/Meshes/SK_Medusa_HeadTilt_v3Candidate"),
            RequestedLabel};
  }
  FS08MedusaCandidate Unknown;
  Unknown.Requested = RequestedLabel;
  return Unknown;
}

// ART-004 T2.2 opt-in review: -ArtPreviewAllMedusa puts the selected candidate
// on all six live fighters (team MI, hero/sidekick scale) so one packaged frame
// shows six sculpts on the board. Review only; never a hero mapping.
// ART-DEFAULT (2026-10-04, S08ArtLook.h): review tooling - it needs -ArtPreview now that the art board itself is the
// default, and the default v2 figures yield to it (S08HeroesV2::FlagEnabled).
inline bool S08ArtPreviewAllMedusa() {
  return FParse::Param(FCommandLine::Get(), TEXT("ArtPreview")) &&
         FParse::Param(FCommandLine::Get(), TEXT("ArtPreviewAllMedusa"));
}
