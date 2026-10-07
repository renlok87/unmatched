// FX-03 (VS-6 Z-2): the registry data of S08CueFx.h - mirrored from cue-table.json, verified by
// Unmatched.S08.CueFx.Registry. The flags stay per-process (read from the command line, automation override).
#include "S08CueFx.h"

#include "HAL/IConsoleManager.h"
#include "Misc/Crc.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace S08CueFx {

namespace {
struct FOverride {
  bool bSet = false;
  bool bFxEnabled = true;
  bool bHitTintLegacy = false;
};
FOverride& Override() {
  static FOverride G;
  return G;
}

FEntry Make(const TCHAR* CueId, const TCHAR* System, const TCHAR* EffectType, bool bSocket, const TCHAR* Socket,
            int32 Budget, bool bPrewarm, const TCHAR* HeroKey = TEXT("")) {
  FEntry E;
  E.CueId = CueId;
  E.System = System;
  E.HeroKey = HeroKey;
  E.EffectType = EffectType;
  E.bSocket = bSocket;
  E.Socket = Socket;
  E.SpriteBudget = Budget;
  E.bPrewarm = bPrewarm;
  return E;
}
}  // namespace

bool FxEnabled() {
  if (Override().bSet) return Override().bFxEnabled;
  return !FParse::Param(FCommandLine::Get(), FxLegacyFlagName);
}

bool HitTintLegacy() {
  if (Override().bSet) return Override().bHitTintLegacy;
  return FParse::Param(FCommandLine::Get(), HitTintLegacyFlagName);
}

void SetOverrideForTest(bool bFxEnabled, bool bHitTintLegacy) {
  Override() = {true, bFxEnabled, bHitTintLegacy};
}

void ResetOverrideForTest() {
  Override() = {};
}

const TArray<FEntry>& Registry() {
  // The vfx blocks of cue-table.json (revision fx-p4-2026-10): paths, attach / socket, prewarm; the sprite
  // budgets from the notes (dust 3-5 discs, 3 chevrons, one star, 3-5 motes, <= 40 embers, one arc / vortex).
  // The systems are missing until FX-13..FX-32 (the tables' status: missing); CUE-014 is per hero (FX-28).
  static const TArray<FEntry> Rows = {
      Make(TEXT("CUE-007"), TEXT("/Game/S08/FX/Board/NS_FX_Dust"), BoardEffectType, false, TEXT(""), 5, true),
      Make(TEXT("CUE-008"), TEXT("/Game/S08/FX/Board/NS_FX_AttackChevrons"), BoardEffectType, false, TEXT(""), 3,
           true),
      Make(TEXT("CUE-011"), TEXT("/Game/S08/FX/Combat/NS_FX_HitStar"), CombatEffectType, false, TEXT(""), 1, true),
      Make(TEXT("CUE-012"), TEXT("/Game/S08/FX/Combat/NS_FX_HealMotes"), CombatEffectType, true, TEXT("Base"), 5,
           true),
      Make(TEXT("CUE-013"), TEXT("/Game/S08/FX/Combat/NS_FX_AshEmbers"), CombatEffectType, false, TEXT(""), 40,
           true),
      Make(TEXT("CUE-014"), TEXT("/Game/S08/FX/Combat/NS_FX_ArthurArc"), CombatEffectType, true, TEXT("Weapon"), 1,
           true, TEXT("KingArthur")),
      Make(TEXT("CUE-014"), TEXT("/Game/S08/FX/Combat/NS_FX_MedusaVortex"), CombatEffectType, true, TEXT("Root"),
           20, true, TEXT("Medusa")),
  };
  return Rows;
}

const FEntry* Find(const FString& CueId, const FString& HeroKey) {
  const FEntry* Out = nullptr;
  for (const FEntry& E : Registry()) {
    if (E.CueId != CueId) continue;
    if (!HeroKey.IsEmpty() && !E.HeroKey.IsEmpty() && E.HeroKey != HeroKey) continue;
    if (!Out) Out = &E;
    if (E.HeroKey == HeroKey) return &E;
  }
  return Out;
}

FString SystemName(const FString& SystemPath) {
  if (SystemPath.IsEmpty()) return TEXT("none");
  int32 Slash = INDEX_NONE;
  SystemPath.FindLastChar(TEXT('/'), Slash);
  return Slash >= 0 ? SystemPath.RightChop(Slash + 1) : SystemPath;
}

uint32 SeedOf(const FString& SystemPath) {
  // FX-04: the seed is a pure function of the asset name (CRC32, positive) - never the time or the frame
  return FCrc::StrCrc32(*SystemName(SystemPath)) & 0x7FFFFFFF;
}

}  // namespace S08CueFx
