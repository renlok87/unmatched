#include "S08HeroesV2.h"

#include "S08ArtPreviewMedusa.h"
#include "S08BoardModel.h"
#include "S08IconMotion.h"
#include "Animation/AnimSequenceBase.h"
#include "Components/PrimitiveComponent.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace S08HeroesV2 {
namespace {
// -1 = read the command line, 0/1 = automation override.
int32 GFlagOverride = -1;
}  // namespace

bool FlagEnabled() {
  if (GFlagOverride >= 0) return GFlagOverride == 1;
  // ART-DEFAULT: on unless rolled back; -ArtPreviewHeroesV2 (FlagName) is not read any more (no-op alias).
  return Decide(LegacyRequested(), S08ArtPreviewAllMedusa());
}

bool LegacyRequested() { return FParse::Param(FCommandLine::Get(), LegacyFlagName); }

void SetFlagOverrideForTest(bool bEnabled) { GFlagOverride = bEnabled ? 1 : 0; }

void ResetFlagOverrideForTest() { GFlagOverride = -1; }

const TCHAR* ClipName(EClip Clip) {
  switch (Clip) {
    case EClip::Idle: return TEXT("Idle");
    case EClip::LungeAttack: return TEXT("LungeAttack");
    case EClip::HitReact: return TEXT("HitReact");
    case EClip::DeathSettle: return TEXT("DeathSettle");
    default: return TEXT("None");
  }
}

const TCHAR* EventName(EEvent Event) {
  switch (Event) {
    case EEvent::Spawn: return TEXT("spawn");
    case EEvent::Attack: return TEXT("attack");
    case EEvent::Damaged: return TEXT("damaged");
    case EEvent::Defeated: return TEXT("defeated");
    default: return TEXT("clipFinished");
  }
}

FClipChoice NextClip(EClip Current, EEvent Event) {
  FClipChoice Out;
  if (Current == EClip::DeathSettle) {
    Out.Clip = EClip::DeathSettle;  // the final pose holds; nothing restarts it
    return Out;
  }
  switch (Event) {
    case EEvent::Defeated:
      Out.Clip = EClip::DeathSettle;
      Out.bRestart = true;
      break;
    case EEvent::Damaged:
      Out.Clip = EClip::HitReact;
      Out.bRestart = true;
      break;
    case EEvent::Attack:
      Out.Clip = EClip::LungeAttack;
      Out.bRestart = true;
      break;
    case EEvent::Spawn:
      // Every board sync re-applies the fighter: only a figure with no clip yet starts Idle; a running
      // LungeAttack / HitReact / Idle is left alone.
      Out.Clip = Current == EClip::None ? EClip::Idle : Current;
      Out.bRestart = Current == EClip::None;
      break;
    case EEvent::ClipFinished:
      // Only a finished one-shot returns to Idle; a stale timer on Idle / None changes nothing.
      if (Current == EClip::LungeAttack || Current == EClip::HitReact) {
        Out.Clip = EClip::Idle;
        Out.bRestart = true;
      } else {
        Out.Clip = Current;
      }
      break;
  }
  return Out;
}

float IdlePhase(const FString& FighterId) {
  uint32 Hash = 2166136261u;
  for (const TCHAR Ch : FighterId) {
    Hash ^= static_cast<uint32>(Ch);
    Hash *= 16777619u;
  }
  return static_cast<float>(Hash % 10000u) / 10000.0f;
}

const TArray<FHeroSpec>& Specs() {
  // Budgets: figure_height_m of the look-dev C ue-import profiles (0.55 / 0.45 / 0.55 / 0.42 m) and the card
  // ranges of 17-art-production-spec §4.2. Measured tops: king-arthur-lookdev-v2.md (crown 55.0, sword 60.06),
  // merlin-lookdev-v2.md + merlin-h2-lookdev-ue-import.json (hood 44.986, staff crystal 49.42),
  // medusa-lookdev-v2.md (55.009 / 55.01), harpy-lookdev-v2.md (42.00, wings do not rise above it).
  // Idle lengths: anim-v2 decisions (4) / the H2Anim tables of the look-dev reports.
  // Contact frames (DE-010): LungeAttack "design" of the *-h2anim.json build profiles (01 F-03).
  static const TArray<FHeroSpec> Table = {
      {TEXT("King Arthur"), TEXT("KingArthur"), TEXT("H2LD"), true, 55.0f, 52.0f, 56.0f, 55.0f, 60.06f, 2.5f, 7},
      {TEXT("Merlin"), TEXT("Merlin"), TEXT("H2LD"), false, 45.0f, 40.0f, 48.0f, 44.986f, 49.42f, 3.0f, 8},
      {TEXT("Medusa"), TEXT("Medusa"), TEXT("H2LD"), true, 55.0f, 50.0f, 55.0f, 55.009f, 55.01f, 56.0f / 24.0f, 8},
      {TEXT("Harpies"), TEXT("Harpy"), TEXT("H3LD"), false, 42.0f, 35.0f, 42.0f, 42.0f, 42.0f, 2.0f, 7},
  };
  return Table;
}

