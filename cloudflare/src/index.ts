import { CAPTURE_FLOW_CONTRACT } from "./capture_flow_contract";
import { FORM_CONTRACT } from "./form_contract";

export interface Env {
  ASSETS: Fetcher;
  T5_MEDIA: R2Bucket;
  CLIENT_API_TOKEN: string;
  GITHUB_TOKEN: string;
  GITHUB_OWNER: string;
  GITHUB_REPO: string;
  GITHUB_API_BASE: string;
  CALLBACK_TOKEN: string;
  PUBLIC_API_BASE: string;
}

type CaptureSlot = "S1" | "S2" | "S3" | "S4";
type JobStatus = "UPLOADING" | "READY" | "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";

interface MerchantPayload {
  nom: string;
  offre: string;
  contenu: string;
  prix: string;
  whatsapp: string;
  quartier: string;
}

interface CaptureMeta {
  uri: string;
  sha256: string;
  mime_type: string;
  width: number;
  height: number;
  fps: number;
  frame_count: number;
  duration_ms: number;
  source_in_ms: number;
  video_codec: string;
  audio_codec: string | null;
  has_audio: boolean;
}

interface StoredOutput {
  uri: string;
  sha256: string;
  bytes: number;
  mime_type: "video/mp4";
}

interface StoredJob {
  status: JobStatus;
  job_id: string;
  idempotency_key: string;
  created_at: string;
  updated_at: string;
  merchant_payload: MerchantPayload;
  captures: Partial<Record<CaptureSlot, CaptureMeta>>;
  job?: Record<string, unknown>;
  github?: Record<string, unknown>;
  output?: StoredOutput;
  result?: unknown;
  error?: unknown;
}

const SLOTS: CaptureSlot[] = ["S1", "S2", "S3", "S4"];
const FIELDS = ["nom", "offre", "contenu", "prix", "whatsapp", "quartier"] as const;
const DURATIONS: Record<CaptureSlot, number> = { S1: 6000, S2: 8000, S3: 7000, S4: 9000 };
const ALLOWED_MIME = new Set(["video/mp4", "video/webm", "video/quicktime"]);
const MAX_CAPTURE_BYTES = 250 * 1024 * 1024;
const MAX_OUTPUT_BYTES = 500 * 1024 * 1024;
const OUTPUT_FILE = "VIDEO_T5_FORMULE_RUNTIME_DYNAMIQUE_V2_A_VALIDER.mp4";

function json(data: unknown, status = 200): Response {
  return Response.json(data, { status, headers: { "cache-control": "no-store" } });
}

function fail(status: number, code: string, message: string, retryable = false): Response {
  return json({ schema_version: "1.0.0", status: "FAILED", code, message, retryable }, status);
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function clean(value: unknown, name: string, max: number, min = 1): string {
  if (typeof value !== "string") throw new Error(`${name} doit être une chaîne.`);
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length < min || normalized.length > max) {
    throw new Error(`${name} doit contenir entre ${min} et ${max} caractères.`);
  }
  return normalized;
}

function validatePayload(raw: unknown): MerchantPayload {
  const value = record(raw);
  if (!value) throw new Error("merchant_payload est requis.");
  const known = new Set(FIELDS);
  if (Object.keys(value).some((key) => !known.has(key as typeof FIELDS[number]))) {
    throw new Error("merchant_payload contient un champ non autorisé.");
  }
  const payload: Record<string, string> = {};
  for (const field of FORM_CONTRACT.fields) {
    payload[field.id] = clean(value[field.id], field.id, field.maxLength, field.minLength);
  }
  return payload as unknown as MerchantPayload;
}

function validId(value: string): boolean {
  return /^[a-zA-Z0-9][a-zA-Z0-9._-]{7,127}$/.test(value);
}

