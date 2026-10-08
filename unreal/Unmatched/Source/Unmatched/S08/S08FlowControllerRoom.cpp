// VS-7 SC-14...SC-20 (docs/game-design/visual/06-tasks/screens.csv; 04-hud-spec.md §1.4, §1.5): the ROOM and the match
// loading side of the flow controller.
//
//   hero card   adminHero(id) - the admin :5480 data the cards show (ВР-VS4-SC14-01): health, movement,
//               properties.attackType, sidekicks[] (name, health, movement, attackType; one entry per figure - the
//               harpies are three equal entries, grouped here with Count), ability.description (EN only in the DB).
//   deck        cardList(heroId) - the hero's catalogue (copies in Card.count); ROOM «Просмотр колоды» shows it in the
//               INSPECT deck mode (composition only, never an order - F-05). The count = the sum of copies (30 and 30).
//   loading     SC-19: gameSequence(gameId) is the connect stage (a cheap read that proves the match row answers);
//               SC-20: RetryMatchLoad asks gameSequence and gameState again and lets the stream reconnect at once;
//               DetachToLobby drops the local room and stream without leaveGame - the match stays IN_PROGRESS (the way
//               back is the LOBBY «Вернуться в мою партию» / the BOOT resume, SC-11 / SC-05).
// None of these reads changes the stage; no room code, no name in a trace line.
#include "S08FlowController.h"

#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace {
const TCHAR* RoomHeroQuery =
    TEXT("query RH($id: String!) { adminHero(id: $id) { id name health movement ability properties sidekicks } }");
const TCHAR* RoomDeckQuery =
    TEXT("query RD($heroId: String, $limit: Int) { cardList(heroId: $heroId, limit: $limit) { total items {")
    TEXT(" id name nameRu cardType attackValue defenseValue boostValue bannerName count } } }");
const TCHAR* GameSequenceQuery = TEXT("query GQ($gameId: String!) { gameSequence(gameId: $gameId) }");

/** A JSON text field of the admin DTO (ability / properties / sidekicks are JSON strings) -> its value. */
TSharedPtr<FJsonValue> UmRoomParseJsonString(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field) {
  FString Text;
  if (!Obj.IsValid() || !Obj->TryGetStringField(Field, Text) || Text.IsEmpty()) return nullptr;
  TSharedPtr<FJsonValue> Value;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
  if (!FJsonSerializer::Deserialize(Reader, Value)) return nullptr;
  return Value;
}

/** A number the DB keeps as a number or as a string ("7"). */
int32 UmRoomInt(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field) {
  double D = 0.0;
  if (Obj->TryGetNumberField(Field, D)) return static_cast<int32>(D);
  FString S;
  if (Obj->TryGetStringField(Field, S)) return FCString::Atoi(*S);
  return 0;
}

int32 UmRoomOptInt(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field) {
  double D = 0.0;
  return Obj->TryGetNumberField(Field, D) ? static_cast<int32>(D) : -1;
}
}  // namespace

FS08FlowController::EBootQuery FS08FlowController::GetHeroDetailsState(const FString& HeroId) const {
  const EBootQuery* S = HeroDetailsStates.Find(HeroId);
  return S ? *S : EBootQuery::Idle;
}

FS08FlowController::EBootQuery FS08FlowController::GetHeroDeckState(const FString& HeroId) const {
  const EBootQuery* S = HeroDeckStates.Find(HeroId);
  return S ? *S : EBootQuery::Idle;
}

