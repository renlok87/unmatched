// M_UM_Figure_v2 core (Custom node "UM_V2_Core"; body of the generated function, returns the base colour).
// Architecture: docs/art-pipeline/material-library/README.md sections 3-6; this graph: m-um-figure-v2.md.
// Inputs  MatIDTex LUTTex (Texture2D, Load only), DetN DetRMH (Texture2DArray, SampleGrad), UV0 UV1 UseUV1,
//         P N0 (pre-skinned local position/normal through vertex interpolators), LocalUnitM, BCh Nh ORMh DyeMask Edge,
//         Team TeamDye TeamDyeGain RoughMin RoughMax DetailStrength WearStrength SheenStrength AOToBC Saturation
//         ValueLift DebugView MatIDOverride BakeFromLUT UseAccent TeamDyeCeiling
// Outputs (inout) Rough Metal Spec AO NormalTS Cloth Fuzz IsCloth DebugE
// Class 0 (legacy bake) repeats the v1 M_UM_Figure graph exactly: BC (TeamMask dye), ORM, hero normal.
// v2.1 (LDV-12): static switch UseTeamAccent. On (UseAccent = 1, DyeMask = TeamAccentTexture.R): the dye weight is the
// TeamAccent mask alone, for every class (teamDyeAllowed is a mask-authoring rule, not a shader gate), and
// TeamDyeCeiling > 0 caps the gain per team colour. Off (UseAccent = 0, DyeMask = TeamMaskTexture.R): the v2.0 path,
// TeamMask x teamDyeAllowed of the class, gain = TeamDyeGain (bit for bit as before).
const float3 LUMA = float3(0.2126, 0.7152, 0.0722);

// ---- class id: MatID R8, value = index * 16 + 8 (Load, no filtering; README section 3)
float mw, mh;
MatIDTex.GetDimensions(mw, mh);
int2 mp = clamp(int2(frac(UV0) * float2(mw, mh)), int2(0, 0), int2(mw, mh) - 1);
int id = int(floor(MatIDTex.Load(int3(mp, 0)).r * (255.0 / 16.0) + 1e-3));
if (MatIDOverride >= 0.0) { id = int(MatIDOverride + 0.5); }
id = clamp(id, 0, 15);

// ---- class parameters: LUT 16 x 16 RGBA16F, column = class, rows 0-9 (build_ue_inputs.py LUT_ROWS)
float4 L0 = LUTTex.Load(int3(id, 0, 0));
float4 L1 = LUTTex.Load(int3(id, 1, 0));
float4 L2 = LUTTex.Load(int3(id, 2, 0));
float4 L3 = LUTTex.Load(int3(id, 3, 0));
float4 L4 = LUTTex.Load(int3(id, 4, 0));
float4 L5 = LUTTex.Load(int3(id, 5, 0));
float4 L6 = LUTTex.Load(int3(id, 6, 0));
float4 L7 = LUTTex.Load(int3(id, 7, 0));
float4 L8 = LUTTex.Load(int3(id, 8, 0));
float4 L9 = LUTTex.Load(int3(id, 9, 0));

// ---- screen derivatives before any divergent branch (SampleGrad inside the branch)
float3 Pm = P * LocalUnitM;                       // pre-skinned position in metres of the object
float3 dPdx = ddx(Pm);
float3 dPdy = ddy(Pm);
float2 dU0x = ddx(UV0), dU0y = ddy(UV0);
float2 dU1x = ddx(UV1), dU1y = ddy(UV1);

float3 bc = BCh;
float3 nh = normalize(Nh);
float3 dts = float3(0.0, 0.0, 1.0);               // detail normal in the hero tangent space
float4 rmh = float4(0.5, 1.0, 0.5, 1.0);
float wear = 0.0;
Rough = 0.5; Metal = 0.0; Spec = 0.5; AO = ORMh.r; Cloth = 0.0; IsCloth = 0.0; Fuzz = float3(0.0, 0.0, 0.0);
NormalTS = Nh;
DebugE = float3(0.0, 0.0, 0.0);

// ---- team dye gain (LDV-13): TeamDyeGain, or with TeamAccent and TeamDyeCeiling > 0 the team-accent.md rule
// gain = min(0.8 / Y_p50, 0.9 / (maxChannel(team) x Y_p95)) = min(TeamDyeGain, TeamDyeCeiling / maxChannel(team)):
// one hero MI gives every team colour (MI TeamColor or CPD_TeamColor) its own gain
float gain = TeamDyeGain;
if (UseAccent > 0.5 && TeamDyeCeiling > 0.0)
{
    gain = min(TeamDyeGain, TeamDyeCeiling / max(max(Team.r, max(Team.g, Team.b)), 1e-3));
}
float dyeW = 0.0;

