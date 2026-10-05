// DE-024 (W-23; 02 SD-42, SD-43; 01 "Резолюция ревью" п. 4; 02-ux-ui-spec §4.2 "Лимит руки", §7.1 UI-ACC-012): the
// hand limit in the game mode.
//   - The rule toast (ms.hint.hand.limit): the first time in the match the own hand grows to the limit (7) it shows the
//     rule once, over the hand strip inside the hand panel. It never blocks input: it is not focusable (keys stay with
//     the game), only its own rectangle takes a click (a click there closes it), nothing else waits for it. It closes
//     at the end of the turn it appeared in or at GAME_OVER and does not come back in that match (FS09HandLimitHint).
//     UI-ACC-012 off (US08UserSettings::bRuleHints, -S08RuleHints=off) - no toast.
//   - The discard itself stays the server's order (SD-43): after the last action the server keeps the turn in TURN_END
//     with metadata.pendingHandDiscard, the command state opens the discard at once (no cancel - Esc and the clear
//     button do not exist for it), the pick is a click and the CONFIRM button / Enter (no drag, D-05), and the server
//     passes the turn by itself. The pending widget lines and the hand highlight come from FS09DiscardPick, the same
//     for the limit and an effect's DISCARD_CARDS (RefreshHud).
// Trace: 'HUD-HINT config ...', 'HUD-HINT rule=hand-limit show|close=... ...', 'HUD-HINT rule=hand-limit suppressed=off'.
#include "S08FlowGameMode.h"

#include "S08TraceLog.h"
#include "S08UserSettings.h"
#include "S08WhyText.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

namespace {
FLinearColor HintSrgb(uint8 R, uint8 G, uint8 B, float A = 1.0f) {
  FLinearColor C = FLinearColor::FromSRGBColor(FColor(R, G, B));
  C.A = A;
  return C;
}
}  // namespace

TSharedRef<SWidget> AS08FlowGameMode::BuildHandLimitHint() {
  // BuildUi runs before the trace opens: the line waits in ArtHud.PendingTrace like the other HUD config lines.
  bRuleHints = US08UserSettings::RuleHintsNow();
  const US08UserSettings* Saved = US08UserSettings::Get();
  ArtHud.PendingTrace.Add(FString::Printf(TEXT("HUD-HINT config ruleHints=%d saved=%d limitDefault=%d"),
                                          bRuleHints ? 1 : 0, Saved && Saved->bRuleHints ? 1 : 0,
                                          FS09HandLimitHint::DefaultLimit));
  return SAssignNew(HandHintBox, SBox)
      .Visibility(EVisibility::Collapsed)
      .Padding(FMargin(0.0f, 0.0f, 0.0f, 6.0f))
      [SNew(SButton)
           .IsFocusable(false)
           .ContentPadding(FMargin(12.0f, 6.0f))
           .ButtonColorAndOpacity(HintSrgb(0x5A, 0x46, 0x1E))
           .OnClicked_Lambda([this]() {
             DismissHandLimitHint();
             return FReply::Handled();
           })
           [SNew(SVerticalBox) +
            SVerticalBox::Slot().AutoHeight()
                [SAssignNew(HandHintText, STextBlock)
                     .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))
                     .ColorAndOpacity(FSlateColor(HintSrgb(0xFF, 0xE6, 0xA8)))] +
            SVerticalBox::Slot().AutoHeight().Padding(0.0f, 2.0f, 0.0f, 0.0f)
                [SNew(STextBlock)
                     .Text(FText::FromString(S08WhyText::En(FName(TEXT("ms.hint.close")))))
                     .Font(FCoreStyle::GetDefaultFontStyle("Regular", 12))
                     .ColorAndOpacity(FSlateColor(HintSrgb(0xD8, 0xD0, 0xBC)))]]];
}

void AS08FlowGameMode::FeedHandLimitHint(const FS08Snapshot& Snapshot) {
  const FS09PlayerPanel* Own = Hud.ViewerPanel();
  if (!Hud.bValid || !Own) return;
  const int32 Limit = FS09HandLimitHint::LimitOf(Own->HandMaxSize);
  const FString TurnKey = FString::Printf(TEXT("%s#%d"), *Snapshot.CurrentTurnPlayerId, Snapshot.TurnCount);
  const FString GameId = Flow.IsValid() ? Flow->GetRoom().GameId : FString();
  const FS09HandLimitHintEvent Event =
      HandLimitHint.OnApplied(GameId, TurnKey, Hud.bGameOver, Own->HandCount, Limit, bRuleHints);
  if (Event.Closed != ES09HintClose::None) {
    FS08Trace::Write(FString::Printf(TEXT("HUD-HINT rule=hand-limit close=%s seq=%d hand=%d/%d"),
                                     FS09HandLimitHint::CloseName(Event.Closed), Snapshot.SequenceNumber,
                                     Own->HandCount, Limit));
  }
  if (Event.bShown) {
    TMap<FString, FString> Args;
    Args.Add(TEXT("n"), FString::FromInt(HandLimitHint.ShownLimit()));
    if (HandHintText.IsValid()) {
      HandHintText->SetText(FText::FromString(S08WhyText::En(FName(TEXT("ms.hint.hand.limit")), Args)));
    }
    FS08Trace::Write(FString::Printf(TEXT("HUD-HINT rule=hand-limit show seq=%d hand=%d/%d turn=%s phase=%s blocking=0"),
                                     Snapshot.SequenceNumber, Own->HandCount, Limit,
                                     Hud.bViewerTurn ? TEXT("own") : TEXT("opp"), *Snapshot.Phase));
  }
  if (!bRuleHints && !bRuleHintOffTraced && !Hud.bGameOver && Own->HandCount >= Limit) {
    bRuleHintOffTraced = true;  // UI-ACC-012 off: one line for the acceptance trace, no toast
    FS08Trace::Write(FString::Printf(TEXT("HUD-HINT rule=hand-limit suppressed=off seq=%d hand=%d/%d"),
                                     Snapshot.SequenceNumber, Own->HandCount, Limit));
  }
  ApplyHandLimitHintVisibility();
}

void AS08FlowGameMode::DismissHandLimitHint() {
  if (!HandLimitHint.Dismiss()) return;
  const FS09PlayerPanel* Own = Hud.ViewerPanel();
  FS08Trace::Write(FString::Printf(TEXT("HUD-HINT rule=hand-limit close=click seq=%d hand=%d"), Hud.SequenceNumber,
                                   Own ? Own->HandCount : -1));
  ApplyHandLimitHintVisibility();
}

void AS08FlowGameMode::ApplyHandLimitHintVisibility() {
  if (!HandHintBox.IsValid()) return;
  // the box itself never takes a hit; the button inside takes clicks only over its own rectangle
  const EVisibility Vis = HandLimitHint.IsVisible() ? EVisibility::SelfHitTestInvisible : EVisibility::Collapsed;
  if (HandHintBox->GetVisibility() != Vis) HandHintBox->SetVisibility(Vis);
}
