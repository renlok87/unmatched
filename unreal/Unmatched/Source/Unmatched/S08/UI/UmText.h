// VS-1 HB-05 (04-hud-spec.md §6, ВР-37, ВР-H13, HUD-RULES П5): every player-facing string of the UMG HUD and the
// screens comes from a string table - RU by default, EN second - never from a literal in code.
//   ST_Hud      /Game/UI/Localization/ST_Hud      namespace hud      hud.<block>.<element>[.<state>]
//   ST_Screens  /Game/UI/Localization/ST_Screens  namespace screens  screens.*, settings.*, common.*
//   ST_Why      /Game/UI/Localization/ST_Why      namespace why      the why.* reasons (why-reasons.json)
//   ST_Ms       /Game/UI/Localization/ST_Ms       namespace ms       move selection (03 §9 + ВР-H09 delta)
// The tables hold the EN source; the RU text is the localization target Game (Content/Localization/Game/ru/Game.locres,
// built by tools/s08/hud_contract/hud_strings_build.py). Source culture EN, UI language RU by default
// (Config/DefaultGame.ini [Internationalization]); a language switch (UI-ACC-010) re-resolves every FText of the
// tables in the same frame, no restart. Names of heroes, fighters, cards and boards are data (name / nameRu /
// allBoards) and never go through these tables. A missing key renders "?<key>" and logs one Warning.
#pragma once

#include "CoreMinimal.h"
#include "Internationalization/Text.h"

enum class EUmTable : uint8 { Hud, Screens, Why, Ms };

namespace UmText {
/** String table id (= object path of the asset), e.g. /Game/UI/Localization/ST_Hud.ST_Hud. */
FName TableId(EUmTable Table);
/** Loads the four table assets once and keeps them (idempotent); false when one is missing. */
bool Preload();
/** True when Key is an entry of Table. */
bool Has(EUmTable Table, const FString& Key);
/** The localized text of Key (cached per key: no allocation per frame for an unchanged text);
 *  "?<key>" + one Warning when the key is not in the table. */
FText Get(EUmTable Table, const FString& Key);
/** FText::Format of Get(Table, Key) with named arguments ({n}, {max}, plural via {n}|plural(one=…,few=…,many=…,other=…)). */
FText Format(EUmTable Table, const FString& Key, const FFormatNamedArguments& Args);
/** UI-ACC-010: switch the UI language (and locale) at runtime, e.g. TEXT("ru") / TEXT("en"). */
bool SetUiLanguage(const FString& Culture);
/** Keys of a table in its asset (empty when the asset is missing). */
TArray<FString> Keys(EUmTable Table);
}  // namespace UmText