void FS08FlowController::FetchHeroDetails(const FString& HeroId) {
  if (HeroId.IsEmpty() || GetHeroDetailsState(HeroId) == EBootQuery::Loading || GetHeroDetailsState(HeroId) == EBootQuery::Done) return;
  HeroDetailsStates.Add(HeroId, EBootQuery::Loading);
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("id"), HeroId);
  const int32 Gen = AuthGeneration;
  SendHttp(RoomHeroQuery, Variables,
           [this, Gen, HeroId](bool bOk, const TArray<FS08GraphQLError>& Errors, TSharedPtr<FJsonObject> Data, const FString&) {
             if (AuthGeneration != Gen) return;
             const TSharedPtr<FJsonObject>* H = nullptr;
             if (!bOk || !Data.IsValid() || !Data->TryGetObjectField(TEXT("adminHero"), H) || !H || !H->IsValid()) {
               HeroDetailsStates.Add(HeroId, EBootQuery::Failed);
               Trace(FString::Printf(TEXT("ROOM hero details failed id=%s: %s"), *HeroId, Errors.Num() ? *Errors[0].Code : TEXT("no data")));
               return;
             }
             FHeroDetails D;
             D.Id = HeroId;
             (*H)->TryGetStringField(TEXT("name"), D.Name);
             D.Health = UmRoomInt(*H, TEXT("health"));
             D.Movement = UmRoomInt(*H, TEXT("movement"));
             if (const TSharedPtr<FJsonValue> Props = UmRoomParseJsonString(*H, TEXT("properties")); Props.IsValid() && Props->Type == EJson::Object) {
               Props->AsObject()->TryGetStringField(TEXT("attackType"), D.AttackType);
             }
             if (const TSharedPtr<FJsonValue> Ability = UmRoomParseJsonString(*H, TEXT("ability")); Ability.IsValid() && Ability->Type == EJson::Object) {
               if (!Ability->AsObject()->TryGetStringField(TEXT("description"), D.Ability)) Ability->AsObject()->TryGetStringField(TEXT("effect"), D.Ability);
             }
             if (const TSharedPtr<FJsonValue> Kicks = UmRoomParseJsonString(*H, TEXT("sidekicks")); Kicks.IsValid() && Kicks->Type == EJson::Array) {
               for (const TSharedPtr<FJsonValue>& V : Kicks->AsArray()) {
                 if (!V.IsValid() || V->Type != EJson::Object) continue;
                 const TSharedPtr<FJsonObject> K = V->AsObject();
                 FHeroSidekick S;
                 K->TryGetStringField(TEXT("name"), S.Name);
                 K->TryGetStringField(TEXT("attackType"), S.AttackType);
                 S.Health = UmRoomInt(K, TEXT("health"));
                 S.Movement = UmRoomInt(K, TEXT("movement"));
                 // one entry per figure: the three harpies are three equal entries -> one line «Harpies ×3»
                 FHeroSidekick* Same = D.Sidekicks.FindByPredicate([&S](const FHeroSidekick& X) {
                   return X.Name == S.Name && X.Health == S.Health && X.Movement == S.Movement && X.AttackType == S.AttackType;
                 });
                 if (Same) {
                   ++Same->Count;
                 } else {
                   S.Count = 1;
                   D.Sidekicks.Add(MoveTemp(S));
                 }
               }
             }
             Trace(FString::Printf(TEXT("ROOM hero id=%s hp=%d move=%d attack=%s sidekicks=%d"), *HeroId, D.Health, D.Movement,
                                   D.AttackType.IsEmpty() ? TEXT("-") : *D.AttackType, D.Sidekicks.Num()));
             HeroDetails.Add(HeroId, MoveTemp(D));
             HeroDetailsStates.Add(HeroId, EBootQuery::Done);
           });
}

