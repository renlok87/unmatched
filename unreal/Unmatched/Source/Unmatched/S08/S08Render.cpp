#include "S08Render.h"

#include "Components/PrimitiveComponent.h"
#include "DynamicRHI.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/GameUserSettings.h"
#include "HAL/IConsoleManager.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "RHIFeatureLevel.h"
#include "RHIShaderPlatform.h"
#include "RHIStrings.h"
#include "RenderUtils.h"
#include "Scalability.h"

// ---------------------------------------------------------------- sha256
namespace {
constexpr uint32 K256[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};

inline uint32 Rotr(uint32 X, uint32 N) { return (X >> N) | (X << (32 - N)); }

void Sha256Block(uint32 H[8], const uint8* P) {
  uint32 W[64];
  for (int32 I = 0; I < 16; ++I) {
    W[I] = (uint32(P[4 * I]) << 24) | (uint32(P[4 * I + 1]) << 16) | (uint32(P[4 * I + 2]) << 8) | uint32(P[4 * I + 3]);
  }
  for (int32 I = 16; I < 64; ++I) {
    const uint32 S0 = Rotr(W[I - 15], 7) ^ Rotr(W[I - 15], 18) ^ (W[I - 15] >> 3);
    const uint32 S1 = Rotr(W[I - 2], 17) ^ Rotr(W[I - 2], 19) ^ (W[I - 2] >> 10);
    W[I] = W[I - 16] + S0 + W[I - 7] + S1;
  }
  uint32 A = H[0], B = H[1], C = H[2], D = H[3], E = H[4], F = H[5], G = H[6], Hh = H[7];
  for (int32 I = 0; I < 64; ++I) {
    const uint32 S1 = Rotr(E, 6) ^ Rotr(E, 11) ^ Rotr(E, 25);
    const uint32 Ch = (E & F) ^ (~E & G);
    const uint32 T1 = Hh + S1 + Ch + K256[I] + W[I];
    const uint32 S0 = Rotr(A, 2) ^ Rotr(A, 13) ^ Rotr(A, 22);
    const uint32 Maj = (A & B) ^ (A & C) ^ (B & C);
    const uint32 T2 = S0 + Maj;
    Hh = G; G = F; F = E; E = D + T1; D = C; C = B; B = A; A = T1 + T2;
  }
  H[0] += A; H[1] += B; H[2] += C; H[3] += D; H[4] += E; H[5] += F; H[6] += G; H[7] += Hh;
}

int32 Cvar(const TCHAR* Name, int32 Default = -1) {
  const IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name);
  return V ? V->GetInt() : Default;
}

float CvarF(const TCHAR* Name, float Default = -1.0f) {
  const IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name);
  return V ? V->GetFloat() : Default;
}

const TCHAR* AaName(int32 Method) {
  switch (Method) {
    case 0: return TEXT("none");
    case 1: return TEXT("FXAA");
    case 2: return TEXT("TAA");
    case 3: return TEXT("MSAA");
    case 4: return TEXT("TSR");
    case 5: return TEXT("SMAA");
    default: return TEXT("unknown");
  }
}

FString PresetName(const Scalability::FQualityLevels& Q) {
  const int32 Groups[] = {Q.ViewDistanceQuality, Q.AntiAliasingQuality, Q.ShadowQuality,
                          Q.GlobalIlluminationQuality, Q.ReflectionQuality, Q.PostProcessQuality,
                          Q.TextureQuality, Q.EffectsQuality, Q.FoliageQuality, Q.ShadingQuality,
                          Q.LandscapeQuality};
  for (const int32 G : Groups) {
    if (G != Groups[0]) return TEXT("custom");
  }
  static const TCHAR* Names[] = {TEXT("Low"), TEXT("Medium"), TEXT("High"), TEXT("Epic"), TEXT("Cinematic")};
  return Groups[0] >= 0 && Groups[0] <= 4 ? FString(Names[Groups[0]]) : TEXT("custom");
}

