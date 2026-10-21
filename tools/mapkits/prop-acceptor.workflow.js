export const meta = {
  name: 'mapkit-prop-acceptor',
  description: 'Map-kit prop acceptance: second-acceptor logic with the model output schema embedded (args = {effort: xhigh|high, items: [{asset, evidence, label, prompt}]})',
  phases: [{ title: 'Accept', detail: 'one independent Opus acceptor per prop card' }],
}
// Copy of .claude/workflows/second-acceptor.js (2026-10-21) for tools/mapkits/accept.py: the strict model output schema
// (tools/art/acceptance/asset-acceptance-2.output-model.schema.json, descriptions stripped) is embedded so the caller
// passes only {effort, items}.
const MODEL_SCHEMA = {"type": "object", "properties": {"schema": {"type": "string", "enum": ["unmatched.asset-acceptance/2"]}, "kind": {"type": "string", "enum": ["model"]}, "asset_id": {"type": "string", "pattern": "^ASSET-[A-Z0-9]+(-[A-Z0-9]+)*-[0-9]{3}$"}, "clip": {"type": "null"}, "cycle": {"type": "string", "enum": ["r1", "r2", "r3", "r4"]}, "date": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"}, "previous_card": {"type": ["string", "null"]}, "accepted_object": {"type": "array", "items": {"type": "object", "properties": {"path": {"type": "string"}, "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}, "required": ["path", "sha256"], "additionalProperties": false}}, "frames": {"type": "object", "properties": {"dir": {"type": "string"}, "files": {"type": "array", "items": {"type": "string", "pattern": "^[A-Za-z0-9._-]+\\.(jpg|png|json)$"}}}, "required": ["dir", "files"], "additionalProperties": false}, "reports": {"type": "array", "items": {"type": "string"}}, "gates": {"type": "object", "properties": {"G-TOPO": {"type": "object", "properties": {"status": {"type": "string", "enum": ["PASS", "FAIL", "n/a"]}, "source": {"type": "string"}, "note": {"type": ["string", "null"]}, "source_defect": {"type": ["boolean", "null"]}}, "required": ["status", "source", "note", "source_defect"], "additionalProperties": false}, "G-UV": {"type": "object", "properties": {"status": {"type": "string", "enum": ["PASS", "FAIL", "n/a"]}, "source": {"type": "string"}, "note": {"type": ["string", "null"]}, "source_defect": {"type": ["boolean", "null"]}}, "required": ["status", "source", "note", "source_defect"], "additionalProperties": false}, "G-TEX": {"type": "object", "properties": {"status": {"type": "string", "enum": ["PASS", "FAIL", "n/a"]}, "source": {"type": "string"}, "note": {"type": ["string", "null"]}, "source_defect": {"type": ["boolean", "null"]}}, "required": ["status", "source", "note", "source_defect"], "additionalProperties": false}, "G-RIG": {"type": "object", "properties": {"status": {"type": "string", "enum": ["PASS", "FAIL", "n/a"]}, "source": {"type": "string"}, "note": {"type": ["string", "null"]}, "source_defect": {"type": ["boolean", "null"]}}, "required": ["status", "source", "note", "source_defect"], "additionalProperties": false}, "G-NAMES": {"type": "object", "properties": {"status": {"type": "string", "enum": ["PASS", "FAIL", "n/a"]}, "source": {"type": "string"}, "note": {"type": ["string", "null"]}, "source_defect": {"type": ["boolean", "null"]}}, "required": ["status", "source", "note", "source_defect"], "additionalProperties": false}}, "required": ["G-TOPO", "G-UV", "G-TEX", "G-RIG", "G-NAMES"], "additionalProperties": false}, "scores": {"type": "object", "properties": {"S": {"type": "object", "properties": {"value": {"type": "number"}, "rationale": {"type": "string"}, "frames": {"type": "array", "items": {"type": "string"}}}, "required": ["value", "rationale", "frames"], "additionalProperties": false}, "F": {"type": "object", "properties": {"value": {"type": "number"}, "rationale": {"type": "string"}, "frames": {"type": "array", "items": {"type": "string"}}}, "required": ["value", "rationale", "frames"], "additionalProperties": false}, "T": {"type": "object", "properties": {"value": {"type": "number"}, "rationale": {"type": "string"}, "frames": {"type": "array", "items": {"type": "string"}}}, "required": ["value", "rationale", "frames"], "additionalProperties": false}, "D": {"type": "object", "properties": {"value": {"type": ["number", "null"]}, "rationale": {"type": "string"}, "frames": {"type": "array", "items": {"type": "string"}}}, "required": ["value", "rationale", "frames"], "additionalProperties": false}}, "required": ["S", "F", "T", "D"], "additionalProperties": false}, "score": {"type": "number"}, "verdict": {"type": "string", "enum": ["pass", "rework_blender", "return_to_stage_1", "return_to_stage_2", "escalate_user"]}, "verdict_reason": {"type": ["string", "null"]}, "rework_fix_list": {"type": "array", "items": {"type": "object", "properties": {"item": {"type": "string", "pattern": "^([SFTDCQPRL]|G-[A-Z]+)$"}, "frame": {"type": "string"}, "fix": {"type": "string"}, "tool": {"type": "string"}}, "required": ["item", "frame", "fix", "tool"], "additionalProperties": false}}, "known_issues": {"type": "array", "items": {"type": "object", "properties": {"item": {"type": "string", "pattern": "^([SFTDCQPRL]|G-[A-Z]+)$"}, "frame": {"type": "string"}, "note": {"type": "string"}}, "required": ["item", "frame", "note"], "additionalProperties": false}}, "acceptor": {"type": "object", "properties": {"profile": {"type": "string", "enum": ["Opus xhigh", "Opus high"]}, "session_id": {"type": "string"}}, "required": ["profile", "session_id"], "additionalProperties": false}, "executor_session_id": {"type": "string"}, "decided_by": {"type": "string"}, "status_note": {"type": "string"}}, "required": ["schema", "kind", "asset_id", "clip", "cycle", "date", "previous_card", "accepted_object", "frames", "reports", "gates", "scores", "score", "verdict", "verdict_reason", "rework_fix_list", "known_issues", "acceptor", "executor_session_id", "decided_by", "status_note"], "additionalProperties": false}
args.kind = 'model'
args.schema = MODEL_SCHEMA
phase('Accept')
if (!args || !Array.isArray(args.items) || !args.items.length || !args.schema) {
  throw new Error('args = {kind?, effort?, profile?, items: [{asset, evidence, label, prompt?}], schema} required')
}
const KINDS = {
  model: {
    frames: ev => `Open with the Read tool, each in full, the frames the prompt file names in its «Входы» section (directory ${ev}/frames) and judge them; other frames.json#files you may open only if you need them.`,
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
