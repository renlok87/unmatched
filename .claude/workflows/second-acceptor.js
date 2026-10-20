export const meta = {
  name: 'second-acceptor',
  description: 'Opus acceptor for 3d-model-pipeline cards, strict output schema: the first acceptor "Opus xhigh" (effort xhigh, the default since Sol was switched off 2026-10-20) and the second acceptor of another profile "Opus high" (effort high, user decision 2026-10-21) for a card scored 8.0-8.4',
  whenToUse: '3d-model-pipeline acceptance-and-blender.md §8.3/§8.5: the first acceptor of a model, clip or concept card ("Opus xhigh", effort xhigh; Sol switched off 2026-10-20) and the independent second acceptor of a card scored 8.0-8.4 ("Opus high", effort high; Z-Code failed its calibration 2026-10-21, AGENTS.md "AI tools and side models"). args = {kind?: model|concept|anim, effort?: xhigh|high, profile?: "Opus xhigh"|"Opus high", items: [{asset, evidence, label, prompt?}], schema: <contents of tools/art/acceptance/asset-acceptance-2.output-<kind>.schema.json>}; without effort and profile: xhigh / "Opus xhigh". Ready ASCII args: python tools/art/acceptance/_output_schema.py --workflow-args <kind> [--first] --item <ASSET_ID>=<evidence> (--first: "Opus xhigh"; without it the second acceptor "Opus high", effort high); concept sheet: sheet_acceptance.py prepare / prepare-second; clips: run_clip_acceptors.py [--second]',
  phases: [{ title: 'Accept', detail: 'one independent Opus acceptor per card: effort xhigh (first) or high (second)' }],
}
// Moved into the repo from the pilot session script (2026-10-14, research RA-11 / F102).
// The caller reads the strict OUTPUT schema (output-model / output-anim / output-concept) and passes it as args.schema,
// so optional fields come back as JSON null, not the string "null"; the launcher then writes card.json / card-2.json and
// runs validate_card.py as usual (finish_second.py takes this return value, a bare list, or {"result": [...]}).
// items[].prompt defaults to acceptor-prompt-2.md in the evidence dir.
// Card kind (C10, skill check run 2026-10-14): args.kind, else the schema's kind enum, else "model". The kind decides
// which frames the acceptor opens and which item ids the lists may hold; the rest of the task is the prompt file.
// Profile (user decision 2026-10-21, «Хорошо, использую Opus High вместо Z-код для приемщика»): args.effort or
// args.profile; "high" / "Opus high" is the second acceptor of another profile, "xhigh" / "Opus xhigh" (the default)
// the first one. The same effort goes to the retry.
phase('Accept')
if (!args || !Array.isArray(args.items) || !args.items.length || !args.schema) {
  throw new Error('args = {kind?, effort?, profile?, items: [{asset, evidence, label, prompt?}], schema} required')
}
const KINDS = {
  model: {
    frames: ev => `Open every frame listed in ${ev}/frames/frames.json#files with the Read tool, each in full, and judge it.`,
    items: 'one letter S, F, T or D, or a gate id G-TOPO, G-UV, G-TEX, G-RIG, G-NAMES',
  },
  concept: {
    frames: ev => 'The images are not attached: open every image the prompt file lists (the three views, the sheet, the approved design, the 1b orthos, the quality reference) with the Read tool, each in full, and judge it.',
    items: 'one letter S, C, Q or P, or the gate id G-CHECKS',
  },
  anim: {
    frames: ev => `Open every file of frames.files named in the prompt file (frames.dir, ${ev}/frames) with the Read tool, each in full, and judge it.`,
    items: 'one letter R, C, D or L, or a gate id G-VALIDATE, G-CONTACT, G-MANIFEST',
  },
}
const PROFILE_OF = { xhigh: 'Opus xhigh', high: 'Opus high' }
const EFFORT_OF = { 'Opus xhigh': 'xhigh', 'Opus high': 'high' }
if (args.effort && !PROFILE_OF[args.effort]) throw new Error(`unknown args.effort ${args.effort}: xhigh | high`)
if (args.profile && !EFFORT_OF[args.profile]) throw new Error(`unknown args.profile ${args.profile}: "Opus xhigh" | "Opus high"`)
const effort = args.effort || EFFORT_OF[args.profile] || 'xhigh'
const profile = PROFILE_OF[effort]
if (args.profile && args.profile !== profile) throw new Error(`args.profile ${args.profile} does not match args.effort ${effort}`)
const schemaKind = (((args.schema.properties || {}).kind || {}).enum || [])[0]
const kind = args.kind || schemaKind || 'model'
if (!KINDS[kind]) throw new Error(`unknown card kind ${kind}: model | concept | anim`)
if (schemaKind && schemaKind !== kind) throw new Error(`args.kind ${kind} does not match the schema kind ${schemaKind}`)
const K = KINDS[kind]
const results = await parallel(args.items.map(it => async () => {
  const promptFile = it.prompt || `${it.evidence}/acceptor-prompt-2.md`
  const prompt = `You are an independent acceptor for the 3d-model-pipeline skill in the current repository (card kind: ${kind}).
User delegation, verbatim (2026-10-06): «Не знаю. Делай сам, меня это не касается. Все решения принимай». No spending.
Read the file ${promptFile} (repo-relative) with the Read tool and follow it exactly: it is your full task.
Do not read card.json, card-2.json, final.json or any acceptor-* file in ${it.evidence} other than the prompt file. Do not write or edit any file. Do not run scripts.
${K.frames(it.evidence)} Score = round(sum/(2*n)*10, 1) per the rubric.
acceptor.profile = "${profile}", acceptor.session_id = "workflow:${it.label}". Empty optional fields are JSON null (not the string "null"); known_issues/rework_fix_list item is only ${K.items}.
Return the card as structured output.`
  let card = await agent(prompt, { label: it.label, model: 'opus', effort, schema: args.schema })
  if (!card) card = await agent(prompt, { label: it.label + '-retry', model: 'opus', effort, schema: args.schema })
  return { asset: it.asset, evidence: it.evidence, effort, card }
}))
return results
