// VS-2 HB-12: the software cursors of the UMG HUD - see UmCursor.h.
#include "UmCursor.h"

#include "Blueprint/WidgetTree.h"
#include "Components/Image.h"
#include "Components/SizeBox.h"
#include "Components/SizeBoxSlot.h"
#include "Dom/JsonObject.h"
#include "Engine/GameInstance.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Misc/ScopeLock.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

const TCHAR* const UUmCursor::WidgetBlueprintPath = TEXT("/Game/S08/UI/Common/WBP_UmCursor");

namespace {
/** Start (ms) of each frame of the busy loop: the 8 frames of cursor-busy (draw_icons.py CURSOR_BUSY_FRAMES - the
 *  hourglass of state-sent at 0, 183, 367, 550 ms, the 90° turn at 800, then 950, 1170, 1390; the loop is 1500 ms). */
constexpr double UmCursorBusyStartMs[UmCursor::BusyFrames] = {0.0, 183.0, 367.0, 550.0, 800.0, 950.0, 1170.0, 1390.0};
constexpr int32 UmCursorSizes[] = {24, 32, 48, 64};

struct FUmCursorHotspots {
  bool bLoaded = false;
  bool bOk = false;
  TMap<FString, FIntPoint> Spots;  // "<State>:<px>"
};

FCriticalSection GUmCursorHotspotsLock;
FUmCursorHotspots GUmCursorHotspots;

void UmCursorLoadHotspots(FUmCursorHotspots& Out) {
  Out = FUmCursorHotspots();
  Out.bLoaded = true;
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *UmCursor::HotspotsPath())) {
    UE_LOG(LogTemp, Error, TEXT("HUD-CURSOR hotspots missing: %s"), *UmCursor::HotspotsPath());
    return;
  }
  TSharedPtr<FJsonObject> Root;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
  const TSharedPtr<FJsonObject>* States = nullptr;
  if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid() || !Root->TryGetObjectField(TEXT("states"), States)) {
    UE_LOG(LogTemp, Error, TEXT("HUD-CURSOR hotspots unreadable: %s"), *UmCursor::HotspotsPath());
    return;
  }
  for (const auto& State : (*States)->Values) {
    const TSharedPtr<FJsonObject> Sizes = State.Value.IsValid() ? State.Value->AsObject() : nullptr;
    if (!Sizes.IsValid()) continue;
    for (const auto& Size : Sizes->Values) {
      const TArray<TSharedPtr<FJsonValue>>* Xy = nullptr;
      if (!Size.Value.IsValid() || !Size.Value->TryGetArray(Xy) || Xy->Num() != 2) continue;
      Out.Spots.Add(FString::Printf(TEXT("%s:%s"), *FString(State.Key), *FString(Size.Key)),
                    FIntPoint(FMath::RoundToInt((*Xy)[0]->AsNumber()), FMath::RoundToInt((*Xy)[1]->AsNumber())));
    }
  }
  Out.bOk = Out.Spots.Num() > 0;
}

template <typename T>
T* UmCursorMake(UWidgetTree& Tree, const TCHAR* Name) {
  return Tree.ConstructWidget<T>(T::StaticClass(), FName(Name));
}

template <typename T>
T* UmCursorFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}
}  // namespace

