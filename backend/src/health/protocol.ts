/**
 * GD-053: the client <-> server protocol number. Bump it whenever a change of the GraphQL contract breaks an older
 * Unreal client; the client's twin is S08ClientProtocol in
 * unreal/Unmatched/Source/Unmatched/S08/S08Protocol.h (tools/s08/test_protocol_version.py keeps the two equal).
 * The client asks `serverInfo { protocol }` on its BOOT pass and stops with «Сервер другой версии» on a mismatch.
 */
export const SERVER_PROTOCOL = 1;