[branch] if (id == 0)
{
    // v1 path (M_UM_Figure): roughness range, ORM metallic, lerp(BC, team, TeamMask)
    Rough = lerp(RoughMin, RoughMax, ORMh.g);
    Metal = ORMh.b;
    float yl = dot(bc, LUMA);
    float3 teamed = lerp(bc * Team, Team * yl * gain, TeamDye);
    dyeW = DyeMask;
    bc = lerp(bc, teamed, dyeW);
}
else
{
    if (BakeFromLUT > 0.5) { bc = L0.rgb; }
    float3 Nn = normalize(N0);
    float tpm = L4.r;
    float slice = L4.b;
    float ns = L4.g * DetailStrength;
    // scale-free derivative frame (only directions / ratios are used)
    float ps = 1.0 / max(max(length(dPdx), length(dPdy)), 1e-20);
    float3 ex = dPdx * ps, ey = dPdy * ps;
    float3 dp2perp = cross(ey, Nn);
    float3 dp1perp = cross(Nn, ex);
    float3 p0;
    if (UseUV1 > 0.5)
    {
        // UV1 in metres (README section 5): tangent frame of UV1 from derivatives (cotangent frame, Schueler 2013),
        // so the UV1 charts may be rotated freely against UV0
        float2 uvD = UV1 * tpm;
        float2 n1 = DetN.SampleGrad(DetNSampler, float3(uvD, slice), dU1x * tpm, dU1y * tpm).rg * 2.0 - 1.0;
        rmh = DetRMH.SampleGrad(DetRMHSampler, float3(uvD, slice), dU1x * tpm, dU1y * tpm);
        float us = 1.0 / max(max(max(abs(dU1x.x), abs(dU1x.y)), max(abs(dU1y.x), abs(dU1y.y))), 1e-20);
        float3 T1 = dp2perp * (dU1x.x * us) + dp1perp * (dU1y.x * us);
        float3 B1 = dp2perp * (dU1x.y * us) + dp1perp * (dU1y.y * us);
        float inv1 = rsqrt(max(max(dot(T1, T1), dot(B1, B1)), 1e-30));
        p0 = normalize(Nn + ns * (n1.x * T1 + n1.y * B1) * inv1);
    }
    else
    {
        // fallback: triplanar on the pre-skinned local position (stable under skinning), UDN blend;
        // projection X: (u, v) = (y, z), Y: (x, z), Z: (x, y); DirectX tile: n.x along +u, n.y along +v (+row)
        float3 w = pow(abs(Nn), 4.0);
        w /= (w.x + w.y + w.z);
        float2 uX = Pm.yz * tpm, uY = Pm.xz * tpm, uZ = Pm.xy * tpm;
        float2 nX = DetN.SampleGrad(DetNSampler, float3(uX, slice), dPdx.yz * tpm, dPdy.yz * tpm).rg * 2.0 - 1.0;
        float2 nY = DetN.SampleGrad(DetNSampler, float3(uY, slice), dPdx.xz * tpm, dPdy.xz * tpm).rg * 2.0 - 1.0;
        float2 nZ = DetN.SampleGrad(DetNSampler, float3(uZ, slice), dPdx.xy * tpm, dPdy.xy * tpm).rg * 2.0 - 1.0;
        float4 rX = DetRMH.SampleGrad(DetRMHSampler, float3(uX, slice), dPdx.yz * tpm, dPdy.yz * tpm);
        float4 rY = DetRMH.SampleGrad(DetRMHSampler, float3(uY, slice), dPdx.xz * tpm, dPdy.xz * tpm);
        float4 rZ = DetRMH.SampleGrad(DetRMHSampler, float3(uZ, slice), dPdx.xy * tpm, dPdy.xy * tpm);
        float3 tang = w.x * float3(0.0, nX.x, nX.y) + w.y * float3(nY.x, 0.0, nY.y) + w.z * float3(nZ.x, nZ.y, 0.0);
        rmh = w.x * rX + w.y * rY + w.z * rZ;
        p0 = normalize(Nn + ns * tang);
    }
    // pre-skinned object-space normal -> hero tangent space (UV0 frame from derivatives, Gram-Schmidt against the
    // interpolated normal like the mesh tangent basis): X = grad u0, Y = grad v0 (UE, DirectX normal maps)
    float usc = 1.0 / max(max(max(abs(dU0x.x), abs(dU0x.y)), max(abs(dU0y.x), abs(dU0y.y))), 1e-20);
    float3 T0 = dp2perp * (dU0x.x * usc) + dp1perp * (dU0y.x * usc);
    float3 B0 = dp2perp * (dU0x.y * usc) + dp1perp * (dU0y.y * usc);
    float3 tt = T0 - Nn * dot(Nn, T0);
    float tl = dot(tt, tt);
    float3 Ta = tl > 1e-30 ? tt * rsqrt(tl) : normalize(cross(Nn, abs(Nn.z) < 0.9 ? float3(0.0, 0.0, 1.0) : float3(1.0, 0.0, 0.0)));
    float3 Bc = cross(Nn, Ta);
    float3 Ba = dot(Bc, B0) < 0.0 ? -Bc : Bc;
    dts = float3(dot(p0, Ta), dot(p0, Ba), dot(p0, Nn));
    // reoriented normal blend of the hero normal and the detail (BlendAngleCorrectedNormals)
    float3 t = nh + float3(0.0, 0.0, 1.0);
    float3 uu = dts * float3(-1.0, -1.0, 1.0);
    NormalTS = normalize(t * (dot(t, uu) / t.z) - uu);

    // roughness: typical + tile variation, clamped to the class range
    Rough = clamp(L1.r + (rmh.r - 0.5) * 2.0 * L1.a * DetailStrength, L1.g, L1.b);
    Metal = L0.a;
    Spec = L2.r;
    AO = ORMh.r * lerp(1.0, rmh.g, 0.5);
    float Y = dot(bc, LUMA);
    if (L2.a > 0.5)
    {
        // metal: preset F0, bake luminance only modulates (+-m around the class median of the hero bake)
        float m = L2.b;
        float ratio = L8.r > 0.0 ? clamp(Y / L8.r, 1.0 - m, 1.0 + m) : 1.0;
        bc = L0.rgb * ratio * lerp(1.0, rmh.g, L4.a);
    }
    else
    {
        // dielectric: hero bake clamped to the class luminance band and channel ceiling
        float y = max(Y, 1e-5);
        float yc = clamp(y, L7.r, L7.g);
        bc = Y > 1e-5 ? bc * (yc / y) : yc.xxx;
        bc = min(bc, L7.bbb);
        bc *= lerp(1.0, rmh.g, 0.35);
        float3 aoc = lerp(L9.rgb, float3(1.0, 1.0, 1.0), saturate(AO));   // skin: red cavities (subsurfaceApprox)
        bc *= lerp(float3(1.0, 1.0, 1.0), aoc, L9.a);
    }
    // TeamColor. UseTeamAccent on: the TeamAccent mask alone decides (any class). Off (v2.0): only classes with
    // teamDyeAllowed (cloth, leather, feathers), inside the hero TeamMask
    float yd = dot(bc, LUMA);
    float3 dyed = lerp(bc * Team, Team * yd * gain, TeamDye);
    dyeW = UseAccent > 0.5 ? DyeMask : DyeMask * L7.a;
    bc = lerp(bc, dyed, dyeW);
    // edge wear: hero convexity mask x class strength, broken up by the tile height, kept out of occlusion
    if (L5.r > 0.0)
    {
        wear = saturate(Edge * L5.r * 2.0 - (1.0 - rmh.b)) * WearStrength * smoothstep(0.3, 0.8, ORMh.r);
        float3 wbc = L6.a > 0.5 ? L6.rgb : min(bc * L5.a, L7.bbb);
        float wr = L5.g >= 0.0 ? L5.g : saturate(Rough + L5.b);
        bc = lerp(bc, wbc, wear);
        Rough = lerp(Rough, wr, wear);
    }
    IsCloth = L3.a;
    Cloth = L2.g;
}

