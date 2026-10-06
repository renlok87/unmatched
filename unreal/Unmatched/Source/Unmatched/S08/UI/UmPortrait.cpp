// VS-2 CP-08: the portrait circle helpers - see UmPortrait.h.
#include "UmPortrait.h"

#include "UmCardMedia.h"
#include "UmHudTheme.h"
#include "../S08HudTokens.generated.h"
#include "../../S09/S09TurnHud.h"
#include "Engine/Texture2D.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace UmPortrait {
FString SlugOf(const FString& Name) {
  FString Out;
  for (const TCHAR C : Name.ToLower()) {
    if ((C >= TEXT('a') && C <= TEXT('z')) || (C >= TEXT('0') && C <= TEXT('9')) || C == TEXT('-')) {
      Out.AppendChar(C);
    } else if (C == TEXT(' ') || C == TEXT('_')) {
      Out.AppendChar(TEXT('-'));
    }
  }
  return Out;
}

bool IsSidekickKey(FName Key) { return Key.ToString().Contains(TEXT("/")); }

const FUmCardMediaEntry* Find(FName Key) {
  if (Key.IsNone()) return nullptr;
  FString Hero = Key.ToString();
  FString Sidekick;
  if (Hero.Split(TEXT("/"), &Hero, &Sidekick)) return UmCardMedia::FindPortrait(Hero, Sidekick);
  return UmCardMedia::FindPortrait(Hero);
}

FString FallbackText(FName Key, const FString& Name, int32 SidekickNumber) {
  // ВР-CP09 / ВР-07: a harpy is its number, never the "H" of Monogram("Harpies")
  if (Key.ToString().EndsWith(TEXT("/harpies")) && SidekickNumber >= 1 && SidekickNumber <= 3) {
    return FString::FromInt(SidekickNumber);
  }
  return S09TurnHud::Monogram(Name);
}

float SourceCirclePx(const FUmCardMediaEntry& Entry) {
  return Entry.bHasDisc ? static_cast<float>(Entry.Disc.Z * Entry.Src.X) : static_cast<float>(Entry.Src.X);
}

FVector4 UvRect(const FUmCardMediaEntry& Entry) {
  const FVector Disc = Entry.bHasDisc ? Entry.Disc : FVector(0.5, 0.5, 1.0);
  const double R = 0.5 * Disc.Z;
  return FVector4((Disc.X - R) * Entry.Uv.X, (Disc.Y - R) * Entry.Uv.Y, (Disc.X + R) * Entry.Uv.X,
                  (Disc.Y + R) * Entry.Uv.Y);
}

float CappedSu(float ShowSu, float SrcCirclePx, float PxPerSu) {
  if (SrcCirclePx <= 0.0f || PxPerSu <= 0.0f) return ShowSu;
  return FMath::Min(ShowSu, CapScale * SrcCirclePx / PxPerSu);
}

float Desaturation(EUmPortraitState State) { return State == EUmPortraitState::Avatar ? 0.0f : 1.0f; }

float Opacity(EUmPortraitState State) { return State == EUmPortraitState::Loser ? LoserOpacity : 1.0f; }

const TCHAR* StateName(EUmPortraitState State) {
  switch (State) {
    case EUmPortraitState::Fallen: return TEXT("fallen");
    case EUmPortraitState::Loser: return TEXT("loser");
    default: return TEXT("avatar");
  }
}

void SetupDiscMid(UMaterialInstanceDynamic& Mid, const FUmCardMediaEntry& Entry, UTexture2D* Tex, float CircleSu) {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  Mid.SetTextureParameterValue(ParamAvatar, Tex);
  const FVector4 R = UvRect(Entry);
  Mid.SetVectorParameterValue(ParamUvRect, FLinearColor(R.X, R.Y, R.Z, R.W));
  FLinearColor Edge = Theme.Color(TEXT("panel.edge"));
  Edge.A = S08HudTokens::Alpha_PanelEdge;  // the rim keeps the token's alpha over panel.bg (4.0 : 1)
  Mid.SetVectorParameterValue(ParamEdgeColor, Edge);
  Mid.SetVectorParameterValue(ParamKeylineColor, Theme.Color(TEXT("mark.keyline")));
  Mid.SetVectorParameterValue(ParamFillColor, Theme.Color(TEXT("card.navy")));
  Mid.SetScalarParameterValue(ParamEdgeFrac, EdgeSu / FMath::Max(CircleSu, 1.0f));
  Mid.SetScalarParameterValue(ParamKeylineFrac, KeylineSu / FMath::Max(CircleSu, 1.0f));
}

FString TraceLine(FName Key, const FString& Texture, float Su, float PxPerSu, float SrcCirclePx, const TCHAR* Show,
                  const TCHAR* Side, EUmPortraitState State) {
  const float Px = Su * PxPerSu;
  const float Scale = SrcCirclePx > 0.0f && Texture != TEXT("monogram") ? Px / SrcCirclePx : 0.0f;
  return FString::Printf(TEXT("PORTRAIT id=%s tex=%s su=%.1f px=%.1f scale=%.3f show=%s side=%s state=%s"),
                         Key.IsNone() ? TEXT("none") : *Key.ToString(), Texture.IsEmpty() ? TEXT("monogram") : *Texture, Su,
                         Px, Scale, Show, Side, StateName(State));
}
}  // namespace UmPortrait
