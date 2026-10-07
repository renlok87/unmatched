// W4-C: user-facing text of the ART-004 art HUD layer (plate, compact world
// labels, damage numbers) comes from ONE string table, not from literals
// (engine gate memo, HUD row: "StringTable/why.* instead of hardcoded text";
// D-08 RU/EN from the start, GD-048). The table is the CSV
//   <Project>/Content/Localization/StringTables/S08ArtHud.csv
// registered with LOCTABLE_FROMFILE_GAME (namespace/ID "S08ArtHud"), so the
// localization gather picks it up and the source strings change without a
// C++ rebuild; it is staged as a UFS file (Unmatched.Build.cs).
// English stays only in the TRACE (codes such as HERO / MELEE / YOURS): the
// trace lines and the qa010 formats are unchanged byte for byte.
// A missing key renders as the key itself (a visible defect, never silent
// English) and is counted by MissingKeys() - the automation test requires 0.
#pragma once

#include "CoreMinimal.h"

/** Everything a plate view shows, already localized (views render only this). */
struct FS08PlateTexts {
  FText Name;
  FText Team;
  FText Hp;
  FText Statuses;
  float HpFraction = 0.0f;  // 0..1
  bool bOwn = true;
  uint8 TeamSlot = 0;       // W5b-R: team LOOK slot of the chip (0 = P1 circle, 1 = P2 hexagon)
  // VS-4 HB-46 (the H12 plate, UI/UmWorldLayer.h): the role line, the side chip text, «ЦЕЛЬ» in the attack mode
  FText Role;
  FText Side;
  bool bTarget = false;
};

namespace S08ArtHudText {
/** String table id (= namespace) of the art HUD. */
extern const FName TableId;
/** Content-relative CSV path (LOCTABLE_FROMFILE_GAME root = ProjectContentDir). */
extern const TCHAR* const CsvPath;

/** Registers the table once (idempotent); false when it has no entries. */
bool EnsureTable();
/** Entry count of the registered table (0 when missing). */
int32 NumEntries();
/** Keys the code uses (every one must exist in the CSV). */
const TArray<FString>& RequiredKeys();
/** RequiredKeys() missing from the table. */
TArray<FString> MissingKeys();
bool Has(const FString& Key);
/** Table text of Key, or the key itself when it is missing. */
FText Get(const FString& Key);

/** "HP {Hp}/{Max}" etc. - numbers without grouping (byte-identical to the
 *  pre-UMG %d formatting for the en source strings). */
FText PlateHp(int32 Health, int32 MaxHealth);
FText PlateTeam(bool bOwn);
/** Status codes (S08PlateStatuses: HERO, SIDEKICK, MELEE, RANGED, ATTACKER,
 *  TARGET, effect names) -> "plate.status.<code lowercase>" when the table
 *  has it, else the code itself (server effect names stay data), joined with
 *  "plate.status.separator". */
FText PlateStatuses(const TArray<FString>& Codes);
FS08PlateTexts PlateTexts(const FString& Name, int32 Health, int32 MaxHealth, bool bOwn,
                          const TArray<FString>& StatusCodes);
/** Compact world label of a plate neighbour ("{Name} {Hp}/{Max}"). */
FText CompactLabel(const FString& Name, int32 Health, int32 MaxHealth);
/** Full-mode HP line under the world name label ("{Hp}/{Max}"). */
FText HpLabel(int32 Health, int32 MaxHealth);
/** World damage number ("-{Amount}"). */
FText DamageNumber(int32 Amount);
}  // namespace S08ArtHudText