const FHeroSpec* Find(bool bArtBoard, bool bHeroesV2, const FString& FighterName) {
  if (!bArtBoard || !bHeroesV2) return nullptr;
  for (const FHeroSpec& Spec : Specs()) {
    if (FighterName.Equals(Spec.FighterName, ESearchCase::IgnoreCase)) return &Spec;
  }
  return nullptr;
}

float FigureScale(const FHeroSpec& Spec) {
  if (Spec.FigureTopUU <= 0.0f) return 1.0f;
  return FMath::Clamp(Spec.BudgetUU / Spec.FigureTopUU, 0.5f, 2.0f);
}

static FString StageRoot(const FHeroSpec& Spec) {
  return FString::Printf(TEXT("/Game/PipelineCandidates/%s/%s"), Spec.Key, Spec.Stage);
}

FString MeshPath(const FHeroSpec& Spec) {
  return FString::Printf(TEXT("%s/Meshes/SK_%s_%s"), *StageRoot(Spec), Spec.Key, Spec.Stage);
}

FString PedestalPath(const FHeroSpec& Spec) {
  return FString::Printf(TEXT("%s/Meshes/SM_%s_%s_Base"), *StageRoot(Spec), Spec.Key, Spec.Stage);
}

FString BodyMaterialPath(const FHeroSpec& Spec, ES08TeamSlot Look) {
  return FString::Printf(TEXT("%s/Materials/MI_%s_%s_%s"), *StageRoot(Spec), Spec.Key, Spec.Stage,
                         S08TeamSlotName(Look));
}

FString PedestalMaterialPath(const FHeroSpec& Spec, ES08TeamSlot Look) {
  return FString::Printf(TEXT("%s/Materials/MI_%s_%s_Base_%s"), *StageRoot(Spec), Spec.Key, Spec.Stage,
                         S08TeamSlotName(Look));
}

FString SkeletonPath(const FHeroSpec& Spec) {
  return FString::Printf(TEXT("/Game/PipelineCandidates/%s/Rig/SK_%s_Skeleton"), Spec.Key, Spec.Key);
}

FString ClipPath(const FHeroSpec& Spec, EClip Clip) {
  if (Clip == EClip::None) return FString();
  return FString::Printf(TEXT("/Game/PipelineCandidates/%s/H2Anim/AM_%s_%s"), Spec.Key, Spec.Key, ClipName(Clip));
}

float ExpectedClipSeconds(const FHeroSpec& Spec, EClip Clip) {
  switch (Clip) {
    case EClip::Idle: return Spec.IdleSeconds;
    case EClip::LungeAttack: return 14.0f / 24.0f;
    case EClip::HitReact: return 10.0f / 24.0f;
    case EClip::DeathSettle: return 21.0f / 24.0f;
    default: return 0.0f;
  }
}

float ProfileContactSeconds(const FHeroSpec& Spec) { return static_cast<float>(Spec.LungeContactFrame) / ClipFps; }

float NotifyContactSeconds(const UAnimSequenceBase* Anim) {
  if (!Anim) return -1.0f;
  const FName Name(ContactNotifyName);
  for (const FAnimNotifyEvent& Event : Anim->Notifies) {
    if (Event.NotifyName == Name) return Event.GetTriggerTime();
  }
  return -1.0f;
}

float ContactSeconds(const FHeroSpec& Spec, const UAnimSequenceBase* LungeAttack) {
  const float FromNotify = NotifyContactSeconds(LungeAttack);
  return FromNotify >= 0.0f ? FromNotify : ProfileContactSeconds(Spec);
}

EDissolveStyle DissolveStyle() {
  return DecideDissolveStyle(FParse::Param(FCommandLine::Get(), DissolveAshFlagName), S08IconMotion::IsReducedMotion());
}

