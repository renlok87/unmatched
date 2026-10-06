// VS-2 HB-12 tests (docs/game-design/visual/06-tasks/hud.csv HB-12; 04-hud-spec.md §3.2):
//   Unmatched.S08.Hud.Cursor.Map      EMouseCursor -> the drawn shape (Default -> arrow, Hand -> pointer, SlashedCircle ->
//                                     denied, anything else -> arrow), Busy overrides all three; the board cursor; the
//                                     size by DPI x UI scale (24 / 32 / 48 / 64); texture names; the busy loop; the widget
//                                     (code tree and WBP_UmCursor): 2 px box, image at the hot-spot offset.
//   Unmatched.S08.Hud.Cursor.Textures the 44 T_Cursor_* textures (4 shapes, 8 busy frames, 4 sizes): exact size, no mips;
//                                     the hot spot of Config/Cursors/S08CursorHotspots.json is an opaque pixel of its
//                                     texture (alpha >= 128), the pointer's at the fingertip (11, 2) u.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Cursor" <abs log>
#if WITH_AUTOMATION_TESTS

#include "UmCursor.h"
#include "Components/Image.h"
#include "Components/SizeBox.h"
#include "Components/SizeBoxSlot.h"
#include "Engine/Engine.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "Misc/PackageName.h"

