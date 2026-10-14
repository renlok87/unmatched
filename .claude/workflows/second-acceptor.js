export const meta = {
  name: 'second-acceptor',
  description: 'Second acceptor (Opus xhigh) for 3d-model-pipeline cards in the 8.0-8.4 band, strict output schema',
  whenToUse: '3d-model-pipeline acceptance-and-blender.md §8.5: a model, clip or concept card scored 8.0-8.4 needs an independent acceptor of another profile. args = {kind?: model|concept|anim, items: [{asset, evidence, label, prompt?}], schema: <contents of tools/art/acceptance/asset-acceptance-2.output-<kind>.schema.json>}; ready ASCII args: python tools/art/acceptance/_output_schema.py --workflow-args <kind> --item <ASSET_ID>=<evidence> (concept sheet: sheet_acceptance.py prepare-second)',
  phases: [{ title: 'Accept', detail: 'one independent Opus xhigh acceptor per card' }],
}
// Moved into the repo from the pilot session script (2026-10-14, research RA-11 / F102).
// The caller reads the strict OUTPUT schema (output-model / output-anim / output-concept) and passes it as args.schema,
// so optional fields come back as JSON null, not the string "null"; the launcher then writes card-2.json and runs
// validate_card.py --second as usual (finish_second.py takes this return value, a bare list, or {"result": [...]}).
// items[].prompt defaults to acceptor-prompt-2.md in the evidence dir.
// Card kind (C10, skill check run 2026-10-14): args.kind, else the schema's kind enum, else "model". The kind decides
// which frames the acceptor opens and which item ids the lists may hold; the rest of the task is the prompt file.
phase('Accept')
if (!args || !Array.isArray(args.items) || !args.items.length || !args.schema) {
  throw new Error('args = {kind?, items: [{asset, evidence, label, prompt?}], schema} required')
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
acceptor.profile = "Opus xhigh", acceptor.session_id = "workflow:${it.label}". Empty optional fields are JSON null (not the string "null"); known_issues/rework_fix_list item is only ${K.items}.
Return the card as structured output.`
  let card = await agent(prompt, { label: it.label, model: 'opus', effort: 'xhigh', schema: args.schema })
  if (!card) card = await agent(prompt, { label: it.label + '-retry', model: 'opus', effort: 'xhigh', schema: args.schema })
  return { asset: it.asset, evidence: it.evidence, card }
}))
return results
