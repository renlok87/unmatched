// GD-053: the client <-> server protocol number. Twin of SERVER_PROTOCOL in backend/src/health/protocol.ts
// (tools/s08/test_protocol_version.py keeps the two equal). Bump both when a GraphQL contract change
// breaks an older client. The BOOT pass asks `serverInfo { protocol }` and stops with «Сервер другой версии» on a
// mismatch instead of failing later with contract errors.
#pragma once

#include "CoreMinimal.h"

inline constexpr int32 S08ClientProtocol = 1;
