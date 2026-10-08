// VS-7 SC-08...SC-13 (docs/game-design/visual/06-tasks/screens.csv; 04-hud-spec.md §1.3): the LOBBY side of the flow
// controller - the open rooms (availableGames, mode ONE_V_ONE: a VS_AI room has no human seat, ВР-VS4-SC08-01) and the
// join of a list row by its id (joinGame). Neither changes the stage by itself: a join that the server accepts goes
// through HandleRoomResponse like the code path (stage Room); a refused one broadcasts OnFlowError with the server's
// message (the LOBBY row then explains itself: why.room.full / why.room.started, ВР-VS4-SC08-02).
// No room code is traced (traces are published evidence).
#include "S08FlowController.h"

namespace {
const TCHAR* LobbyAvailableQuery =
    TEXT("query AG($mode: String, $limit: Float) { availableGames(mode: $mode, limit: $limit) {")
    TEXT(" id code status mode hostId boardId players { userId heroId } } }");
const TCHAR* LobbyJoinMutation =
    TEXT("mutation J($input: JoinGameDto!) { joinGame(input: $input) {")
    TEXT(" id code status mode hostId boardId")
    TEXT(" players { userId username heroId isReady seatOrder } } }");
}  // namespace

void FS08FlowController::FetchAvailableGames() {
  if (AvailableState != EBootQuery::Done) AvailableState = EBootQuery::Loading;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("mode"), TEXT("ONE_V_ONE"));
  Variables->SetNumberField(TEXT("limit"), 20);
  const int32 Gen = AuthGeneration;
  const int32 Serial = ++AvailableSerial;
  SendHttp(LobbyAvailableQuery, Variables,
           [this, Gen, Serial](bool bOk, const TArray<FS08GraphQLError>& Errors, TSharedPtr<FJsonObject> Data, const FString&) {
             if (AuthGeneration != Gen || Serial != AvailableSerial) return;  // another session / a newer request
             const TArray<TSharedPtr<FJsonValue>>* Games = nullptr;
             if (!bOk || !Data.IsValid() || !Data->TryGetArrayField(TEXT("availableGames"), Games) || !Games) {
               AvailableState = EBootQuery::Failed;
               ++AvailableAnswers;
               Trace(TEXT("LOBBY list failed: ") + (Errors.Num() ? Errors[0].Message : FString(TEXT("no list"))));
               return;
             }
             AvailableGames.Reset();
             for (const TSharedPtr<FJsonValue>& Value : *Games) {
               const TSharedPtr<FJsonObject>* Game = nullptr;
               if (!Value.IsValid() || !Value->TryGetObject(Game) || !Game->IsValid()) continue;
               FLobbyGame Row;
               (*Game)->TryGetStringField(TEXT("id"), Row.Id);
               (*Game)->TryGetStringField(TEXT("code"), Row.Code);
               (*Game)->TryGetStringField(TEXT("status"), Row.Status);
               (*Game)->TryGetStringField(TEXT("mode"), Row.Mode);
               (*Game)->TryGetStringField(TEXT("hostId"), Row.HostId);
               (*Game)->TryGetStringField(TEXT("boardId"), Row.BoardId);
               const TArray<TSharedPtr<FJsonValue>>* Players = nullptr;
               if ((*Game)->TryGetArrayField(TEXT("players"), Players) && Players) {
                 Row.Players = Players->Num();
                 for (const TSharedPtr<FJsonValue>& P : *Players) {
                   const TSharedPtr<FJsonObject>* Player = nullptr;
                   FString HeroId;
                   if (P.IsValid() && P->TryGetObject(Player) && Player->IsValid() && (*Player)->TryGetStringField(TEXT("heroId"), HeroId) &&
                       !HeroId.IsEmpty()) {
                     Row.HeroIds.Add(HeroId);
                   }
                 }
               }
               if (Row.Id.IsEmpty()) continue;
               AvailableGames.Add(MoveTemp(Row));
             }
             AvailableState = EBootQuery::Done;
             ++AvailableAnswers;
             Trace(FString::Printf(TEXT("LOBBY list rows=%d"), AvailableGames.Num()));
           });
}

void FS08FlowController::JoinRoomById(const FString& GameId) {
  if (GameId.IsEmpty() || !CanEnterRoomFlow(TEXT("JOIN"))) return;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  TSharedRef<FJsonObject> Input = MakeShared<FJsonObject>();
  Input->SetStringField(TEXT("gameId"), GameId);
  Variables->SetObjectField(TEXT("input"), Input);
  const int32 Gen = MatchGeneration;
  Trace(TEXT("JOIN row -> ") + GameId);
  SendHttp(LobbyJoinMutation, Variables,
           [this, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors, TSharedPtr<FJsonObject> Data, const FString&) {
             // the same stale / live-match gates as the code path (JoinRoomByCode)
             if (MatchGeneration != Gen) {
               Trace(TEXT("JOIN stale answer ignored"));
               return;
             }
             if (!CanApplyRoomEntryAnswer(TEXT("JOIN"))) return;
             if (!bOk) {
               Trace(TEXT("JOIN failed: ") + (Errors.Num() ? Errors[0].Message : FString(TEXT("?"))));
               OnFlowError.Broadcast(Errors.Num() ? Errors[0] : FS08GraphQLError{TEXT("TRANSPORT"), TEXT("join failed"), FString()});
               return;
             }
             HandleRoomResponse(Data, TEXT("joinGame"));
           });
}
