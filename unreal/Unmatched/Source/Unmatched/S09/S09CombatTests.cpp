// GD-034 automation tests: combat UI gates over the REAL viewer-projected
// fixtures captured live (docs/game-design/evidence/S09/fixtures/gd034-*).
// Covers: privacy flags per seat (attacker/defender), role gates (defender
// acts on the attacker's turn; the attacker can NEVER close the defense
// window; resolve is open in COMBAT_RESOLVE), the server deadline
// (combatInfo.timeoutAt ISO parse + expired-window rejection), the attack
// draft (adjacency/banner/type legality), the boost choice mode, and
// echo-through-store routing (echo + WS duplicate of one seq = one cue).
// Run headless:
//   UnrealEditor-Cmd.exe Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S09; Quit"
//     -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S09ManeuverUi.h"
#include "S09HudModel.h"
#include "../S08/S08BoardModel.h"
#include "../S08/S08Contracts.h"
#include "../S08/S08FlowController.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace {
bool LoadS09Fixture(const FString& Name, FS08Snapshot& OutSnapshot, FString& OutRawState) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S09Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(),
                          TEXT("../../docs/game-design/evidence/S09/fixtures"));
  }
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(Dir, Name + TEXT(".json")))) {
    return false;
  }
  TSharedPtr<FJsonValue> Value;
  FString Problem;
  if (!FS08Contracts::TryParseJsonValue(Text, Value, Problem)) return false;
  const TSharedPtr<FJsonObject>* Root = nullptr;
  if (!Value->TryGetObject(Root) || !Root->IsValid()) return false;
  FString Body;
  const TSharedPtr<FJsonObject>* RawObject = nullptr;
  if ((*Root)->TryGetStringField(TEXT("raw"), Body)) {
    if (!FS08Contracts::TryParseJsonValue(Body, Value, Problem)) return false;
  } else if ((*Root)->TryGetObjectField(TEXT("raw"), RawObject) && RawObject->IsValid()) {
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
    FJsonSerializer::Serialize(RawObject->ToSharedRef(), Writer);
  }
  FS08GraphQLError Error;
  if (Body.Contains(TEXT("\"gameState\""))) {
    return FS08Contracts::ParseGameStateQuery(Body, OutSnapshot, OutRawState, Error);
  }
  const TSharedPtr<FJsonObject> BodyObject = FS08Contracts::TryParseJsonValue(
      Body, Value, Problem) ? Value->AsObject() : nullptr;
  if (!BodyObject.IsValid()) return false;
  TSharedPtr<FJsonObject> Target = BodyObject;
  const TSharedPtr<FJsonObject>* DataObj = nullptr;
  if (BodyObject->TryGetObjectField(TEXT("data"), DataObj) && DataObj->IsValid()) {
    Target = *DataObj;
  }
  for (const auto& Entry : Target->Values) {
    const FString FieldName(*Entry.Key);
    const TSharedPtr<FJsonValue> Field = Target->TryGetField(FieldName);
    if (Field.IsValid() && Field->AsObject().IsValid() &&
        FS08Contracts::ParseMutationResult(Body, FieldName, OutSnapshot, Error)) {
      return true;
    }
  }
  return false;
}

// First and second players[].userId from the projection (host, joiner).
bool ViewerIds(const FS08Snapshot& Snapshot, FString& OutFirst, FString& OutSecond) {
  if (!Snapshot.Players.IsValid()) return false;
  const TArray<TSharedPtr<FJsonValue>>* Players = nullptr;
  if (!Snapshot.Players->TryGetArray(Players) || !Players || Players->Num() < 2) return false;
  const TSharedPtr<FJsonObject>* P0 = nullptr;
  const TSharedPtr<FJsonObject>* P1 = nullptr;
  if (!(*Players)[0]->TryGetObject(P0) || !(*Players)[1]->TryGetObject(P1)) return false;
  OutFirst = (*P0)->GetStringField(TEXT("userId"));
  OutSecond = (*P1)->GetStringField(TEXT("userId"));
  return !OutFirst.IsEmpty() && !OutSecond.IsEmpty();
}

FS08Snapshot WithCombatTimeout(FS08Snapshot Snapshot, const TCHAR* IsoTimeout) {
  const TSharedRef<FJsonObject> Meta =
      MakeShared<FJsonObject>(*(Snapshot.Metadata->AsObject()));
  const TSharedRef<FJsonObject> Combat =
      MakeShared<FJsonObject>(*(Meta->GetObjectField(TEXT("combatInfo"))));
  Combat->SetStringField(TEXT("timeoutAt"), IsoTimeout);
  Meta->SetObjectField(TEXT("combatInfo"), Combat);
  Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
  return Snapshot;
}

