// Adds extra query params to SYNTX get_model_info requests (from env SYNTX_EXTRA_Q, JSON).
// Needed because the syntx_mcp.cjs get-model-info schema does not expose every cost parameter:
// a plain quote for kling returns 400 ("mode is required" / "version is required for kling").
// Does not read or print auth. Only get_model_info URLs are touched; generation calls are unchanged.
//
// Usage (price quote, free, no generation):
//   SYNTX_EXTRA_Q='{"version":"2.5","native_audio":"false"}' \
//   NODE_OPTIONS='--require <repo>/tools/art/syntx_video_refs/patch.cjs' \
//   node C:/Users/ren/.claude/mcp-servers/clients/syntx_mcp.cjs get-model-info \
//     '{"ai_name":"kling","model_type":"kling_image2video","mode":"standart","video_duration":5}'
const extra = process.env.SYNTX_EXTRA_Q ? JSON.parse(process.env.SYNTX_EXTRA_Q) : null;
if (extra && typeof fetch === 'function') {
  const orig = fetch;
  globalThis.fetch = (url, opts) => {
    if (typeof url === 'string' && url.includes('/api/v2/get_model_info')) {
      const u = new URL(url);
      for (const [k, v] of Object.entries(extra)) u.searchParams.set(k, String(v));
      url = u.toString();
    }
    return orig(url, opts);
  };
}