void FS08FlowController::FetchHeroDeck(const FString& HeroId) {
  if (HeroId.IsEmpty() || GetHeroDeckState(HeroId) == EBootQuery::Loading || GetHeroDeckState(HeroId) == EBootQuery::Done) return;
  HeroDeckStates.Add(HeroId, EBootQuery::Loading);
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("heroId"), HeroId);
  Variables->SetNumberField(TEXT("limit"), 100);
  const int32 Gen = AuthGeneration;
  SendHttp(RoomDeckQuery, Variables,
           [this, Gen, HeroId](bool bOk, const TArray<FS08GraphQLError>& Errors, TSharedPtr<FJsonObject> Data, const FString&) {
             if (AuthGeneration != Gen) return;
             const TSharedPtr<FJsonObject>* List = nullptr;
             const TArray<TSharedPtr<FJsonValue>>* Items = nullptr;
             if (!bOk || !Data.IsValid() || !Data->TryGetObjectField(TEXT("cardList"), List) || !List ||
                 !(*List)->TryGetArrayField(TEXT("items"), Items) || !Items) {
               HeroDeckStates.Add(HeroId, EBootQuery::Failed);
               Trace(FString::Printf(TEXT("ROOM deck failed hero=%s: %s"), *HeroId, Errors.Num() ? *Errors[0].Code : TEXT("no data")));
               return;
             }
             TArray<FHeroDeckCard> Cards;
             int32 Copies = 0;
             for (const TSharedPtr<FJsonValue>& V : *Items) {
               if (!V.IsValid() || V->Type != EJson::Object) continue;
               const TSharedPtr<FJsonObject> O = V->AsObject();
               FHeroDeckCard C;
               O->TryGetStringField(TEXT("id"), C.CardId);
               O->TryGetStringField(TEXT("name"), C.Name);
               O->TryGetStringField(TEXT("nameRu"), C.NameRu);
               O->TryGetStringField(TEXT("cardType"), C.CardType);
               O->TryGetStringField(TEXT("bannerName"), C.BannerName);
               C.Attack = UmRoomOptInt(O, TEXT("attackValue"));
               C.Defense = UmRoomOptInt(O, TEXT("defenseValue"));
               C.Boost = UmRoomOptInt(O, TEXT("boostValue"));
               C.Count = FMath::Max(0, UmRoomInt(O, TEXT("count")));
               Copies += C.Count;
               Cards.Add(MoveTemp(C));
             }
             Trace(FString::Printf(TEXT("ROOM deck hero=%s unique=%d copies=%d"), *HeroId, Cards.Num(), Copies));
             HeroDecks.Add(HeroId, MoveTemp(Cards));
             HeroDeckStates.Add(HeroId, EBootQuery::Done);
           });
}

void FS08FlowController::FetchGameSequence() {
  if (Room.GameId.IsEmpty()) return;
  GameSequenceState = EBootQuery::Loading;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  Trace(FString::Printf(TEXT("LOADING sequence request game=%s"), *GameId));
  SendHttp(GameSequenceQuery, Variables,
           [this, GameId, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors, TSharedPtr<FJsonObject> Data, const FString&) {
             if (!IsSameMatchRequest(GameId, Gen)) return;
             double Seq = -1.0;
             if (bOk && Data.IsValid() && Data->HasField(TEXT("gameSequence"))) {
               Data->TryGetNumberField(TEXT("gameSequence"), Seq);
               GameSequenceState = EBootQuery::Done;
               Trace(FString::Printf(TEXT("LOADING sequence answered game=%s seq=%.0f"), *GameId, Seq));
             } else {
               GameSequenceState = EBootQuery::Failed;
               Trace(FString::Printf(TEXT("LOADING sequence failed game=%s: %s"), *GameId, Errors.Num() ? *Errors[0].Code : TEXT("no data")));
             }
           });
}

void FS08FlowController::RetryMatchLoad() {
  if (Stage != ES08Stage::Started || Room.GameId.IsEmpty()) return;
  Trace(FString::Printf(TEXT("LOADING retry game=%s"), *Room.GameId));
  FetchGameSequence();
  FetchGameState();
  // the stream: a dead socket waiting for its backoff reconnects in the next tick
  if (!IsStreamReady()) {
    WsReconnectBackoff = 1.0f;
    if (WsReconnectCountdown >= 0.0f || !Ws.IsValid()) WsReconnectCountdown = 0.01f;
  }
}

void FS08FlowController::DetachToLobby() {
  if (Room.GameId.IsEmpty()) return;
  Trace(FString::Printf(TEXT("LOADING detach to lobby game=%s (no leaveGame: the match stays IN_PROGRESS)"), *Room.GameId));
  Room = FS08RoomState();
  GameSequenceState = EBootQuery::Idle;
  // the maneuver draft stays (the same user may return to this match, MS-T-04)
  SetStage(ES08Stage::Lobby);
  TeardownGameStateStream();
}
