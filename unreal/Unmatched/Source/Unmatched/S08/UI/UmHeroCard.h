// VS-7 SC-14 (docs/game-design/visual/06-tasks/screens.csv SC-14; 04-hud-spec.md §1.4, ВР-H12; the accepted CX-30 mockup
// art/imagegen/sc14-room-hero-codex and its decisions ВР-VS4-SC14-01, -02, -06, -11): one hero card of the ROOM grid -
// UUmHeroCard (pooled by UUmScreenRoom; code tree, no WBP of its own) - and the small helpers the ROOM parts share.
//
//   L 300x420   panel.inset body; portrait 120 su (CP-07 disc, show=room), the name type.heading, «HP 18 · ход 2»
//               type.body (tabular digits), the attack word type.body text.secondary (ВР-SC12: «ближний бой» / «дальний
//               бой», no icon), the sidekick row: a 40 su mini portrait + «Merlin · HP 7 · дальний бой» / «Harpies ×3 ·
//               HP 1 · ближний бой» (one picture, the count as «×3»), the ability: chip «EN» + up to 3 lines and «…»
//               (type.caption, text.secondary; the DB has EN only, ВР-VS4-SC14-02), at the bottom «ВЫБРАТЬ» 40 su across.
//   S 360x240   portrait 80 su left, the text right, the ability 2 lines (ВР-VS4-SC14-11).
//   states      normal; hover (panel.bg.hover body); picked (own: 3 su state.pending edge + the selected chip «ВЫБРАНО»);
//               taken (the opponent's: portraits at saturation x0.4, texts text.secondary, no button - why.hero.taken
//               «Выбран соперником» in its slot and as the tooltip); loading (no details yet: the skeleton plate).
//   press       «ВЫБРАТЬ» through the screen's arbiter (id screens.room.hero.pick.<index>); never primary.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudPress.h"
#include "UmHeroCard.generated.h"

class UBorder;
class UCanvasPanel;
class UImage;
class UTextBlock;
class UUmButton;
class UWidgetTree;
class US08AnimatedIconWidget;

/** Shared helpers of the ROOM / LOADING parts. */
namespace UmRoomUi {
UNMATCHED_API void Place(UWidget* W, const FVector2D& Pos, const FVector2D& Size);
UNMATCHED_API void Style(class UTextBlock* T, const TCHAR* Type, const TCHAR* Color);
UNMATCHED_API float MeasureW(const FText& Text, const TCHAR* Type);
/** Greedy word wrap at WidthSu: at most Lines lines, the last one ends with «…» when the text did not fit. */
UNMATCHED_API FString ClampLines(const FString& Text, const TCHAR* Type, float WidthSu, int32 Lines);
UNMATCHED_API void Vis(UWidget* W, bool bOn, bool bHit = false);
UNMATCHED_API bool Icon(US08AnimatedIconWidget* W, const TCHAR* Id, float Su);
UNMATCHED_API FText S(const TCHAR* Key);
/** properties.attackType -> «ближний бой» / «дальний бой» (melee / range; anything else as the DB has it). */
UNMATCHED_API FText AttackWord(const FString& AttackType);
/** «HP {hp} · ход {move}». */
UNMATCHED_API FText Stats(int32 Hp, int32 Move);
/** «Merlin · HP 7» / «Harpies ×3 · HP 1» (+ « · дальний бой» when bAttack). */
UNMATCHED_API FString SidekickLine(const FString& Name, int32 Count, int32 Hp, const FString& AttackType, bool bAttack);
/** A disc of the hero / sidekick key or the empty seat disc (card.navy + panel.edge) when Key is none. */
UNMATCHED_API UWidget* MakeDisc(UWidgetTree& Tree, UObject* Outer, FName Key, const FString& Name, float Su, float PxPerSu,
                                float Desaturation, TArray<TObjectPtr<UObject>>& KeepAlive, FString* OutLine, const TCHAR* Show);
}  // namespace UmRoomUi