struct FS08RenderState {
  FString Rhi;
  FString FeatureLevel;
  FString ShaderPlatform;
  bool bLumenPlatform = false;
  int32 GiMethod = -1;
  int32 ReflMethod = -1;
  FString Gi;
  FString Refl;
  FString Shadows;
  int32 VsmEnable = -1;
  Scalability::FQualityLevels Q;
  FString Preset;
  float ScreenPct = -1.0f;
  int32 ScreenPctMode = -1;
  int32 AaMethod = -1;
  float TMaxFps = -1.0f;
  int32 VSync = -1;
  float FrameRateLimit = -1.0f;
  int32 Substrate = -1;
  int32 Nanite = -1;
  int32 DistanceFields = -1;
  FIntPoint Viewport = FIntPoint::ZeroValue;
};

FS08RenderState ReadState() {
  FS08RenderState S;
  S.Rhi = GDynamicRHI ? FString(GDynamicRHI->GetName()) : FString(TEXT("none"));
  GetFeatureLevelName(GMaxRHIFeatureLevel, S.FeatureLevel);
  S.ShaderPlatform = LegacyShaderPlatformToShaderFormat(GMaxRHIShaderPlatform).ToString();
  S.bLumenPlatform = DoesPlatformSupportLumenGI(GMaxRHIShaderPlatform);
  S.GiMethod = Cvar(TEXT("r.DynamicGlobalIlluminationMethod"));
  S.ReflMethod = Cvar(TEXT("r.ReflectionMethod"));
  const bool bLumenGi = S.bLumenPlatform && S.GiMethod == 1 && Cvar(TEXT("r.Lumen.DiffuseIndirect.Allow"), 1) != 0;
  const bool bLumenRefl = S.bLumenPlatform && S.ReflMethod == 1 && Cvar(TEXT("r.Lumen.Reflections.Allow"), 1) != 0;
  S.Gi = bLumenGi ? TEXT("lumen")
       : S.GiMethod == 1 ? (S.bLumenPlatform ? TEXT("lumen-disallowed") : TEXT("lumen-unsupported"))
       : S.GiMethod == 2 ? TEXT("ssgi") : TEXT("none");
  S.Refl = bLumenRefl ? TEXT("lumen")
         : S.ReflMethod == 1 ? (S.bLumenPlatform ? TEXT("lumen-disallowed") : TEXT("lumen-unsupported"))
         : S.ReflMethod == 2 ? TEXT("ssr") : TEXT("none");
  S.VsmEnable = Cvar(TEXT("r.Shadow.Virtual.Enable"));
  S.Shadows = (S.VsmEnable > 0 && DoesPlatformSupportVirtualShadowMaps(GMaxRHIShaderPlatform)) ? TEXT("vsm") : TEXT("csm");
  S.Q = Scalability::GetQualityLevels();
  S.Preset = PresetName(S.Q);
  S.ScreenPct = CvarF(TEXT("r.ScreenPercentage"));
  S.ScreenPctMode = Cvar(TEXT("r.ScreenPercentage.Default.Desktop.Mode"));
  S.AaMethod = Cvar(TEXT("r.AntiAliasingMethod"));
  S.TMaxFps = CvarF(TEXT("t.MaxFPS"));
  S.VSync = Cvar(TEXT("r.VSync"));
  const UGameUserSettings* Settings = GEngine ? GEngine->GetGameUserSettings() : nullptr;
  S.FrameRateLimit = Settings ? Settings->GetFrameRateLimit() : -1.0f;
  S.Substrate = Cvar(TEXT("r.Substrate"));
  S.Nanite = Cvar(TEXT("r.Nanite"));
  S.DistanceFields = Cvar(TEXT("r.GenerateMeshDistanceFields"));
  if (GEngine && GEngine->GameViewport) {
    FVector2D Size(0.0, 0.0);
    GEngine->GameViewport->GetViewportSize(Size);
    S.Viewport = FIntPoint(static_cast<int32>(Size.X), static_cast<int32>(Size.Y));
  }
  return S;
}