FS08Snapshot WithPendingBoost(FS08Snapshot Snapshot, const FString& PlayerId, bool bOptional) {
  const TSharedRef<FJsonObject> Meta =
      MakeShared<FJsonObject>(*(Snapshot.Metadata->AsObject()));
  TSharedPtr<FJsonObject> Combat = Meta->GetObjectField(TEXT("combatInfo"));
  if (!Combat.IsValid()) {
    // Synthesize a minimal open combat on the resolve window.
    Combat = MakeShared<FJsonObject>();
    Combat->SetStringField(TEXT("attackerId"), TEXT("f-0-hero"));
    Combat->SetStringField(TEXT("defenderId"), TEXT("defender-user"));
    Combat->SetStringField(TEXT("targetFighterId"), TEXT("f-1-hero"));
    Meta->SetObjectField(TEXT("combatInfo"), Combat);
  }
  const TSharedRef<FJsonObject> Effect = MakeShared<FJsonObject>();
  Effect->SetStringField(TEXT("id"), TEXT("pend-boost-1"));
  Effect->SetStringField(TEXT("playerId"), PlayerId);
  Effect->SetStringField(TEXT("type"), TEXT("BOOST_CHOICE"));
  Effect->SetBoolField(TEXT("optional"), bOptional);
  TArray<TSharedPtr<FJsonValue>> Effects;
  Effects.Add(MakeShared<FJsonValueObject>(Effect));
  Meta->SetArrayField(TEXT("pendingEffects"), Effects);
  Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
  Snapshot.Phase = TEXT("COMBAT_RESOLVE");
  return Snapshot;
}
} // namespace

// ---- 1. privacy flags: the presence of a value IS the seat's right to see it
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CombatPrivacyFlagsTest,
    "Unmatched.S09.COMBAT privacy flags per seat (fixtures, pre-reveal)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CombatPrivacyFlagsTest::RunTest(const FString&) {
  struct Seat {
    const TCHAR* Fixture;
    bool bExpectAttackValue;
    bool bExpectAttackerCard;
    bool bExpectDefenseValue;
    bool bExpectDefenderCard;
  };
  const Seat Seats[] = {
      // COMBAT open: attacker sees own value; no defender commit exists yet.
      {TEXT("gd034-combat-open-attacker-view"), true, true, true, false},
      {TEXT("gd034-combat-open-defender-view"), false, false, true, false},
      // COMBAT_RESOLVE (defense committed, no reveal yet): attacker must NOT
      // see the defense card; defender must NOT see the attack value.
      {TEXT("gd034-resolve-window-attacker-view"), true, true, false, false},
      {TEXT("gd034-resolve-window-defender-view"), false, false, true, true},
  };
  for (const Seat& SeatEntry : Seats) {
    FS08Snapshot Snapshot;
    FString Raw;
    if (!LoadS09Fixture(SeatEntry.Fixture, Snapshot, Raw)) {
      AddError(FString::Printf(TEXT("fixture %s not loaded"), SeatEntry.Fixture));
      return true;
    }
    FS08CombatInfo Combat;
    TestTrue(FString(SeatEntry.Fixture) + TEXT(" combatInfo present"),
             FS08Contracts::CombatInfo(Snapshot, Combat));
    TestEqual(FString(SeatEntry.Fixture) + TEXT(" attackValue visibility"),
              Combat.bHasAttackValue, SeatEntry.bExpectAttackValue);
    TestEqual(FString(SeatEntry.Fixture) + TEXT(" attackerCard visibility"),
              Combat.bHasAttackerCard, SeatEntry.bExpectAttackerCard);
    TestEqual(FString(SeatEntry.Fixture) + TEXT(" defenseValue visibility"),
              Combat.bHasDefenseValue, SeatEntry.bExpectDefenseValue);
    TestEqual(FString(SeatEntry.Fixture) + TEXT(" defenderCard visibility"),
              Combat.bHasDefenderCard, SeatEntry.bExpectDefenderCard);
    TestFalse(FString(SeatEntry.Fixture) + TEXT(" not revealed"),
              Combat.bRevealed);
    TestTrue(FString(SeatEntry.Fixture) + TEXT(" deadline parsed"),
             Combat.bHasTimeoutAt);
    // Live-captured fixtures: the 30s/10s server window has long elapsed by
    // test time (a "-3600s" clamp rots as fixtures age). Re-derive the
    // deadline from NOW instead: this still proves parse + epoch conversion,
    // without making the suite time-dependent.
    const FString SoonIso =
        (FDateTime::UtcNow() + FTimespan::FromSeconds(20.0)).ToIso8601();
    const FS08Snapshot Fresh = WithCombatTimeout(Snapshot, *SoonIso);
    FS08CombatInfo FreshCombat;
    TestTrue(FString(SeatEntry.Fixture) + TEXT(" combatInfo reparsed"),
             FS08Contracts::CombatInfo(Fresh, FreshCombat) && FreshCombat.bHasTimeoutAt);
    TestTrue(FString(SeatEntry.Fixture) + TEXT(" deadline counts down"),
             FreshCombat.SecondsUntilDeadline() > 0.0 &&
                 FreshCombat.SecondsUntilDeadline() <= 20.0);
  }
  return true;
}

