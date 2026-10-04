// M_UM_Figure_v2 dissolve (v2.3, DE-011 / W-27, 01 F-09; Custom node "UM_V2_Dissolve", body of the generated
// function, returns the opacity mask: 1 = keep, 0 = clip). Compiled only in the UseDissolve permutation (static switch,
// default off): the dissolve MICs (Masked override) a dying figure gets for its last 500 ms (hero) / 400 ms (sidekick).
// Inputs  P (pre-skinned local position, uu, through the vertex interpolator of the core), LocalUnitM, Progress
//         (CPD_Dissolve 0..1), Style (CPD_DissolveStyle: 0 = simple fade, 1 = team-colour ash), Team (team colour),
//         EdgeWidth, NoiseScale (noise cells per metre), HeightBias (0 = noise only, 1 = height only), HeightUU
// Outputs (inout) Edge (0..1, ash only: the burning front), TeamHue (team colour at full brightness)
// Progress 0 keeps every pixel (no edge either); Progress 1 clips every pixel, in both styles.
float p = saturate(Progress);
float maxc = max(max(Team.r, Team.g), max(Team.b, 1e-3));
TeamHue = Team / maxc;
Edge = 0.0;

// ---- simple fade (default; reduced motion): screen-space dither, interleaved gradient noise that moves every frame,
// so temporal AA / TSR resolves it into a smooth fade (the DitherTemporalAA idea)
float2 px = Parameters.SvPosition.xy + 5.588238 * float(View.StateFrameIndexMod8);
float ign = frac(52.9829189 * frac(dot(px, float2(0.06711056, 0.00583715))));
float keepFade = (1.0 - p) > ign ? 1.0 : 0.0;

// ---- ash: a 3D value-noise field (two octaves) on the pre-skinned position (it does not swim with the animation),
// biased by the height above the pedestal (the figure burns away from the feet up); a band of EdgeWidth in front of
// the threshold glows in the team colour. The lattice is rotated off the mesh axes (a fixed orthonormal matrix, again
// between the octaves), so the value-noise cells do not line up with the figure as squares
const float3x3 ROT = float3x3(0.00, 0.80, 0.60, -0.80, 0.36, -0.48, -0.60, -0.48, 0.64);
float3 q = mul(ROT, P * LocalUnitM * NoiseScale);
float n = 0.0;
float amp = 0.65;
for (int oct = 0; oct < 2; oct++) {
  float3 i = floor(q);
  float3 f = frac(q);
  float3 s = f * f * (3.0 - 2.0 * f);
  float v = 0.0;
  for (int c = 0; c < 8; c++) {
    float3 o = float3(c & 1, (c >> 1) & 1, (c >> 2) & 1);
    float h = frac(sin(dot(i + o, float3(127.1, 311.7, 74.7))) * 43758.5453);
    float3 w = lerp(1.0 - s, s, o);
    v += h * w.x * w.y * w.z;
  }
  n += amp * v;
  q = mul(ROT, q) * 2.31 + 17.0;
  amp = 0.35;
}
float field = lerp(n, saturate(P.z / max(HeightUU, 1e-3)), saturate(HeightBias));
float w = max(EdgeWidth, 1e-3);
float t = p * (1.0 + w + 0.01) - w;
float keepAsh = field > t ? 1.0 : 0.0;
if (Style > 0.5) {
  Edge = keepAsh * (p > 0.0 ? 1.0 - saturate((field - t) / w) : 0.0);
  return keepAsh;
}
return keepFade;
