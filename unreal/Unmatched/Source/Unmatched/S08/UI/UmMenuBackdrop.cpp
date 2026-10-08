// VS-7 SC-02: the menu backdrop helpers - see UmMenuBackdrop.h (the game-mode side: S08FlowGameModeUmScreens.cpp).
#include "UmMenuBackdrop.h"

#include "../S08Contracts.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace UmMenuBackdrop {
bool Wanted(const S08ArtLook::FS08SlateHudBlocks& Blocks) { return Blocks.UmgRoot() && !Blocks.IsSlate(FName(TEXT("menubg"))); }

FString FixturePath() { return FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("Bench"), TEXT("S08BenchMarmoreal.json")); }

bool LoadBoard(const FString& File, FS08BoardModel& OutBoard, FString& OutBoardId, FString* OutProblem) {
  auto Fail = [OutProblem](const FString& Why) {
    if (OutProblem) *OutProblem = Why;
    return false;
  };
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *File)) return Fail(TEXT("no fixture file"));
  TSharedPtr<FJsonValue> Value;
  FString Problem;
  if (!FS08Contracts::TryParseJsonValue(Text, Value, Problem)) return Fail(TEXT("fixture json: ") + Problem);
  const TSharedPtr<FJsonObject>* Root = nullptr;
  if (!Value->TryGetObject(Root) || !Root->IsValid()) return Fail(TEXT("fixture root"));
  (*Root)->TryGetStringField(TEXT("benchBoardId"), OutBoardId);
  // the captured gameState(gameId) body: {"raw": <body object or string>} (S08LoadGameStateFixture of the bench)
  FString Body;
  const TSharedPtr<FJsonObject>* RawObject = nullptr;
  if (!(*Root)->TryGetStringField(TEXT("raw"), Body)) {
    if (!(*Root)->TryGetObjectField(TEXT("raw"), RawObject) || !RawObject->IsValid()) return Fail(TEXT("fixture raw"));
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
    FJsonSerializer::Serialize(RawObject->ToSharedRef(), Writer);
  }
  FS08Snapshot Snap;
  FString RawState;
  FS08GraphQLError Error;
  if (!FS08Contracts::ParseGameStateQuery(Body, Snap, RawState, Error)) return Fail(TEXT("fixture state: ") + Error.Message);
  if (!OutBoard.Decode(Snap.BoardState)) return Fail(TEXT("fixture board decode"));
  return true;
}

FString BackdropShort(const FString& Field) {
  if (Field.IsEmpty()) return TEXT("-");
  int32 Paren = INDEX_NONE;
  return Field.FindChar(TEXT('('), Paren) ? Field.Left(Paren) : Field;
}

FString TraceLine(const FString& BoardIdIn, const FString& Profile, int32 Fighters, const FString& Backdrop, const TCHAR* Stage,
                  const TCHAR* State) {
  return FString::Printf(TEXT("SCREEN-BG board=%s boardId=%s profile=%s fighters=%d veil=%.2f backdrop=%s stage=%s state=%s"),
                         BoardKey, BoardIdIn.IsEmpty() ? TEXT("-") : *BoardIdIn, Profile.IsEmpty() ? TEXT("-") : *Profile,
                         Fighters, VeilAlpha, *BackdropShort(Backdrop), Stage, State);
}
}  // namespace UmMenuBackdrop