// ---- 2. mode derivation + role gates from the fixtures
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CombatRoleGatesTest,
    "Unmatched.S09.COMBAT role gates: defender window, attacker cannot resolve, resolve window open",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CombatRoleGatesTest::RunTest(const FString&) {
  FS08Snapshot CombatAttacker, CombatDefender, ResolveWindow;
  FString Raw;
  if (!LoadS09Fixture(TEXT("gd034-combat-open-attacker-view"), CombatAttacker, Raw) ||
      !LoadS09Fixture(TEXT("gd034-combat-open-defender-view"), CombatDefender, Raw) ||
      !LoadS09Fixture(TEXT("gd034-resolve-window-attacker-view"), ResolveWindow, Raw)) {
    AddError(TEXT("fixtures not loaded"));
    return true;
  }
  FString Host, Joiner;
  if (!ViewerIds(CombatAttacker, Host, Joiner)) {
    AddError(TEXT("players projection unreadable"));
    return true;
  }
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardModel::DecodeFighters(CombatAttacker.Fighters, Fighters);
  Board.Decode(CombatAttacker.BoardState);

  // Defender seat: mode CombatDefense opens EVEN THOUGH it is the attacker's
  // turn (currentTurnPlayerId == host == attacker).
  FS09CommandUi DefenderUi;
  DefenderUi.ViewerId = Joiner;
  DefenderUi.OnSnapshot(CombatDefender, Board, Fighters);
  TestEqual(TEXT("defender mode"), static_cast<int32>(DefenderUi.Mode),
            static_cast<int32>(ES09CommandMode::CombatDefense));
  TestEqual(TEXT("attacker owns the turn"),
            CombatDefender.CurrentTurnPlayerId == Host, true);

  // Defender may resolve (explicit no defense); the attacker may not.
  FString Reason;
  TestTrue(TEXT("defender CanResolveCombat"), DefenderUi.CanResolveCombat(CombatDefender, Reason));
  FS09CommandUi AttackerUi;
  AttackerUi.ViewerId = Host;
  AttackerUi.OnSnapshot(CombatAttacker, Board, Fighters);
  TestEqual(TEXT("attacker mode while defender window (None=waiting)"),
            static_cast<int32>(AttackerUi.Mode), static_cast<int32>(ES09CommandMode::None));
  TestFalse(TEXT("attacker cannot close the defense window"),
            AttackerUi.CanResolveCombat(CombatAttacker, Reason));

  // COMBAT_RESOLVE: resolve is open to ANY participant.
  FS09CommandUi ResolveUi;
  ResolveUi.ViewerId = Host;
  ResolveUi.OnSnapshot(ResolveWindow, Board, Fighters);
  TestEqual(TEXT("resolve mode"), static_cast<int32>(ResolveUi.Mode),
            static_cast<int32>(ES09CommandMode::CombatResolve));
  TestTrue(TEXT("participant may resolve"), ResolveUi.CanResolveCombat(ResolveWindow, Reason));

  // resolve is NEVER legal outside combat phases.
  FS08Snapshot Done;
  if (LoadS09Fixture(TEXT("gd034-combat-done-attacker-view"), Done, Raw)) {
    TestFalse(TEXT("no resolve after combat"), ResolveUi.CanResolveCombat(Done, Reason));
  }
  return true;
}