const TCHAR* DissolveStyleName(EDissolveStyle Style) { return Style == EDissolveStyle::Ash ? TEXT("ash") : TEXT("fade"); }

FString DissolveMaterialPath(const FHeroSpec& Spec, ES08TeamSlot Look) {
  return FString::Printf(TEXT("/Game/UM/Materials/v2/Dissolve/MI_%s_%s_%s_Dissolve"), Spec.Key, Spec.Stage,
                         S08TeamSlotName(Look));
}

float DissolveProgressAt(const FDeathPlan& Plan, float SecondsSinceFall) {
  const float T = SecondsSinceFall - Plan.DissolveStartSeconds();
  if (T <= 0.0f) return 0.0f;
  // A float sum of the stages must not leave the figure at 0.99999 forever: the last microseconds count as gone.
  if (Plan.DissolveSeconds <= 0.0f || T >= Plan.DissolveSeconds - KINDA_SMALL_NUMBER) return 1.0f;
  return FMath::Clamp(T / Plan.DissolveSeconds, 0.0f, 1.0f);
}

float BenchDissolveProgress() {
  const TCHAR* Cmd = FCommandLine::Get();
  float Progress = -1.0f;
  if (!FParse::Param(Cmd, TEXT("Bench")) || !FParse::Value(Cmd, BenchDissolveParamName, Progress)) return -1.0f;
  return Progress < 0.0f ? -1.0f : FMath::Min(Progress, 1.0f);
}

bool ParseBenchClipPoses(const FString& Text, TArray<FBenchClipPoseSpec>& Out, FString& OutError) {
  Out.Reset();
  OutError.Reset();
  const FString Trimmed = Text.TrimStartAndEnd();
  if (Trimmed.IsEmpty()) {
    OutError = TEXT("empty list");
    return false;
  }
  TArray<FString> Blocks;
  Trimmed.ParseIntoArray(Blocks, TEXT(";"), true);
  for (const FString& Block : Blocks) {
    const int32 At = Block.Find(TEXT("@"));
    if (At <= 0 || At == Block.Len() - 1) {
      OutError = FString::Printf(TEXT("'%s' is not <Clip>@<frames>"), *Block);
      Out.Reset();
      return false;
    }
    const FString ClipName = Block.Left(At).TrimStartAndEnd();
    EClip Clip = EClip::None;
    for (const EClip Candidate : {EClip::Idle, EClip::LungeAttack, EClip::HitReact, EClip::DeathSettle}) {
      if (ClipName.Equals(S08HeroesV2::ClipName(Candidate), ESearchCase::IgnoreCase)) Clip = Candidate;
    }
    if (Clip == EClip::None) {
      OutError = FString::Printf(TEXT("unknown clip '%s'"), *ClipName);
      Out.Reset();
      return false;
    }
    TArray<FString> Frames;
    Block.Mid(At + 1).ParseIntoArray(Frames, TEXT(","), true);
    if (Frames.Num() == 0) {
      OutError = FString::Printf(TEXT("clip '%s' has no frames"), *ClipName);
      Out.Reset();
      return false;
    }
    for (const FString& Frame : Frames) {
      FBenchClipPoseSpec Spec;
      Spec.Clip = Clip;
      const FString Token = Frame.TrimStartAndEnd();
      bool bOk = false;
      if (Token.StartsWith(TEXT("q"), ESearchCase::IgnoreCase) && Token.Len() > 1) {
        Spec.bQuarter = true;
        Spec.Value = FCString::Atoi(*Token.Mid(1));
        bOk = Token.Mid(1).IsNumeric() && Spec.Value >= 0 && Spec.Value <= 100;
      } else {
        Spec.bQuarter = false;
        Spec.Value = FCString::Atoi(*Token);
        bOk = Token.IsNumeric() && Spec.Value >= 0;
      }
      if (!bOk) {
        OutError = FString::Printf(TEXT("bad frame '%s' of clip '%s'"), *Token, *ClipName);
        Out.Reset();
        return false;
      }
      Out.Add(Spec);
    }
  }
  return Out.Num() > 0;
}

double BenchClipPoseSeconds(const FBenchClipPoseSpec& Spec, double ClipSeconds) {
  const double Len = FMath::Max(0.0, ClipSeconds);
  return FMath::Clamp(Spec.bQuarter ? Len * Spec.Value / 100.0 : Spec.Value / ClipFps, 0.0, Len);
}