namespace UmCursor {
const TCHAR* Name(EUmCursor Shape) {
  switch (Shape) {
    case EUmCursor::Pointer: return TEXT("pointer");
    case EUmCursor::Denied: return TEXT("denied");
    case EUmCursor::Busy: return TEXT("busy");
    default: return TEXT("default");
  }
}

const TCHAR* StateName(EUmCursor Shape) {
  switch (Shape) {
    case EUmCursor::Pointer: return TEXT("Pointer");
    case EUmCursor::Denied: return TEXT("Denied");
    case EUmCursor::Busy: return TEXT("Busy");
    default: return TEXT("Default");
  }
}

const TArray<EMouseCursor::Type>& RegisteredTypes() {
  static const TArray<EMouseCursor::Type> Types = {EMouseCursor::Default, EMouseCursor::Hand, EMouseCursor::SlashedCircle};
  return Types;
}

EUmCursor BaseShape(EMouseCursor::Type Type) {
  switch (Type) {
    case EMouseCursor::Hand: return EUmCursor::Pointer;
    case EMouseCursor::SlashedCircle: return EUmCursor::Denied;
    default: return EUmCursor::Default;
  }
}

EUmCursor Resolve(EMouseCursor::Type Type, bool bBusy) { return bBusy ? EUmCursor::Busy : BaseShape(Type); }

EMouseCursor::Type BoardCursor(bool bOwnFighter, bool bLitCell) {
  return bOwnFighter || bLitCell ? EMouseCursor::Hand : EMouseCursor::Default;
}

int32 SizePx(float PxPerSu) {
  const float Want = 32.0f * FMath::Max(PxPerSu, 0.01f) - 0.01f;
  for (const int32 Px : UmCursorSizes) {
    if (Px >= Want) return Px;
  }
  return UmCursorSizes[UE_ARRAY_COUNT(UmCursorSizes) - 1];
}

FString TexturePath(EUmCursor Shape, int32 Px, int32 Frame) {
  const TCHAR* Suffix = Px == 24 ? TEXT("_24") : Px == 48 ? TEXT("_48") : Px == 64 ? TEXT("_x2") : TEXT("");
  const FString Name = Shape == EUmCursor::Busy
                           ? FString::Printf(TEXT("T_Cursor_Busy_%02d%s"), FMath::Clamp(Frame, 0, BusyFrames - 1), Suffix)
                           : FString::Printf(TEXT("T_Cursor_%s%s"), StateName(Shape), Suffix);
  return FString::Printf(TEXT("/Game/S08/UI/Cursors/%s.%s"), *Name, *Name);
}

int32 BusyFrame(double MsSinceBusy, bool bReduced) {
  if (bReduced || MsSinceBusy <= 0.0) return 0;
  const double T = FMath::Fmod(MsSinceBusy, BusyCycleMs);
  int32 Frame = 0;
  for (int32 I = 0; I < BusyFrames; ++I) {
    if (T >= UmCursorBusyStartMs[I]) Frame = I;
  }
  return Frame;
}

FString HotspotsPath() { return FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("Cursors"), TEXT("S08CursorHotspots.json")); }

void ReloadHotspots() {
  FScopeLock Lock(&GUmCursorHotspotsLock);
  GUmCursorHotspots = FUmCursorHotspots();
}

bool Hotspot(EUmCursor Shape, int32 Px, FIntPoint& Out) {
  FScopeLock Lock(&GUmCursorHotspotsLock);
  if (!GUmCursorHotspots.bLoaded) UmCursorLoadHotspots(GUmCursorHotspots);
  const FIntPoint* Found = GUmCursorHotspots.Spots.Find(FString::Printf(TEXT("%s:%d"), StateName(Shape), Px));
  Out = Found ? *Found : FIntPoint::ZeroValue;
  return Found != nullptr;
}

FVector2D ImageOffset(int32 Px, const FIntPoint& Spot) { return FVector2D(Px - Spot.X, Px - Spot.Y); }

FString SystemShotLine(const TCHAR* Reason) {
  return FString::Printf(TEXT("HUD-CURSOR state=system impl=system reason=%s"), Reason ? Reason : TEXT("-"));
}
}  // namespace UmCursor

bool UUmCursor::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  USizeBox* BoxWidget = UmCursorMake<USizeBox>(Tree, TEXT("Box"));
  BoxWidget->SetWidthOverride(64.0f);
  BoxWidget->SetHeightOverride(64.0f);
  BoxWidget->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(BoxWidget, nullptr)) return Fail(TEXT("Box"));
  UImage* ImageWidget = UmCursorMake<UImage>(Tree, TEXT("Image"));
  ImageWidget->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(ImageWidget, BoxWidget)) return Fail(TEXT("Image"));
  if (USizeBoxSlot* BoxSlot = Cast<USizeBoxSlot>(ImageWidget->Slot)) {
    BoxSlot->SetHorizontalAlignment(HAlign_Left);
    BoxSlot->SetVerticalAlignment(VAlign_Top);
  }
  return true;
}

bool UUmCursor::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    FString Error;
    UWidgetTree* Tree = WidgetTree;
    bCodeDefaultTree = BuildDefaultTree(*Tree, [Tree](UWidget* Child, UPanelWidget* Parent) {
      if (!Parent) {
        Tree->RootWidget = Child;
        return true;
      }
      return Parent->AddChild(Child) != nullptr;
    }, &Error);
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("HUD-CURSOR default tree: %s"), *Error);
    Box = UmCursorFind<USizeBox>(Tree, TEXT("Box"));
    Image = UmCursorFind<UImage>(Tree, TEXT("Image"));
  }
  if (bFirst) SetVisibility(ESlateVisibility::HitTestInvisible);
  return bFirst;
}