bool IsReference(const FS08RenderState& S, const FS08AppliedRender& A, TArray<FString>& Why) {
  if (S.Rhi != TEXT("D3D12")) Why.Add(TEXT("rhi"));
  if (S.FeatureLevel != TEXT("SM6")) Why.Add(TEXT("featureLevel"));
  if (S.Gi != TEXT("lumen")) Why.Add(TEXT("gi"));
  if (S.Refl != TEXT("lumen")) Why.Add(TEXT("reflections"));
  const Scalability::FQualityLevels& Q = S.Q;
  if (Q.ViewDistanceQuality != 2 || Q.AntiAliasingQuality != 2 || Q.ShadowQuality != 2 ||
      Q.GlobalIlluminationQuality != 2 || Q.ReflectionQuality != 2 || Q.PostProcessQuality != 2 ||
      Q.TextureQuality != 2 || Q.EffectsQuality != 2 || Q.FoliageQuality != 2 || Q.ShadingQuality != 2) {
    Why.Add(TEXT("scalability"));
  }
  if (!FMath::IsNearlyEqual(S.ScreenPct, 100.0f)) Why.Add(TEXT("screenPercentage"));
  if (!A.bArt) Why.Add(TEXT("noArtProfile"));
  if (!A.bExposure || !FMath::IsNearlyEqual(A.ExposureMin, A.ExposureMax)) Why.Add(TEXT("exposure"));
  if (A.PointUnits != TEXT("candelas")) Why.Add(TEXT("lightUnits"));
  if (A.ProfilesSource != TEXT("pak")) Why.Add(TEXT("profilesSource"));
  if (S08LegacyRender()) Why.Add(TEXT("legacyRender"));
  return Why.Num() == 0;
}
} // namespace