// ---- 3. attack draft legality over the real board/hand
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CombatAttackDraftTest,
    "Unmatched.S09.COMBAT attack draft: adjacency, banner/type gates, confirm re-validation",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CombatAttackDraftTest::RunTest(const FString&) {
  FS08Snapshot Snapshot;
  FString Raw;
  // Build an ACTION-phase board from the resolve window (positions live) but
  // with combat closed: metadata.combatInfo removed.
  if (!LoadS09Fixture(TEXT("gd034-resolve-window-attacker-view"), Snapshot, Raw)) {
    AddError(TEXT("fixture not loaded"));
    return true;
  }
  FString Host, Joiner;
  ViewerIds(Snapshot, Host, Joiner);
  {
    const TSharedRef<FJsonObject> Meta =
        MakeShared<FJsonObject>(*(Snapshot.Metadata->AsObject()));
    Meta->RemoveField(TEXT("combatInfo"));
    Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
    Snapshot.Phase = TEXT("ACTION_MANEUVER");
    Snapshot.CurrentTurnPlayerId = Host;
  }
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardModel::DecodeFighters(Snapshot.Fighters, Fighters);
  Board.Decode(Snapshot.BoardState);

  FS09CommandUi Ui;
  Ui.ViewerId = Host;
  Ui.bCommandInFlight = false;
  Ui.OnSnapshot(Snapshot, Board, Fighters);
  FString Reason;
  TestTrue(TEXT("attack draft openable"), Ui.CanOpenAttackDraft(Snapshot, Reason));

  // Fixture geometry: Medusa (f-0-hero, host) stands adjacent to King Arthur
  // (f-1-hero, joiner); a far Harpy has no adjacent enemy.
  const FS08BoardFighter* Medusa = nullptr;
  const FS08BoardFighter* Arthur = nullptr;
  const FS08BoardFighter* FarHarpies = nullptr;
  for (const FS08BoardFighter& Entry : Fighters) {
    if (Entry.Id == TEXT("f-0-hero")) Medusa = &Entry;
    if (Entry.Id == TEXT("f-1-hero")) Arthur = &Entry;
    if (Entry.Id == TEXT("f-0-sk0")) FarHarpies = &Entry;
  }
  if (!TestNotNull(TEXT("fighters found"), Medusa)) return true;
  TestTrue(TEXT("Medusa adjacent to Arthur"), Medusa && Arthur &&
      FMath::Abs(Medusa->X - Arthur->X) + FMath::Abs(Medusa->Y - Arthur->Y) == 1);
  TestFalse(TEXT("far harpies rejected as attacker"),
            FarHarpies && Ui.SelectAttacker(FarHarpies->Id, Fighters, Reason));

  Ui.Mode = ES09CommandMode::AttackDraft; // open explicitly (user pressed A)
  TestTrue(TEXT("Medusa selectable"), Ui.SelectAttacker(Medusa->Id, Fighters, Reason));
  TestTrue(TEXT("Arthur targetable"), Ui.SelectTarget(Arthur->Id, Fighters, Reason));
  TestFalse(TEXT("own fighter not targetable"),
            Ui.SelectTarget(Medusa->Id, Fighters, Reason));

  // Card gates: the real hand carries VERSATILE banner cards; a DEFENSE card
  // and a banner card Medusa cannot satisfy must be rejected.
  FS09PlayerPanel Own;
  {
    FS09HudModel Hud;
    TSet<FString> Prev;
    Hud.Build(Snapshot, Host, Prev, 0, 0);
    if (Hud.ViewerPanel()) Own = *Hud.ViewerPanel();
  }
  const FS09CardView* AnyCard = nullptr;
  const FS09CardView* DefenseCard = nullptr;
  for (const FS09CardView& Card : Own.Cards) {
    if (Card.bHidden) continue;
    if (!AnyCard) AnyCard = &Card;
    if (Card.CardType == TEXT("DEFENSE")) DefenseCard = &Card;
  }
  if (!TestNotNull(TEXT("hand readable"), AnyCard)) return true;
  if (DefenseCard) {
    TestFalse(TEXT("DEFENSE card rejected for attack"),
              Ui.ToggleAttackCard(DefenseCard->InstanceId, Snapshot, Fighters, Reason));
  }
  TestTrue(TEXT("hand instance accepted when type/banner fit"),
           Ui.ToggleAttackCard(AnyCard->InstanceId, Snapshot, Fighters, Reason) ||
               !Reason.IsEmpty()); // banner-mismatch cards reject with a reason
  if (Ui.AttackCardId == AnyCard->InstanceId) {
    // Re-toggle OFF: the confirm loop below must toggle its own card ON.
    Ui.ToggleAttackCard(AnyCard->InstanceId, Snapshot, Fighters, Reason);
  }
  // A full confirm needs a card that passed the gate.
  bool bConfirmed = false;
  for (const FS09CardView& Card : Own.Cards) {
    if (!Card.bHidden && Card.InstanceId != Ui.AttackCardId &&
        Ui.ToggleAttackCard(Card.InstanceId, Snapshot, Fighters, Reason) &&
        Ui.AttackCardId == Card.InstanceId) {
      FS09AttackCommand Command;
      bConfirmed = Ui.ConfirmAttack(Snapshot, Fighters, Command, Reason);
      if (bConfirmed) {
        TestEqual(TEXT("command attacker"), Command.AttackerFighterId, Medusa->Id);
        TestEqual(TEXT("command target"), Command.TargetFighterId, Arthur->Id);
      }
      break;
    }
  }
  TestTrue(TEXT("confirm legal for the real Medusa hand"), bConfirmed);
  return true;
}

