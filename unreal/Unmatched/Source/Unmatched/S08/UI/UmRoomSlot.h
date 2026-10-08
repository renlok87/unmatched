// VS-7 SC-17 (docs/game-design/visual/06-tasks/screens.csv SC-17, SC-14; 04-hud-spec.md §1.4; the accepted CX-30 mockups
// art/imagegen/sc17-room-ready-codex, sc14-room-hero-codex; ВР-VS4-SC14-05, ВР-VS4-SC17-01 / -02): one seat of the ROOM -
// UUmRoomSlot (two of them in UUmScreenRoom; code tree, no WBP of its own).
//
//   L 560x200 (720p 500x200), S 300x136: a screen panel (modal skin); the seat hero's avatar 80 su (S 64; CP-07 disc,
//   show=slot; an empty disc without a hero), the name line: the username type.heading + the chip «Хост» (seat 1) or
//   the chip «ИИ-соперник» + «AI Bot» (VS_AI: the server seats the bot on startGame - its hero is never drawn, the line
//   says «Герой ИИ — при старте»); the ready line: the IC-57 ui-check glyph 24 su on a check.on body + «ГОТОВ» or the
//   empty check.off body + «Не готов» (text, never colour alone); the hero line «Medusa · HP 16 · ход 3» and the
//   sidekick line «+ Harpies ×3 · HP 1» (text.secondary); «Герой не выбран» / «Ждём игрока…». No team colour (02 §2.3).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "UmRoomSlot.generated.h"

class UBorder;
class UCanvasPanel;
class UTextBlock;
class US08AnimatedIconWidget;

enum class EUmRoomSeat : uint8 { Player, Waiting, Ai };

struct UNMATCHED_API FUmRoomSlotModel {
  EUmRoomSeat Seat = EUmRoomSeat::Waiting;
  FString Username;
  bool bHost = false;
  bool bReady = false;
  FString HeroName;   // '' = no hero
  FName HeroKey;
  bool bDetails = false;
  int32 Hp = 0;
  int32 Move = 0;
  FString SidekickName;
  int32 SidekickCount = 0;
  int32 SidekickHp = 0;
  bool operator==(const FUmRoomSlotModel& O) const {
    return Seat == O.Seat && Username == O.Username && bHost == O.bHost && bReady == O.bReady && HeroName == O.HeroName &&
           HeroKey == O.HeroKey && bDetails == O.bDetails && Hp == O.Hp && Move == O.Move && SidekickName == O.SidekickName &&
           SidekickCount == O.SidekickCount && SidekickHp == O.SidekickHp;
  }
  bool operator!=(const FUmRoomSlotModel& O) const { return !(*this == O); }
};

UCLASS()
class UNMATCHED_API UUmRoomSlot : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  void Apply(const FUmRoomSlotModel& InModel, const FVector2D& InSizeSu, bool bInClassS, float PxPerSu);
  const FUmRoomSlotModel& GetModel() const { return Model; }
  FString GetNameText() const;
  FString GetReadyText() const;
  FString GetHeroLine() const;
  FString GetSidekickLine() const;
  bool IsReadyGlyphShown() const;
  const FString& GetPortraitLine() const { return PortraitLine; }

  UPROPERTY() TObjectPtr<UCanvasPanel> Canvas;
  UPROPERTY() TObjectPtr<UBorder> Panel;
  UPROPERTY() TObjectPtr<UBorder> Avatar;
  UPROPERTY() TObjectPtr<UTextBlock> NameText;
  UPROPERTY() TObjectPtr<UBorder> HostChip;
  UPROPERTY() TObjectPtr<UTextBlock> HostText;
  UPROPERTY() TObjectPtr<UBorder> ReadyBox;
  UPROPERTY() TObjectPtr<US08AnimatedIconWidget> ReadyIcon;
  UPROPERTY() TObjectPtr<UTextBlock> ReadyText;
  UPROPERTY() TObjectPtr<UTextBlock> HeroLine;
  UPROPERTY() TObjectPtr<UTextBlock> SidekickLine;
  UPROPERTY() TArray<TObjectPtr<UObject>> KeepAlive;

 private:
  FUmRoomSlotModel Model;
  bool bHasModel = false;
  FVector2D SizeSu = FVector2D(560.0, 200.0);
  bool bClassS = false;
  FName AvatarKey;
  bool bAvatarBuilt = false;
  float AvatarPx = 0.0f;
  bool AvatarClassS = false;
  FString PortraitLine;
};