function jobKey(jobId: string): string { return `jobs/${jobId}/state.json`; }
function idemKey(key: string): string { return `idempotency/${key}.txt`; }
function captureKey(jobId: string, slot: CaptureSlot): string { return `jobs/${jobId}/captures/${slot}.bin`; }
function outputKey(jobId: string): string { return `jobs/${jobId}/output/final.mp4`; }
function outputUri(jobId: string): string { return `output/runtime/${jobId}/${OUTPUT_FILE}`; }

function canonicalStringify(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalStringify).join(",")}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonicalStringify(object[key])}`).join(",")}}`;
}

async function sha256Text(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function readJob(env: Env, jobId: string): Promise<StoredJob | null> {
  const object = await env.T5_MEDIA.get(jobKey(jobId));
  return object ? await object.json<StoredJob>() : null;
}

async function writeJob(env: Env, state: StoredJob): Promise<void> {
  state.updated_at = new Date().toISOString();
  await env.T5_MEDIA.put(jobKey(state.job_id), JSON.stringify(state), {
    httpMetadata: { contentType: "application/json" },
    customMetadata: { status: state.status, idempotency_key: state.idempotency_key },
  });
}

async function authorized(request: Request, secret: string): Promise<boolean> {
  const header = request.headers.get("authorization") || "";
  return secret.length > 0 && header === `Bearer ${secret}`;
}

async function clientOrCallbackAuthorized(request: Request, env: Env): Promise<boolean> {
  return await authorized(request, env.CLIENT_API_TOKEN) || await authorized(request, env.CALLBACK_TOKEN);
}

function runtimeCaptureUri(jobId: string, slot: CaptureSlot, mime: string): string {
  const extension = mime === "video/webm" ? "webm" : mime === "video/quicktime" ? "mov" : "mp4";
  return `rushes/runtime/${jobId}/${slot}.${extension}`;
}

function buildRenderJob(state: StoredJob): Record<string, unknown> {
  const captures = Object.fromEntries(SLOTS.map((slot) => {
    const capture = state.captures[slot];
    if (!capture) throw new Error(`Capture ${slot} absente.`);
    return [slot, capture];
  }));
  return {
    schema_version: "1.0.0",
    job_id: state.job_id,
    idempotency_key: state.idempotency_key,
    template_id: "RESTAURATION-T5",
    template_version: "2.0.0-runtime",
    merchant_payload: state.merchant_payload,
    captures,
    render: {
      visual_mode: "runtime_hybrid_render",
      runtime_capture_manifest_required: true,
      render_business_text: true,
      business_text_source: "merchant_payload",
      runtime_contract: "config/T5_RUNTIME_CONTRACT_V2_0_0.json",
      transition_reference: "T1",
      width: 720,
      height: 1280,
      fps: 30,
      frames: 900,
      duration_s: 30.0,
      scene_durations_s: [6, 8, 7, 9],
      audio_mode: "silent_no_audio_stream",
      production_render_plane: "github_actions",
    },
    output: { uri: outputUri(state.job_id), filename: OUTPUT_FILE },
    control_plane: "cloudflare_worker",
    cloudflare_rendering_forbidden: true,
  };
}

async function createJob(request: Request, env: Env): Promise<Response> {
  const body = await request.json<Record<string, unknown>>();
  const idempotencyKey = clean(request.headers.get("idempotency-key") || body.idempotency_key, "idempotency_key", 120);
  if (!validId(idempotencyKey)) return fail(400, "T5_INVALID_IDEMPOTENCY_KEY", "Clé d'idempotence invalide.");
  const existing = await env.T5_MEDIA.get(idemKey(idempotencyKey));
  if (existing) {
    const existingId = await existing.text();
    const state = await readJob(env, existingId);
    return json({ job_id: existingId, status: state?.status, idempotent_replay: true });
  }
  const merchant = validatePayload(body.merchant_payload);
  const seed = `${idempotencyKey}\n${canonicalStringify(merchant)}\n${Date.now()}\n${crypto.randomUUID()}`;
  const jobId = `t5-runtime-${(await sha256Text(seed)).slice(0, 24)}`;
  const now = new Date().toISOString();
  const state: StoredJob = {
    status: "UPLOADING", job_id: jobId, idempotency_key: idempotencyKey,
    created_at: now, updated_at: now, merchant_payload: merchant, captures: {},
  };
  await writeJob(env, state);
  const claim = await env.T5_MEDIA.put(idemKey(idempotencyKey), jobId, {
    onlyIf: { etagDoesNotMatch: "*" },
    httpMetadata: { contentType: "text/plain" },
  });
  if (!claim) {
    await env.T5_MEDIA.delete(jobKey(jobId));
    const winner = await env.T5_MEDIA.get(idemKey(idempotencyKey));
    if (!winner) return fail(503, "T5_IDEMPOTENCY_RACE", "La réservation idempotente doit être rejouée.", true);
    const existingId = await winner.text();
    const existingState = await readJob(env, existingId);
    return json({ job_id: existingId, status: existingState?.status, idempotent_replay: true });
  }
  return json({ job_id: jobId, status: state.status, required_captures: SLOTS, capture_contract: "/v1/contracts/capture-flow" }, 201);
}

async function uploadCapture(request: Request, env: Env, jobId: string, slot: CaptureSlot): Promise<Response> {
  const state = await readJob(env, jobId);
  if (!state) return fail(404, "T5_JOB_NOT_FOUND", "Job introuvable.");
  if (!["UPLOADING", "READY"].includes(state.status)) return fail(409, "T5_CAPTURE_PHASE_CLOSED", "Les captures ne peuvent plus être modifiées.");
  const mime = (request.headers.get("content-type") || "").split(";", 1)[0].toLowerCase();
  if (!ALLOWED_MIME.has(mime)) return fail(415, "T5_UNSUPPORTED_MEDIA", "Conteneur vidéo non pris en charge.");
  const length = Number(request.headers.get("content-length") || 0);
  if (length <= 0 || length > MAX_CAPTURE_BYTES) return fail(413, "T5_MEDIA_SIZE_INVALID", "Taille de capture invalide.");
  const sha = (request.headers.get("x-content-sha256") || "").toLowerCase();
  if (!/^[a-f0-9]{64}$/.test(sha)) return fail(400, "T5_MISSING_MEDIA_SHA256", "x-content-sha256 est requis.");
  const width = Number(request.headers.get("x-video-width"));
  const height = Number(request.headers.get("x-video-height"));
  const fps = Number(request.headers.get("x-video-fps"));
  const frames = Number(request.headers.get("x-video-frames"));
  const duration = Number(request.headers.get("x-video-duration-ms"));
  const hasAudio = request.headers.get("x-has-audio") === "true";
  if (
    ![width, height, fps, frames, duration].every(Number.isFinite)
    || width < 320 || height < 320 || fps < 12 || fps > 120
    || !Number.isInteger(frames) || frames < 1
    || Math.abs(duration - DURATIONS[slot]) > 1000
  ) return fail(422, "T5_INVALID_MEDIA_METADATA", "Métadonnées vidéo incompatibles avec la scène.");
  if (!request.body) return fail(400, "T5_EMPTY_MEDIA", "Corps vidéo absent.");
  const object = await env.T5_MEDIA.put(captureKey(jobId, slot), request.body, {
    sha256: sha,
    httpMetadata: { contentType: mime },
    customMetadata: { job_id: jobId, slot },
  });
  if (object.size > MAX_CAPTURE_BYTES) {
    await env.T5_MEDIA.delete(captureKey(jobId, slot));
    return fail(413, "T5_MEDIA_TOO_LARGE", "La capture dépasse 250 Mio.");
  }
  if (!object.checksums.sha256) return fail(500, "T5_R2_CHECKSUM_MISSING", "R2 n'a pas confirmé le checksum.", true);
  const actualSha = [...new Uint8Array(object.checksums.sha256)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  if (actualSha !== sha) {
    await env.T5_MEDIA.delete(captureKey(jobId, slot));
    return fail(422, "T5_MEDIA_CHECKSUM_MISMATCH", "Le contenu reçu ne correspond pas à son SHA-256.");
  }
  state.captures[slot] = {
    uri: runtimeCaptureUri(jobId, slot, mime), sha256: actualSha, mime_type: mime,
    width, height, fps, frame_count: frames, duration_ms: Math.round(duration), source_in_ms: 0,
    video_codec: clean(request.headers.get("x-video-codec") || "browser_mediarecorder", "video_codec", 30),
    audio_codec: hasAudio ? clean(request.headers.get("x-audio-codec") || "browser_audio", "audio_codec", 30) : null,
    has_audio: hasAudio,
  };
  state.status = SLOTS.every((name) => Boolean(state.captures[name])) ? "READY" : "UPLOADING";
  await writeJob(env, state);
  return json({ job_id: jobId, slot, status: state.status, sha256: actualSha }, 201);
}

async function dispatch(request: Request, env: Env, jobId: string): Promise<Response> {
  const state = await readJob(env, jobId);
  if (!state) return fail(404, "T5_JOB_NOT_FOUND", "Job introuvable.");
  if (["QUEUED", "RUNNING", "COMPLETED"].includes(state.status)) {
    return json({ job_id: jobId, status: state.status, idempotent_replay: true });
  }
  const retrying = state.status === "FAILED" && record(state.error)?.code === "T5_GITHUB_DISPATCH_FAILED";
  if ((!retrying && state.status !== "READY") || !SLOTS.every((slot) => state.captures[slot])) {
    return fail(409, "T5_CAPTURES_INCOMPLETE", "Les quatre captures acceptées sont requises.");
  }
  state.job = buildRenderJob(state);
  state.status = "QUEUED";
  await writeJob(env, state);
  const githubApi = (env.GITHUB_API_BASE || "https://api.github.com").replace(/\/$/, "");
  let response: Response;
  try {
    response = await fetch(`${githubApi}/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/dispatches`, {
      method: "POST",
      headers: {
        "accept": "application/vnd.github+json",
        "authorization": `Bearer ${env.GITHUB_TOKEN}`,
        "content-type": "application/json",
        "user-agent": "T5-Cloudflare-Control-Plane/2.0",
        "x-github-api-version": "2026-03-10",
      },
      body: JSON.stringify({ event_type: "t5_render_job", client_payload: { job_id: jobId, api_base: env.PUBLIC_API_BASE } }),
    });
  } catch (error) {
    state.status = "FAILED";
    state.error = { code: "T5_GITHUB_DISPATCH_FAILED", message: error instanceof Error ? error.message : "network error" };
    await writeJob(env, state);
    return fail(502, "T5_GITHUB_DISPATCH_FAILED", "GitHub Actions est temporairement injoignable.", true);
  }
  if (!response.ok) {
    state.status = "FAILED";
    state.error = { code: "T5_GITHUB_DISPATCH_FAILED", status: response.status, body: (await response.text()).slice(0, 1000) };
    await writeJob(env, state);
    return fail(502, "T5_GITHUB_DISPATCH_FAILED", "GitHub Actions n'a pas accepté le job.", true);
  }
  return json({ job_id: jobId, status: state.status }, 202);
}

async function uploadOutput(request: Request, env: Env, jobId: string): Promise<Response> {
  const state = await readJob(env, jobId);
  if (!state) return fail(404, "T5_JOB_NOT_FOUND", "Job introuvable.");
  if (!["QUEUED", "RUNNING"].includes(state.status)) return fail(409, "T5_OUTPUT_PHASE_CLOSED", "La sortie ne peut pas être déposée dans cet état.");
  const mime = (request.headers.get("content-type") || "").split(";", 1)[0].toLowerCase();
  if (mime !== "video/mp4") return fail(415, "T5_UNSUPPORTED_OUTPUT", "La sortie doit être une vidéo MP4.");
  const length = Number(request.headers.get("content-length") || 0);
  if (length <= 0 || length > MAX_OUTPUT_BYTES) return fail(413, "T5_OUTPUT_SIZE_INVALID", "Taille de sortie invalide.");
  const expectedSha = (request.headers.get("x-content-sha256") || "").toLowerCase();
  if (!/^[a-f0-9]{64}$/.test(expectedSha)) return fail(400, "T5_MISSING_OUTPUT_SHA256", "x-content-sha256 est requis.");
  if (!request.body) return fail(400, "T5_EMPTY_OUTPUT", "Corps de sortie absent.");
  const object = await env.T5_MEDIA.put(outputKey(jobId), request.body, {
    sha256: expectedSha,
    httpMetadata: { contentType: "video/mp4" },
    customMetadata: { job_id: jobId, artifact: "t5_runtime_video" },
  });
  if (!object.checksums.sha256) return fail(500, "T5_R2_CHECKSUM_MISSING", "R2 n'a pas confirmé le checksum.", true);
  const actualSha = [...new Uint8Array(object.checksums.sha256)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  if (actualSha !== expectedSha || object.size !== length) {
    await env.T5_MEDIA.delete(outputKey(jobId));
    return fail(422, "T5_OUTPUT_INTEGRITY_MISMATCH", "La sortie reçue ne correspond pas à sa taille ou son SHA-256.");
  }
  state.output = { uri: outputUri(jobId), sha256: actualSha, bytes: object.size, mime_type: "video/mp4" };
  await writeJob(env, state);
  return json({ job_id: jobId, status: state.status, output: state.output }, 201);
}

function validSha(value: unknown): value is string {
  return typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
}

async function validateCallbackPayload(state: StoredJob, status: string, body: Record<string, unknown>): Promise<string | null> {
  if (status === "COMPLETED") {
    const result = record(body.result);
    const output = record(result?.output);
    const quality = record(result?.quality);
    const inputs = record(result?.inputs);
    const captureSha = record(inputs?.capture_sha256);
    const job = record(state.job);
    if (!result || result.schema_version !== "1.0.0" || result.status !== "COMPLETED") return "RenderResult absent ou invalide.";
    if (result.job_id !== state.job_id || result.idempotency_key !== state.idempotency_key) return "RenderResult rattaché à un autre job.";
    if (result.template_id !== "RESTAURATION-T5" || result.template_version !== "2.0.0-runtime" || result.profile_used !== "T5_GITHUB_ACTIONS_RUNTIME_V2") return "Profil T5 du RenderResult invalide.";
    if (result.control_plane !== "cloudflare_worker") return "Plan de contrôle du RenderResult invalide.";
    if (!output || output.uri !== outputUri(state.job_id) || output.file !== OUTPUT_FILE || !validSha(output.sha256)) return "Sortie RenderResult invalide.";
    if (!state.output || state.output.uri !== output.uri || state.output.sha256 !== output.sha256 || state.output.bytes !== output.bytes) return "Le RenderResult ne désigne pas le MP4 vérifié dans R2.";
    if (!quality || quality.status !== "PASS") return "Le contrôle qualité n'est pas PASS.";
    if (!inputs || inputs.merchant_payload_sha256 !== await sha256Text(canonicalStringify(state.merchant_payload))) return "Les réponses du résultat divergent du RenderJob.";
    if (!captureSha || SLOTS.some((slot) => captureSha[slot] !== state.captures[slot]?.sha256)) return "Les captures du résultat divergent du RenderJob.";
    if (!validSha(inputs.runtime_manifest_sha256) || !validSha(inputs.resolved_text_sha256)) return "La provenance runtime du résultat est incomplète.";
    if (JSON.stringify(result.rendered_fields) !== JSON.stringify(FIELDS)) return "Les six champs rendus ne sont pas attestés.";
    if (!Array.isArray(result.scene_capture_bindings) || result.scene_capture_bindings.length !== 4) return "Les quatre liaisons scène/capture manquent.";
    if (!job || record(job.render)?.visual_mode !== "runtime_hybrid_render") return "Le RenderJob stocké n'autorise pas ce rendu.";
  }
  if (status === "FAILED") {
    const error = record(body.error);
    if (!error || error.schema_version !== "1.0.0" || error.status !== "FAILED") return "RenderError absent ou invalide.";
    if (error.job_id !== state.job_id || typeof error.code !== "string" || !String(error.code).startsWith("T5_") || typeof error.message !== "string") return "RenderError rattaché à un autre job ou incomplet.";
  }
  return null;
}

async function callback(request: Request, env: Env, jobId: string): Promise<Response> {
  if (!(await authorized(request, env.CALLBACK_TOKEN))) return fail(401, "T5_UNAUTHORIZED", "Authentification requise.");
  const state = await readJob(env, jobId);
  if (!state) return fail(404, "T5_JOB_NOT_FOUND", "Job introuvable.");
  const body = await request.json<Record<string, unknown>>();
  const status = String(body.status);
  if (!["RUNNING", "COMPLETED", "FAILED"].includes(status)) return fail(400, "T5_INVALID_STATUS", "Statut de callback invalide.");
  if (state.status === "COMPLETED" && status !== "COMPLETED") return fail(409, "T5_TERMINAL_JOB", "Un résultat terminé ne peut pas régresser.");
  if (status === "RUNNING" && !["QUEUED", "RUNNING"].includes(state.status)) return fail(409, "T5_INVALID_STATUS_TRANSITION", `Transition ${state.status} → RUNNING interdite.`);
  if ((status === "COMPLETED" || status === "FAILED") && !["QUEUED", "RUNNING", "FAILED", "COMPLETED"].includes(state.status)) return fail(409, "T5_INVALID_STATUS_TRANSITION", `Transition ${state.status} → ${status} interdite.`);
  const invalid = await validateCallbackPayload(state, status, body);
  if (invalid) return fail(422, "T5_INVALID_CALLBACK_PAYLOAD", invalid);
  state.status = status as JobStatus;
  state.github = { run_id: body.github_run_id, run_url: body.github_run_url };
  if (status === "COMPLETED") state.result = body.result;
  if (status === "FAILED") state.error = body.error;
  await writeJob(env, state);
  return json({ job_id: jobId, status: state.status });
}

async function downloadObject(env: Env, key: string, contentType: string, sha: string): Promise<Response> {
  const object = await env.T5_MEDIA.get(key);
  if (!object) return fail(404, "T5_MEDIA_NOT_FOUND", "Média introuvable.");
  return new Response(object.body, {
    headers: {
      "content-type": contentType,
      "content-length": String(object.size),
      "x-content-sha256": sha,
      "cache-control": "private, no-store",
    },
  });
}

async function assetResponse(request: Request, env: Env): Promise<Response> {
  const response = await env.ASSETS.fetch(request);
  const headers = new Headers(response.headers);
  headers.set("content-security-policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
  headers.set("permissions-policy", "camera=(self), microphone=(self), geolocation=()");
  headers.set("referrer-policy", "no-referrer");
  headers.set("x-content-type-options", "nosniff");
  headers.set("x-frame-options", "DENY");
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

async function handle(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const parts = url.pathname.split("/").filter(Boolean);
  if (request.method === "GET" && url.pathname === "/health") {
    return json({ status: "ok", service: "t5-formule-control-plane", control_plane: "cloudflare_worker", render_plane: "github_actions", cloudflare_rendering: false });
  }
  if (request.method === "GET" && url.pathname === "/v1/contracts/form") return json(FORM_CONTRACT);
  if (request.method === "GET" && url.pathname === "/v1/contracts/capture-flow") return json(CAPTURE_FLOW_CONTRACT);
  if (request.method === "POST" && url.pathname === "/v1/jobs") {
    if (!(await authorized(request, env.CLIENT_API_TOKEN))) return fail(401, "T5_UNAUTHORIZED", "Jeton client requis.");
    return createJob(request, env);
  }
  if (parts.length >= 3 && parts[0] === "v1" && parts[1] === "jobs" && validId(parts[2])) {
    const jobId = parts[2];
    if (request.method === "GET" && parts.length === 3) {
      const state = await readJob(env, jobId);
      if (!state) return fail(404, "T5_JOB_NOT_FOUND", "Job introuvable.");
      return json({
        job_id: jobId, status: state.status, created_at: state.created_at, updated_at: state.updated_at,
        captures: Object.keys(state.captures), output: state.output, output_ready: Boolean(state.output),
        github: state.github, result: state.result, error: state.error,
      });
    }
    if (request.method === "PUT" && parts.length === 5 && parts[3] === "captures" && SLOTS.includes(parts[4] as CaptureSlot)) {
      if (!(await authorized(request, env.CLIENT_API_TOKEN))) return fail(401, "T5_UNAUTHORIZED", "Jeton client requis.");
      return uploadCapture(request, env, jobId, parts[4] as CaptureSlot);
    }
    if (request.method === "POST" && parts.length === 4 && parts[3] === "dispatch") {
      if (!(await authorized(request, env.CLIENT_API_TOKEN))) return fail(401, "T5_UNAUTHORIZED", "Jeton client requis.");
      return dispatch(request, env, jobId);
    }
    if (request.method === "GET" && parts.length === 4 && parts[3] === "payload") {
      if (!(await authorized(request, env.CALLBACK_TOKEN))) return fail(401, "T5_UNAUTHORIZED", "Authentification requise.");
      const state = await readJob(env, jobId);
      if (!state?.job) return fail(409, "T5_JOB_NOT_DISPATCHED", "RenderJob indisponible.");
      if (!["QUEUED", "RUNNING"].includes(state.status)) return fail(409, "T5_JOB_NOT_RUNNABLE", `Le job est ${state.status}.`);
      if (state.status === "QUEUED") { state.status = "RUNNING"; await writeJob(env, state); }
      return json({ job: state.job });
    }
    if (request.method === "GET" && parts.length === 5 && parts[3] === "captures" && SLOTS.includes(parts[4] as CaptureSlot)) {
      if (!(await authorized(request, env.CALLBACK_TOKEN))) return fail(401, "T5_UNAUTHORIZED", "Authentification requise.");
      const state = await readJob(env, jobId);
      const meta = state?.captures[parts[4] as CaptureSlot];
      if (!meta) return fail(404, "T5_CAPTURE_NOT_FOUND", "Capture introuvable.");
      return downloadObject(env, captureKey(jobId, parts[4] as CaptureSlot), meta.mime_type, meta.sha256);
    }
    if (request.method === "PUT" && parts.length === 4 && parts[3] === "output") {
      if (!(await authorized(request, env.CALLBACK_TOKEN))) return fail(401, "T5_UNAUTHORIZED", "Authentification requise.");
      return uploadOutput(request, env, jobId);
    }
    if (request.method === "GET" && parts.length === 4 && parts[3] === "output") {
      if (!(await clientOrCallbackAuthorized(request, env))) return fail(401, "T5_UNAUTHORIZED", "Authentification requise.");
      const state = await readJob(env, jobId);
      if (!state?.output) return fail(404, "T5_OUTPUT_NOT_FOUND", "Sortie introuvable.");
      return downloadObject(env, outputKey(jobId), "video/mp4", state.output.sha256);
    }
    if (request.method === "POST" && parts.length === 4 && parts[3] === "events") return callback(request, env, jobId);
  }
  if ((request.method === "GET" || request.method === "HEAD") && !url.pathname.startsWith("/v1/")) return assetResponse(request, env);
  return fail(404, "T5_ROUTE_NOT_FOUND", "Route inconnue.");
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    try { return await handle(request, env); }
    catch (error) { return fail(400, "T5_INVALID_REQUEST", error instanceof Error ? error.message : "Erreur inattendue."); }
  },
};
