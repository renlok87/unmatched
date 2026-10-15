// Interactive dev loop (user request 2026-10-15: «Я не хочу полностью пересобирать игру каждый раз во время фикса.
// Запусти ее так чтобы ты мог интерактивно ее фиксить»). Driver: tools/dev/devexec.py, doc: tools/dev/DEV-LOOP.md.
//
// -DevExec=<dir> turns any client (uncooked `UnrealEditor.exe <uproject> -game -LiveCoding` or packaged) into a file
// command server: the game thread polls <dir>/cmd-<seq>.txt every 0.1 s, runs its lines in order and answers with
// <dir>/done-<seq>.json {seq, ok, ms, lines: [{cmd, ok, out}]}. No sockets, no OS input: clicks, keys and text are
// synthetic Slate events routed to the game window, so the user's mouse and keyboard stay untouched and the window may
// sit behind other windows. Without the flag nothing runs (no ticker, no files).
//
// Line commands (anything else is a console command run through GEngine->Exec, e.g. `LiveCoding.Compile`,
// `r.SetRes 1280x720w`, `stat fps`):
//   click <x> <y> [left|right]   viewport pixels (the PNG of `shot` has the same pixel grid); release 2 frames later
//   down|up <x> <y> [left|right] one half of a click
//   move <x> <y>                 hover
//   drag <x0> <y0> <x1> <y1>     left button drag in 8 steps
//   wheel <x> <y> <delta>
//   key <Key> [ctrl|shift|alt]   FKey name (Enter, Escape, M, A, SpaceBar, F10...)
//   type <text>                  character events into the focused widget
//   wait <seconds>               blocks the following lines of this command file
//   shot <png path>              viewport + Slate UI (FScreenshotRequest bShowUI), waits until the file is written
//   res <W>x<H>[w|f|wf]          r.SetRes, then waits 0.5 s for the swap chain
//   cursor os|faux               real mouse back / the driver's faux cursor (input lines switch to faux)
//   pick <x> <y>                 the Slate path under the point, leaf first: widget (UObject name) and [cursor] if set
//   info                         viewport size, DPI scale, window position, world, game mode
#include "S08DevExec.h"

#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/GameModeBase.h"
#include "HAL/FileManager.h"
#include "ImageUtils.h"
#include "Misc/CommandLine.h"
#include "Misc/DelayedAutoRegister.h"
#include "Misc/FileHelper.h"
#include "Misc/OutputDeviceRedirector.h"
#include "Misc/Paths.h"
#include "Misc/Parse.h"
#include "Serialization/JsonSerializer.h"
#include "Types/ReflectionMetadata.h"
#include "Serialization/JsonWriter.h"
#include "UnrealClient.h"
#include "Widgets/SViewport.h"
#include "Widgets/SWindow.h"

DEFINE_LOG_CATEGORY_STATIC(LogS08DevExec, Log, All);

namespace {

class FDevOutput final : public FOutputDevice {
 public:
  FString Text;
  virtual void Serialize(const TCHAR* V, ELogVerbosity::Type, const FName&) override {
    Text += V;
    Text += TEXT("\n");
  }
};

struct FLineResult {
  FString Cmd;
  bool bOk = true;
  FString Out;
};

class FS08DevExec {
 public:
  explicit FS08DevExec(const FString& InDir) : Dir(InDir) {
    IFileManager::Get().MakeDirectory(*Dir, true);
    NextSeq = FindNextSeq();
    Ticker = FTSTicker::GetCoreTicker().AddTicker(
        FTickerDelegate::CreateRaw(this, &FS08DevExec::Tick), 0.0f);
    ShotHandle = UGameViewportClient::OnScreenshotCaptured().AddRaw(this, &FS08DevExec::OnCaptured);
    const FString Ready = FString::Printf(TEXT("{\"pid\": %u, \"nextSeq\": %d}"),
                                          FPlatformProcess::GetCurrentProcessId(), NextSeq);
    FFileHelper::SaveStringToFile(Ready, *(Dir / TEXT("ready.json")));
    UE_LOG(LogS08DevExec, Display, TEXT("DEVEXEC ready dir=%s nextSeq=%d"), *Dir, NextSeq);
  }

 private:
  FString Dir;
  int32 NextSeq = 1;
  FTSTicker::FDelegateHandle Ticker;
  FDelegateHandle ShotHandle;
  double PollAt = 0.0;