int32 HarpyNumber(const FS08BoardFighter& Fighter) {
  int32 Number = 1;
  for (int32 I = Fighter.Label.Len() - 1; I >= 0; --I) {
    if (FChar::IsDigit(Fighter.Label[I])) {
      Number = FChar::ConvertCharDigitToInt(Fighter.Label[I]);
      break;
    }
  }
  return FMath::Clamp(Number, 1, 3);
}

FString BaseDigitMaterialPath() { return TEXT("/Game/UM/Materials/v2/M_UM_BaseDigit"); }

FString BaseDigitTextMaterialPath() { return TEXT("/Game/UM/Materials/v2/M_UM_BaseDigitText"); }

FString BaseDigitFontPath() { return TEXT("/Game/UM/Fonts/F_UM_RobotoBoldCondensed_Offline"); }

float BaseDigitTurnDeg() {
  float Turn = BaseDigitSideTurnDeg;
  if (FParse::Value(FCommandLine::Get(), BaseDigitTurnParamName, Turn)) Turn = FMath::Clamp(Turn, -90.0f, 90.0f);
  return Turn;
}

FBaseDigitPlacement BaseDigitPlacement(const FVector& PedestalCenter, float TopZ, float TopRadiusUU,
                                       const FVector& CameraPos, double RestYawDeg, float TurnDeg) {
  FBaseDigitPlacement Out;
  const float R = FMath::Max(0.0f, TopRadiusUU);
  Out.DiscDiameterUU = BaseDigitDiscOfTopDiameter * 2.0f * R;
  // The camera axis (pedestal -> camera, XY) and the side away from the figure's rest offset.
  FVector Axis(CameraPos.X - PedestalCenter.X, CameraPos.Y - PedestalCenter.Y, 0.0);
  if (!Axis.Normalize()) Axis = FVector(0.0, 1.0, 0.0);
  const double AxisYaw = FMath::RadiansToDegrees(FMath::Atan2(Axis.Y, Axis.X));
  const double Off = FMath::FindDeltaAngleDegrees(AxisYaw, RestYawDeg);
  Out.Side = Off >= 0.0 ? -1 : 1;
  const double PlaceYaw = FMath::DegreesToRadians(AxisYaw + Out.Side * TurnDeg);
  const FVector Dir(FMath::Cos(PlaceYaw), FMath::Sin(PlaceYaw), 0.0);
  const FVector Centre2D(PedestalCenter.X, PedestalCenter.Y, 0.0);
  const FVector OnTop = Centre2D + Dir * (BaseDigitCentreOfRadius * R);
  Out.DiscCenter = FVector(OnTop.X, OnTop.Y, TopZ + BaseDigitDiscLiftUU + 0.5f * BaseDigitDiscThicknessUU);
  const float Xy = Out.DiscDiameterUU / 100.0f;  // the engine cylinder: 100 uu across, 100 uu tall
  Out.DiscScale = FVector(Xy, Xy, BaseDigitDiscThicknessUU / 100.0f);
  // The digit: flat (its normal +Z), the glyph top away from the camera so it reads upright from the camera side,
  // centred on the disc, lifted clear of the plate's top (no z-fight).
  const float Em = BaseDigitEmOfDisc * Out.DiscDiameterUU;
  Out.TextWorldSizeUU = Em * RobotoCellPerEm;
  Out.CapUU = Em * RobotoDigitPerEm;
  Out.TextRotation = FRotationMatrix::MakeFromXZ(FVector::UpVector, -Axis).Rotator();
  Out.TextLocation = FVector(OnTop.X, OnTop.Y, TopZ + BaseDigitDiscLiftUU + BaseDigitDiscThicknessUU + BaseDigitTextLiftUU);
  return Out;
}

void SetDissolve(UPrimitiveComponent* Body, UPrimitiveComponent* Pedestal, float Progress, EDissolveStyle Style) {
  const float P = FMath::Clamp(Progress, 0.0f, 1.0f);
  if (Body) {
    Body->SetCustomPrimitiveDataFloat(DissolveCpdIndex, P);
    Body->SetCustomPrimitiveDataFloat(DissolveStyleCpdIndex, static_cast<float>(static_cast<uint8>(Style)));
  }
  if (Pedestal) Pedestal->SetCustomPrimitiveDataFloat(PedestalFadeCpdIndex, P);
}

}  // namespace S08HeroesV2