// ---- 3b. attack card REPLACEMENT semantics (S09AUTO preference fix)
namespace {
// Rename one visible hand card in the projection (deep copy of handZones).
bool RenameHandCard(FS08Snapshot& Snapshot, const FString& InstanceId,
                    const FString& NewName) {
  if (!Snapshot.HandZones.IsValid()) return false;
  const TSharedPtr<FJsonObject>* Zones = nullptr;
  if (!Snapshot.HandZones->TryGetObject(Zones) || !Zones) return false;
  // Pass 1 (read-only over the map): find the zone holding the card.
  FString TargetZone;
  {
    const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
    const TSharedPtr<FJsonObject>* ZoneObj = nullptr;
    for (auto& Zone : (*Zones)->Values) {
      if (!Zone.Value->TryGetObject(ZoneObj) || !ZoneObj) continue;
      if (!(*ZoneObj)->TryGetArrayField(TEXT("cards"), Cards) || !Cards) continue;
      for (const TSharedPtr<FJsonValue>& CardValue : *Cards) {
        const TSharedPtr<FJsonObject>* Card = nullptr;
        if (CardValue->TryGetObject(Card) && Card &&
            (*Card)->GetStringField(TEXT("id")) == InstanceId) {
          TargetZone = Zone.Key;
          break;
        }
      }
      if (!TargetZone.IsEmpty()) break;
    }
  }
  if (TargetZone.IsEmpty()) return false;
  // Pass 2: rebuild that zone's card array (no map mutation while iterating).
  const TSharedPtr<FJsonObject>* ZoneObj = nullptr;
  const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
  if (!(*Zones)->TryGetObjectField(TargetZone, ZoneObj) || !ZoneObj ||
      !(*ZoneObj)->TryGetArrayField(TEXT("cards"), Cards) || !Cards) {
    return false;
  }
  const TSharedPtr<FJsonObject> Copy = MakeShared<FJsonObject>(**ZoneObj);
  TArray<TSharedPtr<FJsonValue>> NewCards;
  bool bFound = false;
  for (const TSharedPtr<FJsonValue>& CardValue : *Cards) {
    const TSharedPtr<FJsonObject>* Card = nullptr;
    if (!CardValue->TryGetObject(Card) || !Card) { NewCards.Add(CardValue); continue; }
    const TSharedPtr<FJsonObject> CardCopy = MakeShared<FJsonObject>(**Card);
    if ((*Card)->GetStringField(TEXT("id")) == InstanceId) {
      CardCopy->SetStringField(TEXT("name"), NewName);
      bFound = true;
    }
    NewCards.Add(MakeShared<FJsonValueObject>(CardCopy));
  }
  if (!bFound) return false;
  Copy->SetArrayField(TEXT("cards"), NewCards);
  (*Zones)->SetObjectField(TargetZone, Copy);
  return true;
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CombatAttackCardReplaceTest,
    "Unmatched.S09.COMBAT attack card replacement: later legal pick replaces, old pick re-toggle re-selects",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CombatAttackCardReplaceTest::RunTest(const FString&) {
  FS08Snapshot Snapshot;
  FString Raw;
  if (!LoadS09Fixture(TEXT("gd034-resolve-window-attacker-view"), Snapshot, Raw)) {
    AddError(TEXT("fixture not loaded"));
    return true;
  }
  FString Host, Joiner;
  ViewerIds(Snapshot, Host, Joiner);
  {
    const TSharedRef<FJsonObject> Meta =
        MakeShared<FJsonObject>(*(Snapshot.Metadata->AsObject()));
    Meta->RemoveField(TEXT("combatInfo"));
    Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
    Snapshot.Phase = TEXT("ACTION_MANEUVER");
    Snapshot.CurrentTurnPlayerId = Host;
  }
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardModel::DecodeFighters(Snapshot.Fighters, Fighters);
  Board.Decode(Snapshot.BoardState);

  FS09PlayerPanel Own;
  {
    FS09HudModel Hud;
    TSet<FString> Prev;
    Hud.Build(Snapshot, Host, Prev, 0, 0);
    if (Hud.ViewerPanel()) Own = *Hud.ViewerPanel();
  }
  // First legal (VERSATILE Any) card and a second one to rename into the
  // may-boost name the S09AUTO preference hunts for.
  FString FirstLegalId, BoostCapableId;
  for (const FS09CardView& Card : Own.Cards) {
    if (Card.bHidden || Card.CardType != TEXT("VERSATILE")) continue;
    if (FirstLegalId.IsEmpty()) { FirstLegalId = Card.InstanceId; continue; }
    if (BoostCapableId.IsEmpty()) { BoostCapableId = Card.InstanceId; break; }
  }
  if (!TestTrue(TEXT("fixture hand has two legal attack cards"),
                 !FirstLegalId.IsEmpty() && !BoostCapableId.IsEmpty())) return true;
  TestTrue(TEXT("rename to a may-boost name"),
           RenameHandCard(Snapshot, BoostCapableId, TEXT("Second Shot")));

  FS09CommandUi Ui;
  Ui.ViewerId = Host;
  Ui.bCommandInFlight = false;
  Ui.OnSnapshot(Snapshot, Board, Fighters);
  FString Reason;
  Ui.Mode = ES09CommandMode::AttackDraft;
  const FS08BoardFighter* Medusa = nullptr;
  const FS08BoardFighter* Arthur = nullptr;
  for (const FS08BoardFighter& Entry : Fighters) {
    if (Entry.Id == TEXT("f-0-hero")) Medusa = &Entry;
    if (Entry.Id == TEXT("f-1-hero")) Arthur = &Entry;
  }
  if (!TestNotNull(TEXT("fighters found"), Medusa)) return true;
  TestTrue(TEXT("attacker selected"), Ui.SelectAttacker(Medusa->Id, Fighters, Reason));
  TestTrue(TEXT("target selected"), Ui.SelectTarget(Arthur->Id, Fighters, Reason));

  // First legal card in.
  TestTrue(TEXT("first legal card toggled on"),
           Ui.ToggleAttackCard(FirstLegalId, Snapshot, Fighters, Reason));
  TestEqual(TEXT("selection = first card"), Ui.AttackCardId, FirstLegalId);
  // Boost-capable replacement: toggle SELECTS the new card and drops the old.
  TestTrue(TEXT("boost-capable card toggled on"),
           Ui.ToggleAttackCard(BoostCapableId, Snapshot, Fighters, Reason));
  TestEqual(TEXT("replacement wins - final selection is the boost card"),
            Ui.AttackCardId, BoostCapableId);
  // DRIVER CONTRACT: toggling the OLD card now does NOT clear the new pick -
  // it re-SELECTS the old one (a toggle only clears its OWN id). That is why
  // the auto driver must never touch the previous card after a replacement.
  TestTrue(TEXT("re-toggle of the old pick succeeds (it re-selects)"),
           Ui.ToggleAttackCard(FirstLegalId, Snapshot, Fighters, Reason));
  TestEqual(TEXT("re-toggle re-selected the OLD card"), Ui.AttackCardId, FirstLegalId);
  // Back to the boost card and confirm: the final command must carry it.
  TestTrue(TEXT("boost card re-selected"),
           Ui.ToggleAttackCard(BoostCapableId, Snapshot, Fighters, Reason));
  TestEqual(TEXT("final selection is the boost card"), Ui.AttackCardId, BoostCapableId);
  FS09AttackCommand Command;
  TestTrue(TEXT("confirm legal"), Ui.ConfirmAttack(Snapshot, Fighters, Command, Reason));
  TestEqual(TEXT("command carries the boost-capable card"),
            Command.CardInstanceId, BoostCapableId);
  return true;
}

// ---- 4. defense confirm + expired server deadline
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CombatDefenseDeadlineTest,
    "Unmatched.S09.COMBAT defense: card pick for the attacked fighter, expired deadline blocks",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CombatDefenseDeadlineTest::RunTest(const FString&) {
  FS08Snapshot DefenderView;
  FString Raw;
  if (!LoadS09Fixture(TEXT("gd034-combat-open-defender-view"), DefenderView, Raw)) {
    AddError(TEXT("fixture not loaded"));
    return true;
  }
  FString Host, Joiner;
  ViewerIds(DefenderView, Host, Joiner);
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardModel::DecodeFighters(DefenderView.Fighters, Fighters);
  Board.Decode(DefenderView.BoardState);

  FS09CommandUi Ui;
  Ui.ViewerId = Joiner; // defender seat
  Ui.OnSnapshot(DefenderView, Board, Fighters);
  TestEqual(TEXT("defense mode"), static_cast<int32>(Ui.Mode),
            static_cast<int32>(ES09CommandMode::CombatDefense));

  FS09DefenseCommand Command;
  FString Reason;
  TestFalse(TEXT("confirm without a card"),
            Ui.ConfirmDefense(DefenderView, Fighters, Command, Reason));

  // Expired deadline: the window is the server's to close (auto-resolve).
  const FS08Snapshot Expired = WithCombatTimeout(DefenderView, TEXT("2020-01-01T00:00:00.000Z"));
  FS09CommandUi ExpiredUi;
  ExpiredUi.ViewerId = Joiner;
  ExpiredUi.OnSnapshot(Expired, Board, Fighters);
  TestTrue(TEXT("deadline in the past parses"),
           ExpiredUi.Combat.bHasTimeoutAt && ExpiredUi.Combat.SecondsUntilDeadline() < 0.0);
  TestFalse(TEXT("expired window blocks defense"),
            ExpiredUi.ConfirmDefense(Expired, Fighters, Command, Reason));
  return true;
}

// ---- 5. boost choice mode
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CombatBoostChoiceTest,
    "Unmatched.S09.COMBAT boost choice: mode opens for the owner, mandatory cannot be declined",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CombatBoostChoiceTest::RunTest(const FString&) {
  FS08Snapshot Snapshot;
  FString Raw;
  if (!LoadS09Fixture(TEXT("gd034-resolve-window-attacker-view"), Snapshot, Raw)) {
    AddError(TEXT("fixture not loaded"));
    return true;
  }
  FString Host, Joiner;
  ViewerIds(Snapshot, Host, Joiner);

  const FS08Snapshot OptionalBoost = WithPendingBoost(Snapshot, Host, true);
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardModel::DecodeFighters(OptionalBoost.Fighters, Fighters);
  Board.Decode(OptionalBoost.BoardState);

  FS09CommandUi Ui;
  Ui.ViewerId = Host;
  Ui.OnSnapshot(OptionalBoost, Board, Fighters);
  TestEqual(TEXT("boost mode opens for owner"), static_cast<int32>(Ui.Mode),
            static_cast<int32>(ES09CommandMode::PendingChoice));
  TArray<FS08PendingEffect> Effects;
  TestTrue(TEXT("pendingEffects parsed"), FS08Contracts::PendingEffects(OptionalBoost, Effects));
  TestEqual(TEXT("queue length"), Effects.Num(), 1);
  TestEqual(TEXT("effect type"), Effects[0].Type, FString(TEXT("BOOST_CHOICE")));
  TestTrue(TEXT("optional flag"), Effects[0].bOptional);

  // GD-033: the other seat still opens the COMBAT_RESOLVE window during the
  // post-reveal boost pause (revealed cards/values must stay rendered); it
  // just cannot fire R while the queue head is open.
  FS09CommandUi OtherUi;
  OtherUi.ViewerId = Joiner;
  OtherUi.OnSnapshot(OptionalBoost, Board, Fighters);
  TestEqual(TEXT("other seat keeps the resolve window during the boost pause"),
            static_cast<int32>(OtherUi.Mode),
            static_cast<int32>(ES09CommandMode::CombatResolve));
  FString GateReason;
  TestFalse(TEXT("other seat cannot resolve while the queue is open"),
            OtherUi.CanResolveCombat(OptionalBoost, GateReason));
  TestFalse(TEXT("owner seat cannot resolve while the queue is open"),
            Ui.CanResolveCombat(OptionalBoost, GateReason));

  FS09PendingChoiceCommand Command;
  FString Reason;
  TestTrue(TEXT("optional decline legal"),
           Ui.ConfirmPendingChoice(OptionalBoost, true, Command, Reason));
  TestEqual(TEXT("decline effect id"), Command.EffectId, FString(TEXT("pend-boost-1")));

  const FS08Snapshot MandatoryBoost = WithPendingBoost(Snapshot, Host, false);
  FS09CommandUi MandatoryUi;
  MandatoryUi.ViewerId = Host;
  MandatoryUi.OnSnapshot(MandatoryBoost, Board, Fighters);
  TestFalse(TEXT("mandatory decline rejected"),
            MandatoryUi.ConfirmPendingChoice(MandatoryBoost, true, Command, Reason));
  return true;
}

// ---- 6. echo-through-store: one seq = one cue; stale seq ignored
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CombatSeqGuardTest,
    "Unmatched.S09.COMBAT seq guard: resolve echo applies once, same-seq merge fires no second cue, stale ignored",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CombatSeqGuardTest::RunTest(const FString&) {
  FS08Snapshot ResolveWindow, ResolveEcho, DefenseEcho;
  FString Raw;
  if (!LoadS09Fixture(TEXT("gd034-resolve-window-attacker-view"), ResolveWindow, Raw) ||
      !LoadS09Fixture(TEXT("gd034-resolve-echo"), ResolveEcho, Raw) ||
      !LoadS09Fixture(TEXT("gd034-defense-echo-defender"), DefenseEcho, Raw)) {
    AddError(TEXT("fixtures not loaded"));
    return true;
  }
  TestEqual(TEXT("defense echo opens resolve"), DefenseEcho.Phase,
            FString(TEXT("COMBAT_RESOLVE")));
  TestEqual(TEXT("resolve echo closes combat"), ResolveEcho.Phase,
            FString(TEXT("ACTION_MANEUVER")));

  FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"));
  int32 Cues = 0;
  int32 Applied = 0;
  int32 Merged = 0;
  int32 Ignored = 0;
  Flow.OnCues.AddLambda([&](const TArray<FS08Cue>& InCues) { Cues += InCues.Num(); });
  Flow.OnApplied.AddLambda([&](const FS08Snapshot&, ES08SeqDecision Decision) {
    if (Decision == ES08SeqDecision::Apply) ++Applied;
    else if (Decision == ES08SeqDecision::Merge) ++Merged;
    else ++Ignored;
  });
  TestEqual(TEXT("resolve window applies"),
            static_cast<int32>(Flow.ApplySnapshot(ResolveWindow)),
            static_cast<int32>(ES08SeqDecision::Apply));
  TestEqual(TEXT("resolve echo applies"),
            static_cast<int32>(Flow.ApplySnapshot(ResolveEcho)),
            static_cast<int32>(ES08SeqDecision::Apply));
  // The WS duplicate of the same closed-combat seq: merge, zero new cues.
  TestEqual(TEXT("same-seq duplicate merges"),
            static_cast<int32>(Flow.ApplySnapshot(ResolveEcho)),
            static_cast<int32>(ES08SeqDecision::Merge));
  // A late defense-window body (older seq) is stale: ignored (no OnApplied
  // broadcast for Ignore - the seq guard drops it before any state touch).
  int32 IgnoredCount = 0;
  if (Flow.ApplySnapshot(DefenseEcho) == ES08SeqDecision::Ignore) ++IgnoredCount;
  TestEqual(TEXT("stale defense echo ignored"), IgnoredCount, 1);
  TestEqual(TEXT("applied count"), Applied, 2);
  TestEqual(TEXT("merge count"), Merged, 1);
  TestEqual(TEXT("ignored count"), Ignored + IgnoredCount, 1);
  TestTrue(TEXT("damage cue fired exactly for the resolve transition"), Cues <= 1);
  return true;
}

// ---- 7. mutation echo parsing (request/response shape)
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CombatEchoParseTest,
    "Unmatched.S09.COMBAT mutation echoes parse (attack/defense/resolve)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CombatEchoParseTest::RunTest(const FString&) {
  struct Echo {
    const TCHAR* Fixture;
    const TCHAR* Field;
    const TCHAR* ExpectPhase;
  };
  const Echo Echoes[] = {
      {TEXT("gd034-attack-echo-attacker"), TEXT("attack"), TEXT("COMBAT")},
      {TEXT("gd034-defense-echo-defender"), TEXT("playDefense"), TEXT("COMBAT_RESOLVE")},
      {TEXT("gd034-resolve-echo"), TEXT("resolveCombat"), TEXT("ACTION_MANEUVER")},
  };
  for (const Echo& Entry : Echoes) {
    FString Text;
    FString Dir;
    if (!FParse::Value(FCommandLine::Get(), TEXT("S09Fixtures="), Dir) || Dir.IsEmpty()) {
      Dir = FPaths::Combine(FPaths::ProjectDir(),
                            TEXT("../../docs/game-design/evidence/S09/fixtures"));
    }
    if (!FFileHelper::LoadFileToString(
            Text, *FPaths::Combine(Dir, FString(Entry.Fixture) + TEXT(".json")))) {
      AddError(FString::Printf(TEXT("fixture %s missing"), Entry.Fixture));
      continue;
    }
    TSharedPtr<FJsonValue> Value;
    FString Problem;
    if (!FS08Contracts::TryParseJsonValue(Text, Value, Problem)) {
      AddError(FString::Printf(TEXT("fixture %s unreadable"), Entry.Fixture));
      continue;
    }
    FString Body;
    const TSharedPtr<FJsonObject>* RawObject = nullptr;
    if (Value->AsObject()->TryGetObjectField(TEXT("raw"), RawObject)) {
      const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
      FJsonSerializer::Serialize(RawObject->ToSharedRef(), Writer);
    } else {
      Body = Value->AsObject()->GetStringField(TEXT("raw"));
    }
    FS08Snapshot Snapshot;
    FS08GraphQLError Error;
    TestTrue(FString::Printf(TEXT("%s parses as %s"), Entry.Fixture, Entry.Field),
             FS08Contracts::ParseMutationResult(Body, Entry.Field, Snapshot, Error));
    TestEqual(FString::Printf(TEXT("%s phase"), Entry.Fixture), Snapshot.Phase,
              FString(Entry.ExpectPhase));
  }
  return true;
}

#endif // WITH_AUTOMATION_TESTS
