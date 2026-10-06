// VS-3 CP-03...CP-06, CP-14...CP-20 review sheets in the backend-less icon gallery (-S08IconGallery, review tooling):
//   -S08IconGalleryCards=<page>  UUmCardWidget (the real widget, theme, M_UmCardFace, registry textures) on panel.bg.inset
//                                with the card data of the backend (docs/game-design/evidence/S01/content-<hero>.json,
//                                the S01 capture of the content API - names, types, values, banners, copies):
//     1-8   CP-03 / CP-04  every card of the deck: King Arthur RU / EN, Medusa RU / EN, at 150 x 208 (hand) and 225 x 312
//                          (hover) - odd pages 150 x 208, even 225 x 312 (1 KA RU, 3 KA EN, 5 Medusa RU, 7 Medusa EN);
//     9-10  CP-05 / CP-06  the back of King Arthur / Medusa in its five displays (48 x 67, 32 x 45, 150 x 208, 230 x 319,
//                          the inspector 460 x 640);
//     11    CP-14          M_UmCardFace: the scan at 1.0 x (1 : 1), in the hand (0.52) and the deck chip (0.11), normal and
//                          "unplayable" (Desaturation 0.6, Opacity 0.7);
//     12    CP-14          the card.frame.* skins at 150 x 208 and 230 x 319 (idle, hover, selected, warning, flash,
//                          focus) and the minis 48 x 67 / 32 x 45; 13 - the inspector RU 460 x 640 and EN 408 x 566;
//     14    CP-15          one card in every display, RU and EN, the fallback (no key) and the -S08CardArtLegacy look;
//     15    CP-16          a hand of 7: two defense cards unplayable outside combat (why.defense.only.in.combat), one
//                          new card (the dot appears at t = 0);
//     16    CP-17          hover (the tween from t = 0), selected, selected + hover, focus, lowered + hover, CUE-006 flash;
//     17    CP-18          the own boost (face -> back at t = 0, chip "+N" from 150 ms), the opponent's (back, chip without
//                          a number), the boost of a maneuver (face up);
//     18    CP-19          the hand over its limit: every card a candidate, two marked (16 su down, card-drop at t = 0);
//     19    CP-20          the reveal: the attack card turns at t = 0, the defense card 120 ms later (DefenseFlipDelayMs).
//   With -S08IconGalleryShots=<dir> -S08IconGalleryTimes=<ms,..> the gallery clock (FS08FlowGameMode IconGalleryTick)
//   freezes every card at each time (motion sheets: 0 / 72 / 120 / 180, 0 / 75 / 150, 0 / 40 / 80 / 120 / 160 / 200 /
//   280 ms; -S08ReducedMotion for the reduced ones).
// Trace: 'UMGALLERY cards page=<p> pxPerSu=<x> cells=<n>' and per card 'UMGALLERY card <cell> CARD-ART ...' (check-trace).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudModel.h"
#include "UmCardWidget.h"
#include "UmCardGallery.generated.h"

class UBorder;
class UUmCardWidget;
class UVerticalBox;

namespace UmCardGallery {
inline constexpr int32 PageCount = 19;
/** The cards of a hero's deck from the S01 capture of the content API (docs/game-design/evidence/S01/content-<hero>.json);
 *  Copies gets the count of each. Empty when the file is missing. */
UNMATCHED_API TArray<FS09CardView> LoadDeck(const FString& HeroSlug, TArray<int32>* Copies = nullptr);
}  // namespace UmCardGallery

UCLASS()
class UNMATCHED_API UUmCardsGalleryWidget : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  /** Builds page Page (1-based) for a canvas of CanvasSu at PxPerSu; returns the trace lines. */
  TArray<FString> Build(int32 Page, const FVector2D& CanvasSu, float PxPerSu);
  /** Freezes every card's clock at TMs (the actions of the page started at 0) and returns their CARD-ART lines. */
  TArray<FString> SetClockMs(float TMs);
  const TArray<TObjectPtr<UUmCardWidget>>& GetCards() const { return Cards; }

 private:
  UUmCardWidget* AddCard(class UHorizontalBox* Row, const FString& Caption, const FS09CardView& Data, const FString& Hero,
                         EUmCardShow Show, const FString& Lang, bool bFaceDown = false, int32 Legacy = -1);
  class UHorizontalBox* AddRow(const FString& Title);
  UPROPERTY() TObjectPtr<UBorder> Background;
  UPROPERTY() TObjectPtr<UVerticalBox> Rows;
  UPROPERTY() TArray<TObjectPtr<UUmCardWidget>> Cards;
  UPROPERTY() TArray<TObjectPtr<UObject>> KeepAlive;
  TArray<FString> CellNames;
  int32 PageNow = 1;
  float PxPerSuNow = 1.0f;
};