namespace UmCursorTest {
struct FWorld {
  UWorld* World = nullptr;
  explicit FWorld(const TCHAR* Name) {
    World = UWorld::CreateWorld(EWorldType::Game, false, FName(Name));
    if (World) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
  }
  ~FWorld() {
    if (!World) return;
    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
  }
};

bool CheckWidget(FAutomationTestBase& T, UUmCursor* C, const TCHAR* What) {
  if (!T.TestNotNull(*FString::Printf(TEXT("%s widget"), What), C)) return false;
  FString Missing;
  T.TestTrue(FString::Printf(TEXT("%s every part bound (missing %s)"), What, *Missing), C->HasAllParts(&Missing));
  if (!C->Box || !C->Image) return false;
  C->SetCursorType(EMouseCursor::Hand);
  C->ApplyModel(FUmCursorModel{false, 32, 0});
  T.TestEqual(FString::Printf(TEXT("%s Hand draws the pointer"), What), static_cast<int32>(C->GetShown()),
              static_cast<int32>(EUmCursor::Pointer));
  T.TestEqual(FString::Printf(TEXT("%s pointer hot spot 32 px"), What), C->GetHotspot(), FIntPoint(11, 2));
  T.TestEqual(FString::Printf(TEXT("%s box 2 px wide (Slate centres the cursor widget)"), What),
              C->Box->GetWidthOverride(), 64.0f);
  T.TestEqual(FString::Printf(TEXT("%s box 2 px high"), What), C->Box->GetHeightOverride(), 64.0f);
  if (const USizeBoxSlot* BoxSlot = Cast<USizeBoxSlot>(C->Image->Slot)) {
    const FMargin P = BoxSlot->GetPadding();
    T.TestEqual(FString::Printf(TEXT("%s image left = px - hx (the hot spot on the centre)"), What), P.Left, 21.0f);
    T.TestEqual(FString::Printf(TEXT("%s image top = px - hy"), What), P.Top, 30.0f);
  } else {
    T.AddError(FString::Printf(TEXT("%s image not in a size box slot"), What));
  }
  T.TestEqual(FString::Printf(TEXT("%s image 32 px"), What), FVector2D(C->Image->GetBrush().ImageSize), FVector2D(32.0, 32.0));
  T.TestNotNull(FString::Printf(TEXT("%s T_Cursor_Pointer loaded"), What), C->GetTexture());
  C->ApplyModel(FUmCursorModel{true, 48, 3});
  T.TestEqual(FString::Printf(TEXT("%s busy overrides the pointer"), What), static_cast<int32>(C->GetShown()),
              static_cast<int32>(EUmCursor::Busy));
  T.TestEqual(FString::Printf(TEXT("%s busy hot spot = centre"), What), C->GetHotspot(), FIntPoint(24, 24));
  T.TestEqual(FString::Printf(TEXT("%s busy box 96"), What), C->Box->GetWidthOverride(), 96.0f);
  T.TestTrue(FString::Printf(TEXT("%s busy frame 3 texture"), What),
             C->GetTexture() && C->GetTexture()->GetName() == TEXT("T_Cursor_Busy_03_48"));
  C->SetCursorType(EMouseCursor::SlashedCircle);
  C->ApplyModel(FUmCursorModel{false, 24, 0});
  T.TestEqual(FString::Printf(TEXT("%s SlashedCircle draws denied"), What), static_cast<int32>(C->GetShown()),
              static_cast<int32>(EUmCursor::Denied));
  T.TestTrue(FString::Printf(TEXT("%s denied 24 texture"), What),
             C->GetTexture() && C->GetTexture()->GetName() == TEXT("T_Cursor_Denied_24"));
  return true;
}
}  // namespace UmCursorTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCursorMapTest, "Unmatched.S08.Hud.Cursor.Map",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCursorMapTest::RunTest(const FString&) {
  using namespace UmCursorTest;
  // the map of the three registered types; Busy overrides every one
  TestEqual(TEXT("three registered types"), UmCursor::RegisteredTypes().Num(), 3);
  struct FCase {
    EMouseCursor::Type Type;
    EUmCursor Shape;
  };
  for (const FCase& C : {FCase{EMouseCursor::Default, EUmCursor::Default}, FCase{EMouseCursor::Hand, EUmCursor::Pointer},
                         FCase{EMouseCursor::SlashedCircle, EUmCursor::Denied},
                         FCase{EMouseCursor::TextEditBeam, EUmCursor::Default}}) {
    TestEqual(FString::Printf(TEXT("type %d -> %s"), static_cast<int32>(C.Type), UmCursor::Name(C.Shape)),
              static_cast<int32>(UmCursor::Resolve(C.Type, false)), static_cast<int32>(C.Shape));
    TestEqual(FString::Printf(TEXT("type %d busy -> busy"), static_cast<int32>(C.Type)),
              static_cast<int32>(UmCursor::Resolve(C.Type, true)), static_cast<int32>(EUmCursor::Busy));
  }
  TestEqual(TEXT("board: own figure -> hand"), static_cast<int32>(UmCursor::BoardCursor(true, false)),
            static_cast<int32>(EMouseCursor::Hand));
  TestEqual(TEXT("board: lit cell -> hand"), static_cast<int32>(UmCursor::BoardCursor(false, true)),
            static_cast<int32>(EMouseCursor::Hand));
  TestEqual(TEXT("board: nothing -> default"), static_cast<int32>(UmCursor::BoardCursor(false, false)),
            static_cast<int32>(EMouseCursor::Default));
  // HB-23 / 04 §3.2: 32 px at 100 %, 24 at 720p, 48 at 150 % (and 1440p), 64 at 4K
  for (const TPair<float, int32>& S : {TPair<float, int32>(0.75f, 24), TPair<float, int32>(1.0f, 32),
                                       TPair<float, int32>(1.125f, 48), TPair<float, int32>(4.0f / 3.0f, 48),
                                       TPair<float, int32>(1.5f, 48), TPair<float, int32>(2.0f, 64),
                                       TPair<float, int32>(3.0f, 64)}) {
    TestEqual(FString::Printf(TEXT("size at %.3f px/su"), S.Key), UmCursor::SizePx(S.Key), S.Value);
  }
  TestEqual(TEXT("pointer 32 path"), UmCursor::TexturePath(EUmCursor::Pointer, 32),
            FString(TEXT("/Game/S08/UI/Cursors/T_Cursor_Pointer.T_Cursor_Pointer")));
  TestEqual(TEXT("denied 64 path"), UmCursor::TexturePath(EUmCursor::Denied, 64),
            FString(TEXT("/Game/S08/UI/Cursors/T_Cursor_Denied_x2.T_Cursor_Denied_x2")));
  TestEqual(TEXT("busy frame 3, 48 path"), UmCursor::TexturePath(EUmCursor::Busy, 48, 3),
            FString(TEXT("/Game/S08/UI/Cursors/T_Cursor_Busy_03_48.T_Cursor_Busy_03_48")));
  // the busy loop: 8 frames, 1500 ms, f04 (the turn) from 800 ms; reduced motion = frame 0
  for (const TPair<double, int32>& F : {TPair<double, int32>(0.0, 0), TPair<double, int32>(200.0, 1),
                                        TPair<double, int32>(799.0, 3), TPair<double, int32>(800.0, 4),
                                        TPair<double, int32>(1499.0, 7), TPair<double, int32>(1500.0, 0),
                                        TPair<double, int32>(2300.0, 4)}) {
    TestEqual(FString::Printf(TEXT("busy frame at %.0f ms"), F.Key), UmCursor::BusyFrame(F.Key, false), F.Value);
  }
  TestEqual(TEXT("reduced motion: static frame"), UmCursor::BusyFrame(900.0, true), 0);
  // the board half re-picks only on a move or after RepickFrames
  FUmBoardCursor Board;
  TestTrue(TEXT("board cursor: first pick"), Board.NeedsPick(FVector2D(10, 10), 1));
  TestEqual(TEXT("board cursor stored"), static_cast<int32>(Board.Store(FVector2D(10, 10), 1, true, false)),
            static_cast<int32>(EMouseCursor::Hand));
  TestFalse(TEXT("board cursor: still pointer, next frame"), Board.NeedsPick(FVector2D(10, 10), 2));
  TestTrue(TEXT("board cursor: moved"), Board.NeedsPick(FVector2D(12, 10), 2));
  TestTrue(TEXT("board cursor: after RepickFrames"), Board.NeedsPick(FVector2D(10, 10), 1 + FUmBoardCursor::RepickFrames));
  // the widget: code default tree and the WBP
  FWorld W(TEXT("UmCursorMap"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmCursor* Code = CreateWidget<UUmCursor>(W.World, UUmCursor::StaticClass());
  if (Code) TestTrue(TEXT("code default tree"), Code->UsesCodeDefaultTree());
  CheckWidget(*this, Code, TEXT("code"));
  const FString Package(UUmCursor::WidgetBlueprintPath);
  if (FPackageName::DoesPackageExist(Package)) {
    UClass* Class = LoadClass<UUmCursor>(nullptr, *(Package + TEXT(".") + FPackageName::GetShortName(Package) + TEXT("_C")));
    CheckWidget(*this, Class ? CreateWidget<UUmCursor>(W.World, Class) : nullptr, TEXT("WBP_UmCursor"));
  } else {
    AddError(TEXT("WBP_UmCursor missing - run tools/s08/hud_contract/ue_author_um_hud.py"));
  }
  TestTrue(TEXT("rollback line"), UmCursor::SystemShotLine(TEXT("-S08SlateHud=cursor")).StartsWith(TEXT("HUD-CURSOR state=system")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCursorTexturesTest, "Unmatched.S08.Hud.Cursor.Textures",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCursorTexturesTest::RunTest(const FString&) {
  UmCursor::ReloadHotspots();
  int32 Checked = 0;
  for (const EUmCursor Shape : {EUmCursor::Default, EUmCursor::Pointer, EUmCursor::Denied, EUmCursor::Busy}) {
    const int32 Frames = Shape == EUmCursor::Busy ? UmCursor::BusyFrames : 1;
    for (int32 Frame = 0; Frame < Frames; ++Frame) {
      for (const int32 Px : {24, 32, 48, 64}) {
        const FString Path = UmCursor::TexturePath(Shape, Px, Frame);
        UTexture2D* T = LoadObject<UTexture2D>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
        if (!TestNotNull(*FString::Printf(TEXT("%s exists"), *Path), T)) continue;
        FIntPoint Spot;
        TestTrue(*FString::Printf(TEXT("%s hot spot known"), *Path), UmCursor::Hotspot(Shape, Px, Spot));
#if WITH_EDITORONLY_DATA
        // the imported size: -nullrhi builds no platform data, GetSizeX() would be 0
        TestEqual(*FString::Printf(TEXT("%s width"), *Path), static_cast<int32>(T->Source.GetSizeX()), Px);
        TestEqual(*FString::Printf(TEXT("%s height"), *Path), static_cast<int32>(T->Source.GetSizeY()), Px);
        TestEqual(*FString::Printf(TEXT("%s no mips"), *Path), static_cast<int32>(T->MipGenSettings),
                  static_cast<int32>(TMGS_NoMipmaps));
        TArray64<uint8> Mip;
        if (T->Source.IsValid() && T->Source.GetFormat() == TSF_BGRA8 && T->Source.GetMipData(Mip, 0) &&
            Mip.Num() >= static_cast<int64>(Px) * Px * 4) {
          const uint8 Alpha = Mip[(static_cast<int64>(Spot.Y) * Px + Spot.X) * 4 + 3];
          TestTrue(*FString::Printf(TEXT("%s hot spot (%d,%d) opaque (alpha %d)"), *Path, Spot.X, Spot.Y, Alpha), Alpha >= 128);
        } else {
          AddError(FString::Printf(TEXT("%s: no BGRA8 source to check the hot spot"), *Path));
        }
#endif
        ++Checked;
      }
    }
  }
  TestEqual(TEXT("44 cursor textures"), Checked, 44);
  FIntPoint Spot;
  for (const TPair<int32, FIntPoint>& P : {TPair<int32, FIntPoint>(24, FIntPoint(8, 2)), TPair<int32, FIntPoint>(32, FIntPoint(11, 2)),
                                           TPair<int32, FIntPoint>(48, FIntPoint(17, 3)), TPair<int32, FIntPoint>(64, FIntPoint(22, 4))}) {
    UmCursor::Hotspot(EUmCursor::Pointer, P.Key, Spot);
    TestEqual(*FString::Printf(TEXT("pointer fingertip at %d px"), P.Key), Spot, P.Value);
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
