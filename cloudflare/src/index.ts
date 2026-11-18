import {
  AUDIO_MIX_CONTRACT,
  AUDIO_MIX_CONTRACT_SHA256,
  T5_VOICE_MANIFEST_SHA256,
} from "./audio_mix_contract";
import { CAPTURE_FLOW_CONTRACT } from "./capture_flow_contract";
import { FORM_CONTRACT } from "./form_contract";
import { MUSIC_PACK_CONTRACT, MUSIC_PACK_CONTRACT_SHA256 } from "./music_pack_contract";

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
type MusicId = "t5_music_300338" | "t5_music_324016" | "t5_music_292156" | "t5_music_345669";
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
  requested_music_id: "auto" | MusicId;
  selected_music_id?: MusicId;
  last_successful_music_id?: MusicId | null;
  job?: Record<string, unknown>;
  github?: Record<string, unknown>;
  output?: StoredOutput;
  result?: unknown;
  error?: unknown;
}

interface MusicState {
  schema_version: "1.0.0";
  last_successful_music_id: MusicId | null;
  last_successful_render_job_id: string | null;
  successful_render_count: number;
  successful_render_jobs: Record<string, MusicId>;
}

const SLOTS: CaptureSlot[] = ["S1", "S2", "S3", "S4"];
const MUSIC_IDS: MusicId[] = ["t5_music_300338", "t5_music_324016", "t5_music_292156", "t5_music_345669"];
const FIELDS = ["nom", "offre", "contenu", "prix", "whatsapp", "quartier"] as const;
const DURATIONS: Record<CaptureSlot, number> = { S1: 6000, S2: 8000, S3: 7000, S4: 9000 };
const ALLOWED_MIME = new Set(["video/mp4", "video/webm", "video/quicktime"]);
const MAX_CAPTURE_BYTES = 250 * 1024 * 1024;
const MAX_OUTPUT_BYTES = 500 * 1024 * 1024;
const OUTPUT_FILE = "VIDEO_T5_FORMULE_PLEIN_ECRAN_V3_A_VALIDER.mp4";
const MUSIC_STATE_KEY = "music/t5-last-success.json";

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

function initialMusicState(): MusicState {
  return {
    schema_version: "1.0.0",
    last_successful_music_id: null,
    last_successful_render_job_id: null,
    successful_render_count: 0,
    successful_render_jobs: {},
  };
}

function validateMusicState(state: MusicState): MusicState {
  const receipts = record(state.successful_render_jobs);
  if (
    state.schema_version !== "1.0.0"
    || (state.last_successful_music_id !== null && !MUSIC_IDS.includes(state.last_successful_music_id))
    || !Number.isInteger(state.successful_render_count)
    || state.successful_render_count < 0
    || !receipts
    || Object.keys(receipts).length !== state.successful_render_count
    || Object.entries(receipts).some(([jobId, musicId]) => !validId(jobId) || !MUSIC_IDS.includes(musicId as MusicId))
    || ((state.last_successful_music_id === null) !== (state.last_successful_render_job_id === null))
    || ((state.successful_render_count === 0) !== (state.last_successful_music_id === null))
    || (state.last_successful_render_job_id !== null
      && receipts[state.last_successful_render_job_id] !== state.last_successful_music_id)
  ) throw new Error("État musical T5 persistant invalide.");
  return { ...state, successful_render_jobs: receipts as Record<string, MusicId> };
}

async function readMusicState(env: Env): Promise<MusicState> {
  const object = await env.T5_MEDIA.get(MUSIC_STATE_KEY);
  return object ? validateMusicState(await object.json<MusicState>()) : initialMusicState();
}

function selectMusic(requested: "auto" | MusicId, last: MusicId | null) {
  const contract = MUSIC_PACK_CONTRACT.selection_contract;
  if (
    contract.allowed_variant_ids.join("") !== MUSIC_IDS.join("")
    || contract.first_render_variant_id !== MUSIC_IDS[0]
    || contract.first_render_pool_size !== 1
    || contract.subsequent_pool_size !== 1
    || contract.explicit_selection_policy !== "exact_successor_only"
    || contract.idempotency_ledger_key !== "successful_render_jobs"
    || contract.state_update_policy !== "after_completed_audio_qc_pass_only"
    || contract.failed_render_state_policy !== "unchanged"
  ) throw new Error("Le contrat musical T5 ne garantit pas le cycle strict.");
  const previousIndex = last === null ? -1 : MUSIC_IDS.indexOf(last);
  const expected = MUSIC_PACK_CONTRACT.tracks[(previousIndex + 1) % MUSIC_PACK_CONTRACT.tracks.length];
  if (requested !== "auto" && requested !== expected.id) {
    throw new Error(`Le cycle T5 strict attend ${expected.id}; ${requested} ne peut pas le contourner.`);
  }
  return {
    ...expected,
    selection_mode: requested === "auto" ? "strict_success_cycle" as const : "explicit" as const,
    last_successful_music_id: last,
  };
}

