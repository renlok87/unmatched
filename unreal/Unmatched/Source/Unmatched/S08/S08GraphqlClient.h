// GD-028: minimal GraphQL-over-HTTP client for the S08 grey flow.
// POST /graphql with Authorization: Bearer <token>. GraphQL failures arrive
// as HTTP 200 + errors[] - surfaced as actionable FS08GraphQLError, never
// swallowed. No tokens are logged.
#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "S08Contracts.h"
#include "Interfaces/IHttpRequest.h"

class UNMATCHED_API FS08GraphqlClient {
public:
  using FResult = TFunction<void(bool bOk, const TArray<FS08GraphQLError>& Errors,
                                 TSharedPtr<FJsonObject> Data, const FString& RawBody)>;

  explicit FS08GraphqlClient(FString InBaseUrl);

  void SetAccessToken(const FString& InToken) { AccessToken = InToken; }
  bool HasAccessToken() const { return !AccessToken.IsEmpty(); }
  const FString& GetAccessToken() const { return AccessToken; }

  /** Executes one GraphQL document. Variables may be null. Returns the request
   *  (MS-T-06: the controller cancels a maneuver command at its 10 s deadline). */
  FHttpRequestPtr Execute(const FString& Query, const TSharedPtr<FJsonObject>& Variables, FResult OnDone);

private:
  FString BaseUrl;
  FString AccessToken;
};
