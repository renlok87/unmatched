// VS-7 SC-03...SC-05 (docs/game-design/visual/06-tasks/screens.csv; 04-hud-spec.md §1.1): the BOOT pass of the flow
// controller after the login - the board catalogue (boardList: Board row id -> name), the own live match after a
// restart (myGames IN_PROGRESS) and its return. None of these change the stage by itself; the BOOT screen
// (UI/UmScreenBoot.h) reads the states. heroList stays FS08FlowController::FetchHeroes (it counts its failures).
// GD-038: the refresh token stays in memory only, so a fresh client has no session to check: BOOT runs its
// session stage, goes to LOGIN and continues with the catalogue after the login (ВР-VS7-01).
#include "S08FlowController.h"

namespace {
const TCHAR* BootBoardsQuery = TEXT("query BL($limit: Int) { boardList(limit: $limit) { items { id name } } }");
const TCHAR* BootActiveGameQuery =
    TEXT("query MA($status: GameStatus) { myGames(filters: { status: $status }) {")
    TEXT(" id code status mode hostId boardId")
    TEXT(" players { userId username heroId isReady seatOrder } } }");
}  // namespace

void FS08FlowController::FetchBoards() {
  BoardsState = EBootQuery::Loading;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetNumberField(TEXT("limit"), 100);
  const int32 Gen = AuthGeneration;
  SendHttp(BootBoardsQuery, Variables,
           [this, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors, TSharedPtr<FJsonObject> Data, const FString&) {
             if (AuthGeneration != Gen) return;  // another session's answer
             const TSharedPtr<FJsonObject>* List = nullptr;
             const TArray<TSharedPtr<FJsonValue>>* Items = nullptr;
             if (!bOk || !Data.IsValid() || !Data->TryGetObjectField(TEXT("boardList"), List) || !List ||
                 !(*List)->TryGetArrayField(TEXT("items"), Items) || !Items) {
               BoardsState = EBootQuery::Failed;
               Trace(TEXT("BOARDS failed: ") + (Errors.Num() ? Errors[0].Message : FString(TEXT("no list"))));
               return;
             }
             BoardNames.Reset();
             for (const TSharedPtr<FJsonValue>& Value : *Items) {
               const TSharedPtr<FJsonObject>* Row = nullptr;
               if (!Value.IsValid() || !Value->TryGetObject(Row) || !Row->IsValid()) continue;
               BoardNames.Add((*Row)->GetStringField(TEXT("id")), (*Row)->GetStringField(TEXT("name")));
             }
             BoardsState = EBootQuery::Done;
             Trace(FString::Printf(TEXT("BOARDS loaded %d"), BoardNames.Num()));
           });
}

void FS08FlowController::FetchActiveGame() {
  ActiveGameState = EBootQuery::Loading;
  ActiveGame = FS08RoomState();
  ActiveGameRow.Reset();
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("status"), TEXT("IN_PROGRESS"));
  const int32 Gen = AuthGeneration;
  SendHttp(BootActiveGameQuery, Variables,
           [this, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors, TSharedPtr<FJsonObject> Data, const FString&) {
             if (AuthGeneration != Gen) return;
             const TArray<TSharedPtr<FJsonValue>>* Games = nullptr;
             if (!bOk || !Data.IsValid() || !Data->TryGetArrayField(TEXT("myGames"), Games) || !Games) {
               ActiveGameState = EBootQuery::Failed;
               Trace(TEXT("RESUME check failed: ") + (Errors.Num() ? Errors[0].Message : FString(TEXT("no list"))));
               return;
             }
             for (const TSharedPtr<FJsonValue>& Value : *Games) {
               const TSharedPtr<FJsonObject>* Game = nullptr;
               if (!Value.IsValid() || !Value->TryGetObject(Game) || !Game->IsValid()) continue;
               if ((*Game)->GetStringField(TEXT("status")) != TEXT("IN_PROGRESS")) continue;
               ActiveGameRow = *Game;
               ActiveGame.GameId = (*Game)->GetStringField(TEXT("id"));
               ActiveGame.Status = (*Game)->GetStringField(TEXT("status"));
               ActiveGame.Mode = (*Game)->GetStringField(TEXT("mode"));
               ActiveGame.HostId = (*Game)->GetStringField(TEXT("hostId"));
               ActiveGame.BoardId = (*Game)->GetStringField(TEXT("boardId"));
               const TArray<TSharedPtr<FJsonValue>>* Players = nullptr;
               if ((*Game)->TryGetArrayField(TEXT("players"), Players) && Players) {
                 for (const TSharedPtr<FJsonValue>& P : *Players) {
                   const TSharedPtr<FJsonObject>* Player = nullptr;
                   if (!P.IsValid() || !P->TryGetObject(Player) || !Player->IsValid()) continue;
                   FS08RoomPlayer Entry;
                   Entry.UserId = (*Player)->GetStringField(TEXT("userId"));
                   Entry.Username = (*Player)->GetStringField(TEXT("username"));
                   Entry.HeroId = (*Player)->GetStringField(TEXT("heroId"));
                   ActiveGame.Players.Add(MoveTemp(Entry));
                 }
               }
               break;
             }
             ActiveGameState = EBootQuery::Done;
             // the id is no secret (the RECOVER line prints it too); no room code in the trace
             Trace(FString::Printf(TEXT("RESUME check game=%s mode=%s"),
                                   ActiveGame.GameId.IsEmpty() ? TEXT("-") : *ActiveGame.GameId,
                                   ActiveGame.Mode.IsEmpty() ? TEXT("-") : *ActiveGame.Mode));
           });
}

bool FS08FlowController::ResumeActiveGame() {
  if (!ActiveGameRow.IsValid() || ActiveGame.GameId.IsEmpty()) return false;
  if (!CanEnterRoomFlow(TEXT("RESUME"))) return false;
  ParseRoomFrom(ActiveGameRow);
  Trace(TEXT("RESUME room=") + Room.GameId + TEXT(" status=") + Room.Status);
  SetStage(ES08Stage::Room);
  OnRoom.Broadcast(Room);
  // the guest's IN_PROGRESS path of HandleRoomResponse: the barrier read + the stream, stage Started
  if (Stage == ES08Stage::Room && Room.Status == TEXT("IN_PROGRESS")) AttachGameStateStream();
  return true;
}