async function commitMusicSuccess(env: Env, jobId: string, selected: MusicId): Promise<void> {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const object = await env.T5_MEDIA.get(MUSIC_STATE_KEY);
    const current = object ? validateMusicState(await object.json<MusicState>()) : initialMusicState();
    if (Object.prototype.hasOwnProperty.call(current.successful_render_jobs, jobId)) {
      if (current.successful_render_jobs[jobId] !== selected) {
        throw new Error("Un callback T5 rejoué ne peut pas changer de musique.");
      }
      return;
    }
    const previousIndex = current.last_successful_music_id === null
      ? -1
      : MUSIC_IDS.indexOf(current.last_successful_music_id);
    const expected = MUSIC_IDS[(previousIndex + 1) % MUSIC_IDS.length];
    if (selected !== expected) {
      throw new Error(`Le succès T5 doit respecter le cycle strict : ${expected} attendu, ${selected} reçu.`);
    }
    const updated: MusicState = {
      schema_version: "1.0.0",
      last_successful_music_id: selected,
      last_successful_render_job_id: jobId,
      successful_render_count: current.successful_render_count + 1,
      successful_render_jobs: { ...current.successful_render_jobs, [jobId]: selected },
    };
    const written = await env.T5_MEDIA.put(MUSIC_STATE_KEY, JSON.stringify(updated), {
      onlyIf: object ? { etagMatches: object.etag } : { etagDoesNotMatch: "*" },
      httpMetadata: { contentType: "application/json" },
      customMetadata: { last_successful_music_id: selected, last_successful_render_job_id: jobId },
    });
    if (written) return;
  }
  throw new Error("Conflit concurrent persistant sur l'état musical T5.");
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