UUmCursor* UUmCursor::Create(UObject* Outer, FString* OutSource) {
  if (!Outer) return nullptr;
  UClass* Class = UUmCursor::StaticClass();
  FString Source = TEXT("code-default");
  const FString Package = WidgetBlueprintPath;
  if (FPackageName::DoesPackageExist(Package)) {
    const FString ClassPath = Package + TEXT(".") + FPackageName::GetShortName(Package) + TEXT("_C");
    if (UClass* Wbp = LoadClass<UUmCursor>(nullptr, *ClassPath, nullptr, LOAD_NoWarn | LOAD_Quiet)) {
      Class = Wbp;
      Source = Package;
    }
  }
  UUmCursor* Made = nullptr;
  if (UWidget* AsWidget = Cast<UWidget>(Outer)) {
    Made = CreateWidget<UUmCursor>(AsWidget, Class);
  } else if (UWorld* World = Cast<UWorld>(Outer)) {
    Made = CreateWidget<UUmCursor>(World, Class);
  } else if (UGameInstance* Game = Cast<UGameInstance>(Outer)) {
    Made = CreateWidget<UUmCursor>(Game, Class);
  }
  if (OutSource) *OutSource = Source;
  return Made;
}

bool UUmCursor::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Box) Missing.Add(TEXT("Box"));
  if (!Image) Missing.Add(TEXT("Image"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmCursor::SetCursorType(EMouseCursor::Type InType) {
  if (CursorType == InType && bHasModel) return;
  CursorType = InType;
  if (bHasModel) Restyle();
}

void UUmCursor::ApplyModel(const FUmCursorModel& InModel) {
  if (bHasModel && InModel.bBusy == Model.bBusy && InModel.Px == Model.Px &&
      (!InModel.bBusy || InModel.BusyFrame == Model.BusyFrame)) {
    return;
  }
  Model = InModel;
  bHasModel = true;
  Restyle();
}

void UUmCursor::Restyle() {
  Shown = UmCursor::Resolve(CursorType, Model.bBusy);
  const int32 Px = Model.Px;
  if (!UmCursor::Hotspot(Shown, Px, HotspotPx)) HotspotPx = FIntPoint::ZeroValue;
  const FString Path = UmCursor::TexturePath(Shown, Px, Model.BusyFrame);
  UTexture2D* Loaded = LoadObject<UTexture2D>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
  if (!Loaded && Texture != Loaded) UE_LOG(LogTemp, Error, TEXT("HUD-CURSOR texture missing: %s"), *Path);
  Texture = Loaded;
  if (Box) {
    Box->SetWidthOverride(2.0f * Px);
    Box->SetHeightOverride(2.0f * Px);
  }
  if (Image) {
    if (Texture) {
      Image->SetBrushFromTexture(Texture, false);
      Image->SetVisibility(ESlateVisibility::HitTestInvisible);
    } else {
      Image->SetVisibility(ESlateVisibility::Collapsed);
    }
    FSlateBrush Brush = Image->GetBrush();
    Brush.ImageSize = FVector2D(Px, Px);
    Image->SetBrush(Brush);
    if (USizeBoxSlot* BoxSlot = Cast<USizeBoxSlot>(Image->Slot)) {
      const FVector2D Off = UmCursor::ImageOffset(Px, HotspotPx);
      BoxSlot->SetPadding(FMargin(Off.X, Off.Y, 0.0f, 0.0f));
      BoxSlot->SetHorizontalAlignment(HAlign_Left);
      BoxSlot->SetVerticalAlignment(VAlign_Top);
    }
  }
}

int32 UUmCursor::NativePaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
                             FSlateWindowElementList& OutDrawElements, int32 LayerId, const FWidgetStyle& InWidgetStyle,
                             bool bParentEnabled) const {
  LastPaintFrame = GFrameCounter;
  return Super::NativePaint(Args, AllottedGeometry, MyCullingRect, OutDrawElements, LayerId, InWidgetStyle, bParentEnabled);
}
