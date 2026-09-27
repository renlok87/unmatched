#include "S08GraphqlClient.h"
#include "S08Contracts.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

FS08GraphqlClient::FS08GraphqlClient(FString InBaseUrl) : BaseUrl(MoveTemp(InBaseUrl)) {}

void FS08GraphqlClient::Execute(const FString& Query, const TSharedPtr<FJsonObject>& Variables,
                                FResult OnDone) {
  TSharedRef<FJsonObject> RequestBody = MakeShared<FJsonObject>();
  RequestBody->SetStringField(TEXT("query"), Query);
  if (Variables.IsValid()) {
    RequestBody->SetObjectField(TEXT("variables"), Variables);
  }
  FString Serialized;
  TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Serialized);
  FJsonSerializer::Serialize(RequestBody, Writer);

  TSharedRef<IHttpRequest> Request = FHttpModule::Get().CreateRequest();
  Request->SetURL(BaseUrl);
  Request->SetVerb(TEXT("POST"));
  Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
  if (!AccessToken.IsEmpty()) {
    Request->SetHeader(TEXT("Authorization"), TEXT("Bearer ") + AccessToken);
  }
  Request->SetContentAsString(Serialized);
  Request->OnProcessRequestComplete().BindLambda(
      [OnDone = MoveTemp(OnDone)](FHttpRequestPtr, FHttpResponsePtr Response, bool bSucceeded) {
        if (!bSucceeded || !Response.IsValid()) {
          TArray<FS08GraphQLError> Errors;
          Errors.Add({TEXT("TRANSPORT"), TEXT("Network request failed - backend unreachable"), FString()});
          OnDone(false, Errors, nullptr, FString());
          return;
        }
        const int32 StatusCode = Response->GetResponseCode();
        const FString Body = Response->GetContentAsString();
        if (StatusCode != 200) {
          // GD-038: the HTTP status is part of the error contract - 401 (the
          // guard rejected the token) and 429 (throttled) drive the auth /
          // no-blind-retry recovery paths in the controller; 5xx means the
          // request outcome is UNKNOWN (a mutation may have been applied).
          const TCHAR* Code = StatusCode == 401   ? TEXT("AUTH")
                              : StatusCode == 429 ? TEXT("RATE_LIMIT")
                                                  : TEXT("TRANSPORT");
          TArray<FS08GraphQLError> Errors;
          Errors.Add({Code,
                      FString::Printf(TEXT("HTTP %d from server"), StatusCode), FString(),
                      StatusCode});
          OnDone(false, Errors, nullptr, Body);
          return;
        }
        TSharedPtr<FJsonObject> Root;
        FString Problem;
        if (!FS08Contracts::TryParseJsonObject(Body, Root, Problem)) {
          TArray<FS08GraphQLError> Errors;
          Errors.Add({TEXT("PARSE"),
                      FString::Printf(TEXT("Response is not valid JSON (%s)"), *Problem),
                      FString()});
          OnDone(false, Errors, nullptr, Body);
          return;
        }
        TArray<FS08GraphQLError> Errors;
        const bool HasGraphQLErrors = FS08Contracts::ExtractGraphQLErrors(Root.ToSharedRef(), Errors);
        const TSharedPtr<FJsonObject>* Data = nullptr;
        Root->TryGetObjectField(TEXT("data"), Data);
        OnDone(!HasGraphQLErrors, Errors, Data ? *Data : nullptr, Body);
      });
  Request->ProcessRequest();
}