async function buildRenderJob(state: StoredJob, env: Env): Promise<Record<string, unknown>> {
  const captures = Object.fromEntries(SLOTS.map((slot) => {
    const capture = state.captures[slot];
    if (!capture) throw new Error(`Capture ${slot} absente.`);
    return [slot, capture];
  }));
  const musicState = await readMusicState(env);
  const selectedMusic = selectMusic(state.requested_music_id, musicState.last_successful_music_id);
  state.selected_music_id = selectedMusic.id;
  state.last_successful_music_id = musicState.last_successful_music_id;
  return {
    schema_version: "1.0.0",
    job_id: state.job_id,
    idempotency_key: state.idempotency_key,
    template_id: "RESTAURATION-T5",
    template_version: "3.0.0-full-frame",
    merchant_payload: state.merchant_payload,
    captures,
    audio: {
      mode: "owner_approved_music_rotation_voice_b_complete",
      contract: "config/T5_AUDIO_MIX_V1_0_0.json",
      contract_sha256: AUDIO_MIX_CONTRACT_SHA256,
      music_pack: "config/T5_MUSIC_PACK_V1_0_0.json",
      music_pack_sha256: MUSIC_PACK_CONTRACT_SHA256,
      music: {
        selection_mode: selectedMusic.selection_mode,
        selected_music_id: selectedMusic.id,
        selected_choice: selectedMusic.choice,
        pixabay_id: selectedMusic.pixabay_id,
        title: selectedMusic.title,
        artist: selectedMusic.artist,
        file: selectedMusic.file,
        sha256: selectedMusic.sha256,
        bytes: selectedMusic.bytes,
        duration_s: selectedMusic.duration_s,
        contains_voice: selectedMusic.contains_voice,
        source_page: selectedMusic.page,
        source_url: selectedMusic.url,
        source_sha256: selectedMusic.source_sha256,
        source_bytes: selectedMusic.source_bytes,
        source_start_s: selectedMusic.source_start_s,
        license: MUSIC_PACK_CONTRACT.license,
        full_source_bundled: false,
        standalone_redistribution_forbidden: true,
        last_successful_music_id: selectedMusic.last_successful_music_id,
        state_update_policy: "after_completed_audio_qc_pass_only",
      },
      voice: {
        source_mode: "owner_approved_registered_clips",
        selected_option: AUDIO_MIX_CONTRACT.voice.selected_option,
        voice_id: AUDIO_MIX_CONTRACT.voice.voice_id,
        language: AUDIO_MIX_CONTRACT.voice.language,
        manifest: AUDIO_MIX_CONTRACT.voice.manifest,
        manifest_sha256: T5_VOICE_MANIFEST_SHA256,
        clip_source_sha256: Object.fromEntries(
          AUDIO_MIX_CONTRACT.voice.clips.map((clip) => [`S${clip.scene}`, clip.source_sha256]),
        ),
      },
      mix_contract: AUDIO_MIX_CONTRACT.mix_contract,
      state_update_policy: "after_completed_audio_qc_pass_only",
    },
    render: {
      visual_mode: "runtime_full_frame_render",
      runtime_capture_manifest_required: true,
      render_business_text: true,
      business_text_source: "merchant_payload",
      runtime_contract: "config/T5_RUNTIME_CONTRACT_V3_0_0.json",
      transition_reference: "T1",
      width: 720,
      height: 1280,
      fps: 30,
      frames: 900,
      duration_s: 30.0,
      scene_durations_s: [6, 8, 7, 9],
      audio_mode: "owner_approved_music_rotation_voice_b_complete",
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
  const requestedMusic = String(body.music_id || "auto") as "auto" | MusicId;
  if (requestedMusic !== "auto" && !MUSIC_IDS.includes(requestedMusic as MusicId)) {
    return fail(400, "T5_INVALID_MUSIC_ID", "music_id doit valoir auto ou un identifiant approuvé du pack T5.");
  }
  const merchant = validatePayload(body.merchant_payload);
  const seed = `${idempotencyKey}\n${canonicalStringify(merchant)}\n${requestedMusic}\n${Date.now()}\n${crypto.randomUUID()}`;
  const jobId = `t5-runtime-${(await sha256Text(seed)).slice(0, 24)}`;
  const now = new Date().toISOString();
  const state: StoredJob = {
    status: "UPLOADING", job_id: jobId, idempotency_key: idempotencyKey,
    created_at: now, updated_at: now, merchant_payload: merchant, captures: {},
    requested_music_id: requestedMusic,
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
  try {
    state.job = await buildRenderJob(state, env);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Sélection musicale invalide.";
    if (message.startsWith("Le cycle T5 strict attend")) {
      return fail(409, "T5_MUSIC_SEQUENCE_CONFLICT", message, true);
    }
    throw error;
  }
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
    customMetadata: { job_id: jobId, artifact: "t5_complete_audio_video" },
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
    const audioQuality = record(result?.audio_quality);
    const resultAudio = record(result?.audio);
    const resultMusic = record(resultAudio?.music);
    const resultVoice = record(resultAudio?.voice);
    const resultVoiceAudioClips = record(resultVoice?.clip_source_sha256);
    const finalMix = record(resultAudio?.final_mix);
    const inputs = record(result?.inputs);
    const captureSha = record(inputs?.capture_sha256);
    const resultVoiceClips = record(inputs?.voice_clip_source_sha256);
    const job = record(state.job);
    const jobRender = record(job?.render);
    const jobAudio = record(job?.audio);
    const jobMusic = record(jobAudio?.music);
    const jobVoice = record(jobAudio?.voice);
    const jobVoiceClips = record(jobVoice?.clip_source_sha256);
    if (!result || result.schema_version !== "1.0.0" || result.status !== "COMPLETED") return "RenderResult complet absent ou invalide.";
    if (result.job_id !== state.job_id || result.idempotency_key !== state.idempotency_key) return "RenderResult rattaché à un autre job.";
    if (result.template_id !== "RESTAURATION-T5" || result.template_version !== "3.0.0-full-frame" || result.profile_used !== "T5_GITHUB_ACTIONS_COMPLETE_V1") return "Profil complet T5 du RenderResult invalide.";
    if (result.control_plane !== "cloudflare_worker") return "Plan de contrôle du RenderResult invalide.";
    if (!output || output.uri !== outputUri(state.job_id) || output.file !== OUTPUT_FILE || !validSha(output.sha256)) return "Sortie RenderResult invalide.";
    if (!state.output || state.output.uri !== output.uri || state.output.sha256 !== output.sha256 || state.output.bytes !== output.bytes) return "Le RenderResult ne désigne pas le MP4 vérifié dans R2.";
    if (!quality || quality.status !== "PASS" || quality.passed !== 21 || quality.total !== 21 || !audioQuality || audioQuality.status !== "PASS" || audioQuality.passed !== 26 || audioQuality.total !== 26) return "Les contrôles visuel 21/21 et audio 26/26 doivent être PASS.";
    if (!inputs || inputs.merchant_payload_sha256 !== await sha256Text(canonicalStringify(state.merchant_payload))) return "Les réponses du résultat divergent du RenderJob.";
    if (!captureSha || SLOTS.some((slot) => captureSha[slot] !== state.captures[slot]?.sha256)) return "Les captures du résultat divergent du RenderJob.";
    if (!validSha(inputs.runtime_manifest_sha256) || !validSha(inputs.resolved_text_sha256)) return "La provenance runtime du résultat est incomplète.";
    if (!job || jobRender?.visual_mode !== "runtime_full_frame_render" || jobRender.audio_mode !== "owner_approved_music_rotation_voice_b_complete") return "Le RenderJob stocké n'autorise pas le rendu complet.";
    if (!jobAudio || !jobMusic || !jobVoice || !jobVoiceClips) return "Le contrat audio du RenderJob est incomplet.";
    if (inputs.audio_contract_sha256 !== jobAudio.contract_sha256 || inputs.music_pack_sha256 !== jobAudio.music_pack_sha256 || inputs.music_source_sha256 !== jobMusic.source_sha256 || inputs.music_program_sha256 !== jobMusic.sha256 || inputs.voice_manifest_sha256 !== jobVoice.manifest_sha256) return "La provenance audio diverge du RenderJob.";
    if (!resultVoiceClips || SLOTS.some((slot) => resultVoiceClips[slot] !== jobVoiceClips[slot])) return "Les sources voix du résultat divergent du RenderJob.";
    if (!resultAudio || resultAudio.mode !== jobAudio.mode || resultAudio.visual_bitstream_copy !== true) return "L'attestation du mix complet est invalide.";
    if (!resultMusic || resultMusic.selected_music_id !== jobMusic.selected_music_id || resultMusic.pixabay_id !== jobMusic.pixabay_id || resultMusic.source_sha256 !== jobMusic.source_sha256 || resultMusic.program_sha256 !== jobMusic.sha256 || resultMusic.full_source_bundled !== false) return "La musique sélectionnée n'est pas attestée conformément au RenderJob.";
    if (!resultVoice || resultVoice.voice_id !== jobVoice.voice_id || resultVoice.manifest_sha256 !== jobVoice.manifest_sha256 || !resultVoiceAudioClips || SLOTS.some((slot) => resultVoiceAudioClips[slot] !== jobVoiceClips[slot])) return "La voix B n'est pas attestée conformément au RenderJob.";
    if (!finalMix || finalMix.audio_codec !== "aac" || finalMix.sample_rate_hz !== 48000 || finalMix.channels !== 2 || finalMix.one_audio_stream !== true) return "Le flux audio final est invalide.";
    if (typeof finalMix.integrated_lufs !== "number" || finalMix.integrated_lufs < -16.6 || finalMix.integrated_lufs > -15.4 || typeof finalMix.true_peak_dbtp !== "number" || finalMix.true_peak_dbtp > -1.0) return "Les mesures audio finales sont hors contrat.";
    if (result.audio_state_commit_allowed !== true) return "Le RenderResult interdit le commit audio transactionnel.";
    if (JSON.stringify(result.rendered_fields) !== JSON.stringify(FIELDS)) return "Les six champs rendus ne sont pas attestés.";
    if (!Array.isArray(result.scene_capture_bindings) || result.scene_capture_bindings.length !== 4) return "Les quatre liaisons scène/capture manquent.";
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
  if (status === "COMPLETED") {
    if (!state.selected_music_id) return fail(409, "T5_MUSIC_SELECTION_MISSING", "La musique sélectionnée manque au job.");
    try {
      await commitMusicSuccess(env, state.job_id, state.selected_music_id);
    } catch (error) {
      return fail(409, "T5_MUSIC_STATE_CONFLICT", error instanceof Error ? error.message : "Conflit d'état musical.", true);
    }
    state.result = body.result;
  }
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
    return json({
      status: "ok",
      service: "t5-formule-control-plane",
      control_plane: "cloudflare_worker",
      render_plane: "github_actions",
      cloudflare_rendering: false,
      audio_mode: "owner_approved_music_rotation_voice_b_complete",
      music_rotation: "t5_music_300338→t5_music_324016→t5_music_292156→t5_music_345669→t5_music_300338",
    });
  }
  if (request.method === "GET" && url.pathname === "/v1/contracts/form") return json(FORM_CONTRACT);
  if (request.method === "GET" && url.pathname === "/v1/contracts/capture-flow") return json(CAPTURE_FLOW_CONTRACT);
  if (request.method === "GET" && url.pathname === "/v1/contracts/audio-mix") return json(AUDIO_MIX_CONTRACT);
  if (request.method === "GET" && url.pathname === "/v1/contracts/music-pack") return json(MUSIC_PACK_CONTRACT);
  if (request.method === "GET" && url.pathname === "/v1/music-state") {
    if (!(await authorized(request, env.CALLBACK_TOKEN))) return fail(401, "T5_UNAUTHORIZED", "Authentification requise.");
    return json(await readMusicState(env));
  }
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