// ---- hero-wide knobs of v1 (neutral defaults): AO into BC, saturation, value lift
bc *= lerp(1.0, ORMh.r, AOToBC);
float yk = dot(bc, LUMA);
bc = lerp(yk.xxx, bc, Saturation);
bc = lerp(bc, float3(1.0, 1.0, 1.0), ValueLift);

// ---- cloth sheen (Fuzz Color) from the final albedo: intensity x tint x sqrt(Y)  (README section 4)
if (IsCloth > 0.5)
{
    float yb = max(dot(bc, LUMA), 1e-4);
    Fuzz = L3.r * SheenStrength * lerp(float3(1.0, 1.0, 1.0), bc / yb, L3.g) * sqrt(yb);
}

// ---- debug views (MI DebugView): emissive only, the surface goes black
if (DebugView > 0.5)
{
    int dv = int(DebugView + 0.5);
    float3 v = float3(0.0, 0.0, 0.0);
    if (dv == 1)
    {
        float h = frac(float(id) * 0.618034);
        float3 hue = saturate(abs(frac(h + float3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0) - 1.0);
        v = id == 0 ? float3(0.02, 0.02, 0.02) : lerp(float3(1.0, 1.0, 1.0), hue, 0.75) * 0.95;
    }
    else if (dv == 2) { v = Rough.xxx; }
    else if (dv == 3) { v = Metal.xxx; }
    else if (dv == 4) { v = dts * 0.5 + 0.5; }
    else if (dv == 5) { v = wear.xxx; }
    else if (dv == 6) { v = NormalTS * 0.5 + 0.5; }
    else if (dv == 7) { v = bc; }
    else if (dv == 8) { v = Fuzz; }
    else if (dv == 9) { v = rmh.rgb; }
    else if (dv == 10) { v = dyeW.xxx; }
    DebugE = v;
    bc = float3(0.0, 0.0, 0.0); Metal = 0.0; Spec = 0.0; Rough = 1.0; IsCloth = 0.0; Cloth = 0.0;
    Fuzz = float3(0.0, 0.0, 0.0);
}
return bc;