enum class EUmHeroCardState : uint8 { Normal, Picked, Taken, Loading };

struct UNMATCHED_API FUmHeroCardModel {
  FString HeroId;
  FString Name;      // the database name (ВР-VS4-SC14-01)
  FName Key;         // the portrait slug (king-arthur, medusa)
  bool bDetails = false;
  int32 Hp = 0;
  int32 Move = 0;
  FString AttackType;
  FString SidekickName;
  FName SidekickKey;  // king-arthur/merlin, medusa/harpies
  int32 SidekickCount = 0;
  int32 SidekickHp = 0;
  FString SidekickAttack;
  FString Ability;
  EUmHeroCardState State = EUmHeroCardState::Normal;
  bool bEnabled = true;  // false while a pick is in flight (why.syncing)
  bool operator==(const FUmHeroCardModel& O) const {
    return HeroId == O.HeroId && Name == O.Name && bDetails == O.bDetails && Hp == O.Hp && Move == O.Move &&
           AttackType == O.AttackType && SidekickName == O.SidekickName && SidekickCount == O.SidekickCount &&
           SidekickHp == O.SidekickHp && SidekickAttack == O.SidekickAttack && Ability == O.Ability && State == O.State &&
           bEnabled == O.bEnabled;
  }
  bool operator!=(const FUmHeroCardModel& O) const { return !(*this == O); }
};

UCLASS()
class UNMATCHED_API UUmHeroCard : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  void SetPress(FName Id, const TSharedPtr<FS09HudPressArbiter>& Arbiter, const FS09OnHudPressOutcome& OnOutcome);
  /** The model, the card size (L 300x420 / S 360x240) and px per su (the portrait cap). */
  void Apply(const FUmHeroCardModel& InModel, const FVector2D& InSizeSu, bool bInClassS, float PxPerSu);
  const FUmHeroCardModel& GetModel() const { return Model; }
  bool IsHovered() const { return bHover; }
  FString GetStatsText() const;
  FString GetAttackText() const;
  FString GetSidekickText() const;
  FString GetAbilityText() const;
  FString GetTakenText() const;
  bool IsPickShown() const;
  /** The PORTRAIT lines of the last build (show=room). */
  const TArray<FString>& GetPortraitLines() const { return PortraitLines; }

  UPROPERTY() TObjectPtr<UCanvasPanel> Canvas;
  UPROPERTY() TObjectPtr<UBorder> Body;
  UPROPERTY() TObjectPtr<UBorder> Edge;
  UPROPERTY() TObjectPtr<UBorder> PortraitBox;
  UPROPERTY() TObjectPtr<UTextBlock> NameText;
  UPROPERTY() TObjectPtr<UTextBlock> StatsText;
  UPROPERTY() TObjectPtr<UTextBlock> AttackText;
  UPROPERTY() TObjectPtr<UBorder> SidekickBox;
  UPROPERTY() TObjectPtr<UTextBlock> SidekickText;
  UPROPERTY() TObjectPtr<UBorder> LangChip;
  UPROPERTY() TObjectPtr<UTextBlock> AbilityText;
  UPROPERTY() TObjectPtr<UUmButton> PickButton;
  UPROPERTY() TObjectPtr<UTextBlock> TakenText;
  UPROPERTY() TArray<TObjectPtr<UObject>> KeepAlive;

 protected:
  virtual void NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual void NativeOnMouseLeave(const FPointerEvent& InMouseEvent) override;

 private:
  void Layout();
  void Restyle();
  void RebuildDiscs(float PxPerSu);

  FUmHeroCardModel Model;
  bool bHasModel = false;
  FVector2D SizeSu = FVector2D(300.0, 420.0);
  bool bClassS = false;
  bool bHover = false;
  FName DiscKey;
  FName DiscSidekickKey;
  EUmHeroCardState DiscState = EUmHeroCardState::Normal;
  float DiscPx = 0.0f;
  bool DiscClassS = false;
  TArray<FString> PortraitLines;
};