  // The command file in progress.
  bool bBusy = false;
  int32 Seq = 0;
  TArray<FString> Lines;
  int32 LineIndex = 0;
  TArray<FLineResult> Results;
  double StartedAt = 0.0;
  double ResumeAt = 0.0;
  FString PendingShot;  // waiting for OnCaptured
  bool bShotSaved = false;
  int32 ShotFramesLeft = 0;
  FVector2D LastPos = FVector2D::ZeroVector;

  int32 FindNextSeq() const {
    int32 Max = 0;
    TArray<FString> Files;
    IFileManager::Get().FindFiles(Files, *(Dir / TEXT("done-*.json")), true, false);
    for (const FString& F : Files) {
      Max = FMath::Max(Max, FCString::Atoi(*F.Mid(5)));
    }
    return Max + 1;
  }

  bool Tick(float) {
    const double Now = FPlatformTime::Seconds();
    if (!bBusy) {
      if (Now < PollAt) return true;
      PollAt = Now + 0.1;
      const FString Path = Dir / FString::Printf(TEXT("cmd-%d.txt"), NextSeq);
      FString Text;
      if (!IFileManager::Get().FileExists(*Path) || !FFileHelper::LoadFileToString(Text, *Path)) return true;
      Seq = NextSeq++;
      Text.ParseIntoArrayLines(Lines, true);
      LineIndex = 0;
      Results.Reset();
      StartedAt = Now;
      ResumeAt = 0.0;
      bBusy = true;
    }
    if (!PendingShot.IsEmpty()) {
      if (!bShotSaved && --ShotFramesLeft > 0) return true;
      FLineResult& R = Results.Last();
      R.bOk = bShotSaved;
      R.Out = bShotSaved ? PendingShot : FString(TEXT("capture timed out"));
      PendingShot.Reset();
    }
    if (Now < ResumeAt) return true;
    while (LineIndex < Lines.Num()) {
      const FString Line = Lines[LineIndex++].TrimStartAndEnd();
      if (Line.IsEmpty() || Line.StartsWith(TEXT("#"))) continue;
      FLineResult& R = Results.AddDefaulted_GetRef();
      R.Cmd = Line;
      RunLine(Line, R);
      // Input lines yield to the next frame: Slate applies focus / hover changes of a click on the following tick,
      // so `click` + `type` in one frame would type into the old focus.
      static const TSet<FString> InputOps = {TEXT("click"), TEXT("up"), TEXT("down"), TEXT("move"), TEXT("drag"), TEXT("wheel"), TEXT("key"),
                                             TEXT("type")};
      if (InputOps.Contains(Line.Left(Line.Find(TEXT(" "))).ToLower())) {
        ResumeAt = FMath::Max(ResumeAt, FPlatformTime::Seconds() + 0.05);
      }
      if (!PendingShot.IsEmpty() || FPlatformTime::Seconds() < ResumeAt) return true;
    }
    Finish();
    return true;
  }

