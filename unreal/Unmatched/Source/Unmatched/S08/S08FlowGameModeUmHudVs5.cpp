// VS-5 E4 (docs/game-design/evidence/VISUAL/VS-4/README.md «Открыто» пп. 2-10; 04-hud-spec.md §2.1, §2.7, §2.8, §2.14):
// the game mode side of the HUD leftovers of VS-4 - new code here, S08FlowGameMode*.cpp only call in.
//   UmHudOwnsSlateBlock  the English Slate blocks of the default view give way to the UMG blocks (ВР-VS5-31...34):
//     draft      «ATTACK (Enter) / CLOSE DRAFT (Esc)» of the attack draft - the attack goes on its own once complete
//                (DE-020), ACTIONS «Атака» (A) and Esc close the draft (04 §2.14, HB-43);
//     scheme     the SCHEME CHOICE header / lines / buttons - the UMG hand (double click plays, HB-24), ACTIONS «Схема»
//                (G) and STATUS «Выберите карту схемы и сыграйте её» say it;
//     resolve    «RESOLVE COMBAT (R)» - the own combat edge's «Завершить бой» (UUmHudCombatEdge, R / Enter);
//     reconnect  «RECONNECTING …» - CONN (HB-14) shows «Синхронизация…» / «Связи нет»; RECONNECT is H14 (VS-7).
//     -S09Markers keeps every Slate block (the gate layer); -S08SlateHud=<block> brings back the UMG block's Slate twin.
#include "S08FlowGameMode.h"

#include "S08ArtLook.h"

bool AS08FlowGameMode::UmHudOwnsSlateBlock(const TCHAR* Block) const {
  if (S08ArtLook::S08Markers() || !UmHud.IsValid()) return false;
  const FString B(Block);
  if (B == TEXT("reconnect")) return !UmHudBlockOnSlate(TEXT("top"));
  if (!UmPendingOwnsCommandPanel()) return false;
  if (B == TEXT("draft")) return UmActionsOnUmg();
  if (B == TEXT("scheme")) return UmActionsOnUmg() && UmHandOnUmg();
  if (B == TEXT("resolve")) return UmCombatOnUmg();
  return false;
}