FString S08Sha256Hex(const uint8* Data, int64 Size) {
  uint32 H[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
  int64 Off = 0;
  for (; Off + 64 <= Size; Off += 64) Sha256Block(H, Data + Off);
  uint8 Tail[128];
  FMemory::Memzero(Tail, sizeof(Tail));
  const int64 Rest = Size - Off;
  if (Rest > 0) FMemory::Memcpy(Tail, Data + Off, Rest);
  Tail[Rest] = 0x80;
  const int32 TailBlocks = Rest + 1 + 8 <= 64 ? 1 : 2;
  const uint64 Bits = static_cast<uint64>(Size) * 8ull;
  for (int32 I = 0; I < 8; ++I) {
    Tail[TailBlocks * 64 - 1 - I] = static_cast<uint8>(Bits >> (8 * I));
  }
  for (int32 B = 0; B < TailBlocks; ++B) Sha256Block(H, Tail + 64 * B);
  FString Out;
  for (const uint32 Word : H) Out += FString::Printf(TEXT("%08x"), Word);
  return Out;
}

bool S08LegacyRender() {
  static const bool bLegacy = FParse::Param(FCommandLine::Get(), TEXT("S08LegacyRender"));
  return bLegacy;
}

UMaterialInterface* S08GameLayerMaterial() {
  if (!S08LegacyRender()) {
    if (UMaterialInterface* Unlit = LoadObject<UMaterialInterface>(
            nullptr, TEXT("/Game/S08/Render/M_S08_GameLayerUnlit.M_S08_GameLayerUnlit"), nullptr, LOAD_NoWarn)) {
      return Unlit;
    }
  }
  return LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/S08/M_S08_Solid.M_S08_Solid"));
}

bool S08GameLayerIsUnlit() {
  const UMaterialInterface* M = S08GameLayerMaterial();
  return M && M->GetName() == TEXT("M_S08_GameLayerUnlit");
}

void S08ApplyGameLayerPrimitive(UPrimitiveComponent* Component) {
  if (!Component || S08LegacyRender()) return;
  Component->SetCastShadow(false);
  Component->SetAffectDynamicIndirectLighting(false);
  Component->SetAffectDistanceFieldLighting(false);
}

FString S08RenderFingerprint(const UWorld* World, const FS08AppliedRender& A, const TCHAR* Tag) {
  const FS08RenderState S = ReadState();
  TArray<FString> Why;
  const bool bReference = IsReference(S, A, Why);
  const Scalability::FQualityLevels& Q = S.Q;
  FString Line = FString::Printf(
      TEXT("RENDER tag=%s rhi=%s featureLevel=%s shaderPlatform=%s lumenPlatform=%d gi=%s giMethod=%d refl=%s reflMethod=%d ")
      TEXT("shadows=%s vsmEnable=%d sg.res=%.0f sg.view=%d sg.aa=%d sg.shadow=%d sg.gi=%d sg.refl=%d sg.pp=%d sg.tex=%d ")
      TEXT("sg.fx=%d sg.foliage=%d sg.shading=%d sg.landscape=%d preset=%s screenPct=%.1f screenPctMode=%d aa=%s aaMethod=%d "),
      Tag, *S.Rhi, *S.FeatureLevel, *S.ShaderPlatform, S.bLumenPlatform ? 1 : 0, *S.Gi, S.GiMethod, *S.Refl, S.ReflMethod,
      *S.Shadows, S.VsmEnable, Q.ResolutionQuality, Q.ViewDistanceQuality, Q.AntiAliasingQuality, Q.ShadowQuality,
      Q.GlobalIlluminationQuality, Q.ReflectionQuality, Q.PostProcessQuality, Q.TextureQuality, Q.EffectsQuality,
      Q.FoliageQuality, Q.ShadingQuality, Q.LandscapeQuality, *S.Preset, S.ScreenPct, S.ScreenPctMode, AaName(S.AaMethod),
      S.AaMethod);
  Line += FString::Printf(
      TEXT("exposure=%s expMin=%.5f expMax=%.5f expBias=%.3f ev100=%.2f lightUnits=%s sky=%d skyIntensity=%.3f ")
      TEXT("keyShadow=%s shadowCasters=%d profile=%s profilesSha256=%s profilesSource=%s legacyRender=%d gameLayer=%s ")
      TEXT("tMaxFPS=%.1f vsync=%d frameRateLimit=%.1f substrate=%d nanite=%d meshDF=%d viewport=%dx%d reference=%d"),
      A.bExposure ? TEXT("fixed-histogram") : TEXT("engine-default"), A.ExposureMin, A.ExposureMax, A.ExposureBias,
      A.Ev100, A.PointUnits.IsEmpty() ? TEXT("-") : *A.PointUnits, A.bSky ? 1 : 0, A.SkyIntensity,
      A.KeyShadow.IsEmpty() ? TEXT("-") : *A.KeyShadow, A.ShadowCasters,
      A.ProfileId.IsEmpty() ? TEXT("-") : *A.ProfileId, A.ProfilesSha256.IsEmpty() ? TEXT("-") : *A.ProfilesSha256,
      A.ProfilesSource.IsEmpty() ? TEXT("-") : *A.ProfilesSource, S08LegacyRender() ? 1 : 0,
      S08GameLayerIsUnlit() ? TEXT("unlit-eyeadaptinv") : TEXT("solid-legacy"), S.TMaxFps, S.VSync, S.FrameRateLimit,
      S.Substrate, S.Nanite, S.DistanceFields, S.Viewport.X, S.Viewport.Y, bReference ? 1 : 0);
  if (!bReference) Line += TEXT(" notReference=") + FString::Join(Why, TEXT(","));
  return Line;
}

bool S08RenderIsReference(const FS08AppliedRender& Applied, FString& OutWhyNot) {
  TArray<FString> Why;
  const bool bOk = IsReference(ReadState(), Applied, Why);
  OutWhyNot = FString::Join(Why, TEXT(","));
  return bOk;
}

FString S08ApplyRenderPresetFromCommandLine() {
  FString Preset;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08RenderPreset="), Preset) || Preset.IsEmpty()) return FString();
  int32 Level = -1;
  if (Preset.Equals(TEXT("Low"), ESearchCase::IgnoreCase)) Level = 0;
  else if (Preset.Equals(TEXT("Medium"), ESearchCase::IgnoreCase)) Level = 1;
  else if (Preset.Equals(TEXT("High"), ESearchCase::IgnoreCase)) Level = 2;
  else if (Preset.Equals(TEXT("Epic"), ESearchCase::IgnoreCase)) Level = 3;
  if (Level < 0) return FString::Printf(TEXT("invalid:%s"), *Preset);
  Scalability::FQualityLevels Q = Scalability::GetQualityLevels();
  Q.SetFromSingleQualityLevel(Level);
  Q.ResolutionQuality = 100.0f;  // r.ScreenPercentage stays pinned at 100 (DefaultEngine.ini)
  Scalability::SetQualityLevels(Q, true);
  return PresetName(Scalability::GetQualityLevels());
}