  void Finish() {
    TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetNumberField(TEXT("seq"), Seq);
    bool bAll = true;
    TArray<TSharedPtr<FJsonValue>> Arr;
    for (const FLineResult& R : Results) {
      bAll &= R.bOk;
      TSharedRef<FJsonObject> O = MakeShared<FJsonObject>();
      O->SetStringField(TEXT("cmd"), R.Cmd);
      O->SetBoolField(TEXT("ok"), R.bOk);
      O->SetStringField(TEXT("out"), R.Out);
      Arr.Add(MakeShared<FJsonValueObject>(O));
    }
    Root->SetBoolField(TEXT("ok"), bAll);
    Root->SetNumberField(TEXT("ms"), FMath::RoundToInt((FPlatformTime::Seconds() - StartedAt) * 1000.0));
    Root->SetArrayField(TEXT("lines"), Arr);
    FString Json;
    const TSharedRef<TJsonWriter<>> W = TJsonWriterFactory<>::Create(&Json);
    FJsonSerializer::Serialize(Root, W);
    const FString Tmp = Dir / FString::Printf(TEXT("done-%d.tmp"), Seq);
    FFileHelper::SaveStringToFile(Json, *Tmp, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    IFileManager::Get().Move(*(Dir / FString::Printf(TEXT("done-%d.json"), Seq)), *Tmp, true);
    bBusy = false;
  }

  static UGameViewportClient* Viewport() { return GEngine ? GEngine->GameViewport : nullptr; }

  /** Viewport pixels -> Slate absolute (desktop) coordinates through the game viewport widget geometry. */
  bool ToScreen(double X, double Y, FVector2D& Out, FString& Err) const {
    UGameViewportClient* GV = Viewport();
    if (!GV || !GV->Viewport) { Err = TEXT("no game viewport"); return false; }
    const TSharedPtr<SViewport> Widget = GV->GetGameViewportWidget();
    if (!Widget.IsValid()) { Err = TEXT("no viewport widget"); return false; }
    const FGeometry& Geo = Widget->GetTickSpaceGeometry();
    const FIntPoint Px = GV->Viewport->GetSizeXY();
    if (Px.X <= 0 || Px.Y <= 0) { Err = TEXT("viewport size 0"); return false; }
    const FVector2D Local(X * Geo.GetLocalSize().X / Px.X, Y * Geo.GetLocalSize().Y / Px.Y);
    Out = Geo.LocalToAbsolute(Local);
    return true;
  }

  TSharedPtr<FGenericWindow> NativeWindow() const {
    UGameViewportClient* GV = Viewport();
    const TSharedPtr<SWindow> Win = GV ? GV->GetWindow() : nullptr;
    return Win.IsValid() ? Win->GetNativeWindow() : nullptr;
  }

  /** The cursor user gets a faux (virtual) cursor at the driver's position: Slate synthesizes mouse moves from the
   *  cursor position every few frames, and with the OS cursor outside the game window that synthesized move is a
   *  MouseLeave - the viewport's cached mouse position drops to (-1,-1) between a press and its release and board picks
   *  (GetHitResultUnderCursor on the release) miss. The OS cursor itself never moves. */
  static void HoldCursor(const FVector2D& P) {
    FSlateApplication& App = FSlateApplication::Get();
    App.UsePlatformCursorForCursorUser(false);
    App.SetCursorPos(P);
  }

  void Move(const FVector2D& P) {
    FSlateApplication& App = FSlateApplication::Get();
    HoldCursor(P);
    const FPointerEvent E(App.CursorPointerIndex, P, LastPos, TSet<FKey>(), EKeys::Invalid, 0.0f,
                          FModifierKeysState());
    App.ProcessMouseMoveEvent(E);
    LastPos = P;
  }

  void Button(const FVector2D& P, const FKey& Btn, bool bDown) {
    FSlateApplication& App = FSlateApplication::Get();
    HoldCursor(P);
    TSet<FKey> Pressed;
    if (bDown) Pressed.Add(Btn);
    const FPointerEvent E(App.CursorPointerIndex, P, LastPos, Pressed, Btn, 0.0f, FModifierKeysState());
    if (bDown) {
      App.ProcessMouseButtonDownEvent(NativeWindow(), E);
    } else {
      App.ProcessMouseButtonUpEvent(E);
    }
    LastPos = P;
  }

  static FModifierKeysState Mods(const FString& M) {
    const bool C = M.Contains(TEXT("ctrl")), S = M.Contains(TEXT("shift")), A = M.Contains(TEXT("alt"));
    return FModifierKeysState(S, false, C, false, A, false, false, false, false);
  }

  void RunLine(const FString& Line, FLineResult& R) {
    TArray<FString> T;
    Line.ParseIntoArrayWS(T);
    const FString Op = T[0].ToLower();
    FString Err;
    FVector2D P;
    if (Op == TEXT("click") && T.Num() >= 3) {
      if (!ToScreen(FCString::Atod(*T[1]), FCString::Atod(*T[2]), P, Err)) { R.bOk = false; R.Out = Err; return; }
      const FKey Btn = (T.Num() > 3 && T[3] == TEXT("right")) ? EKeys::RightMouseButton : EKeys::LeftMouseButton;
      Move(P);
      Button(P, Btn, true);
      // The release goes out two frames later: UPlayerInput folds a press and a release of one frame into a key that
      // was never down, so game-side picks (board cells, fighters) would miss a same-frame click.
      Lines.Insert(FString::Printf(TEXT("up %s %s %s"), *T[1], *T[2], Btn == EKeys::RightMouseButton
                                                                           ? TEXT("right") : TEXT("left")),
                   LineIndex);
      ResumeAt = FPlatformTime::Seconds() + 0.05;
      R.Out = FString::Printf(TEXT("abs %.0f,%.0f"), P.X, P.Y);
    } else if ((Op == TEXT("up") || Op == TEXT("down")) && T.Num() >= 3) {
      if (!ToScreen(FCString::Atod(*T[1]), FCString::Atod(*T[2]), P, Err)) { R.bOk = false; R.Out = Err; return; }
      const FKey Btn = (T.Num() > 3 && T[3] == TEXT("right")) ? EKeys::RightMouseButton : EKeys::LeftMouseButton;
      if (Op == TEXT("down")) Move(P);
      Button(P, Btn, Op == TEXT("down"));
    } else if (Op == TEXT("pick") && T.Num() >= 3) {
      if (!ToScreen(FCString::Atod(*T[1]), FCString::Atod(*T[2]), P, Err)) { R.bOk = false; R.Out = Err; return; }
      FSlateApplication& App = FSlateApplication::Get();
      const FWidgetPath Path = App.LocateWindowUnderMouse(P, App.GetInteractiveTopLevelWindows(), false);  // as FSlateUser::QueryCursor
      TArray<FString> Parts;
      for (int32 I = Path.Widgets.Num() - 1; I >= 0 && Parts.Num() < 32; --I) {
        const FArrangedWidget& A = Path.Widgets[I];
        SWidget& W = A.Widget.Get();
        const FCursorReply C = W.OnCursorQuery(A.Geometry, FPointerEvent(App.CursorPointerIndex, P, P, TSet<FKey>(),
                                                                          EKeys::Invalid, 0.0f, FModifierKeysState()));
        Parts.Add(FString::Printf(TEXT("%s:%s%s"), *W.GetTypeAsString(), *FReflectionMetaData::GetWidgetDebugInfo(&W),
                                  C.IsEventHandled() ? *FString::Printf(TEXT("[c%d]"), static_cast<int32>(C.GetCursorType())) : TEXT("")));
      }
      const TSharedPtr<ICursor> Os = App.GetPlatformCursor();
      const TSharedPtr<FSlateUser> User = App.GetCursorUser();
      const TSharedPtr<SWidget> Captor = User.IsValid() ? User->GetCursorCaptor() : nullptr;
      R.Out = FString::Printf(TEXT("platform=%d captor=%s | "), Os.IsValid() ? static_cast<int32>(Os->GetType()) : -1,
                              Captor.IsValid() ? *FReflectionMetaData::GetWidgetDebugInfo(Captor.Get()) : TEXT("-")) +
              FString::Join(Parts, TEXT(" < "));
    } else if (Op == TEXT("move") && T.Num() >= 3) {
      if (!ToScreen(FCString::Atod(*T[1]), FCString::Atod(*T[2]), P, Err)) { R.bOk = false; R.Out = Err; return; }
      Move(P);
    } else if (Op == TEXT("drag") && T.Num() >= 5) {
      FVector2D A, B;
      if (!ToScreen(FCString::Atod(*T[1]), FCString::Atod(*T[2]), A, Err) ||
          !ToScreen(FCString::Atod(*T[3]), FCString::Atod(*T[4]), B, Err)) { R.bOk = false; R.Out = Err; return; }
      Move(A);
      Button(A, EKeys::LeftMouseButton, true);
      for (int32 I = 1; I <= 8; ++I) {
        const FVector2D Q = FMath::Lerp(A, B, I / 8.0);
        FSlateApplication& App = FSlateApplication::Get();
        TSet<FKey> Pressed{EKeys::LeftMouseButton};
        App.ProcessMouseMoveEvent(FPointerEvent(App.CursorPointerIndex, Q, LastPos, Pressed, EKeys::Invalid, 0.0f,
                                                FModifierKeysState()));
        LastPos = Q;
      }
      Button(B, EKeys::LeftMouseButton, false);
    } else if (Op == TEXT("wheel") && T.Num() >= 4) {
      if (!ToScreen(FCString::Atod(*T[1]), FCString::Atod(*T[2]), P, Err)) { R.bOk = false; R.Out = Err; return; }
      Move(P);
      FSlateApplication& App = FSlateApplication::Get();
      App.ProcessMouseWheelOrGestureEvent(FPointerEvent(App.CursorPointerIndex, P, P, TSet<FKey>(), EKeys::Invalid,
                                                        FCString::Atof(*T[3]), FModifierKeysState()),
                                          nullptr);
    } else if (Op == TEXT("key") && T.Num() >= 2) {
      const FKey Key(*T[1]);
      if (!Key.IsValid()) { R.bOk = false; R.Out = TEXT("unknown key"); return; }
      const FModifierKeysState M = Mods(T.Num() > 2 ? T[2].ToLower() : FString());
      const uint32* Code = nullptr;
      const uint32* Char = nullptr;
      FInputKeyManager::Get().GetCodesFromKey(Key, Code, Char);
      const uint32 KC = Code ? *Code : 0, CC = Char ? *Char : 0;
      FSlateApplication& App = FSlateApplication::Get();
      App.ProcessKeyDownEvent(FKeyEvent(Key, M, 0, false, CC, KC));
      App.ProcessKeyUpEvent(FKeyEvent(Key, M, 0, false, CC, KC));
    } else if (Op == TEXT("type") && T.Num() >= 2) {
      const FString Text = Line.Mid(Line.Find(TEXT(" ")) + 1);
      for (const TCHAR C : Text) {
        FSlateApplication::Get().ProcessKeyCharEvent(FCharacterEvent(C, FModifierKeysState(), 0, false));
      }
    } else if (Op == TEXT("wait") && T.Num() >= 2) {
      ResumeAt = FPlatformTime::Seconds() + FCString::Atod(*T[1]);
    } else if (Op == TEXT("shot") && T.Num() >= 2) {
      const FString Path = FPaths::ConvertRelativePathToFull(Line.Mid(Line.Find(TEXT(" ")) + 1).TrimQuotes());
      IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true);
      IFileManager::Get().Delete(*Path, false, true, true);
      FScreenshotRequest::RequestScreenshot(Path, /*bShowUI=*/true, /*bAddFilenameSuffix=*/false);
      PendingShot = Path;
      bShotSaved = false;
      ShotFramesLeft = 120;
    } else if (Op == TEXT("res") && T.Num() >= 2) {
      FDevOutput Out;
      GEngine->Exec(CurrentWorld(), *FString::Printf(TEXT("r.SetRes %s"), *T[1]), Out);
      R.Out = Out.Text;
      ResumeAt = FPlatformTime::Seconds() + 0.5;
    } else if (Op == TEXT("cursor") && T.Num() >= 2) {
      // `cursor os` gives the cursor back to the real mouse (to play by hand in the same window); input lines take it
      // again.
      FSlateApplication::Get().UsePlatformCursorForCursorUser(T[1] == TEXT("os"));
    } else if (Op == TEXT("info")) {
      UGameViewportClient* GV = Viewport();
      const TSharedPtr<SWindow> Win = GV ? GV->GetWindow() : nullptr;
      const FIntPoint Px = (GV && GV->Viewport) ? GV->Viewport->GetSizeXY() : FIntPoint::ZeroValue;
      UWorld* World = CurrentWorld();
      R.Out = FString::Printf(TEXT("viewport=%dx%d dpi=%.3f window=%s world=%s gamemode=%s"), Px.X, Px.Y,
                              Win.IsValid() ? Win->GetDPIScaleFactor() : 0.0f,
                              Win.IsValid() ? *Win->GetPositionInScreen().ToString() : TEXT("-"),
                              World ? *World->GetMapName() : TEXT("-"),
                              (World && World->GetAuthGameMode()) ? *World->GetAuthGameMode()->GetClass()->GetName()
                                                                  : TEXT("-"));
    } else {
      FDevOutput Out;
      R.bOk = GEngine && GEngine->Exec(CurrentWorld(), *Line, Out);
      R.Out = Out.Text;
    }
  }

  static UWorld* CurrentWorld() {
    UGameViewportClient* GV = Viewport();
    return GV ? GV->GetWorld() : nullptr;
  }

  void OnCaptured(int32 Width, int32 Height, const TArray<FColor>& Colors) {
    // AS08FlowGameMode::HandleScreenshotCaptured is bound too; it saves only its own pending path.
    if (PendingShot.IsEmpty() || Colors.Num() != Width * Height) return;
    TArray64<uint8> Png;
    FImageUtils::PNGCompressImageArray(Width, Height, Colors, Png);
    bShotSaved = Png.Num() > 0 && FFileHelper::SaveArrayToFile(Png, *PendingShot);
    ShotFramesLeft = 1;
  }
};

FS08DevExec* GDevExec = nullptr;

FDelayedAutoRegisterHelper GDevExecRegister(EDelayedRegisterRunPhase::EndOfEngineInit, [] {
  FString Dir;
  if (GDevExec || !FParse::Value(FCommandLine::Get(), TEXT("DevExec="), Dir) || Dir.IsEmpty()) return;
  GDevExec = new FS08DevExec(FPaths::ConvertRelativePathToFull(Dir));
});

}  // namespace

bool S08DevExec::Active() { return GDevExec != nullptr; }
