const app = document.querySelector('#app');
const state = {
  form: null,
  flow: null,
  token: sessionStorage.getItem('t5-client-token') || '',
  jobId: sessionStorage.getItem('t5-active-job') || null,
  idempotencyKey: null,
  merchant: null,
  screens: [],
  screenIndex: 0,
  stream: null,
  recorder: null,
  capture: null,
  reviewUrl: null,
  timer: null,
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const authHeaders = () => ({ authorization: `Bearer ${state.token}` });

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const error = new Error(payload?.message || `Erreur serveur ${response.status}`);
    error.code = payload?.code;
    error.status = response.status;
    throw error;
  }
  return payload;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
}

async function boot() {
  try {
    [state.form, state.flow] = await Promise.all([
      api('/v1/contracts/form'),
      api('/v1/contracts/capture-flow'),
    ]);
    if (state.form.fields.length !== 6 || state.flow.counts.stable_capture_screens !== 12 || state.flow.screens.length !== 12) {
      throw new Error('Le contrat T5 doit contenir exactement 6 questions et 12 écrans.');
    }
    state.screens = state.flow.screens;
    if (state.jobId && state.token) {
      renderStatus();
      pollStatus();
    } else {
      renderForm();
    }
  } catch (error) {
    app.innerHTML = `<section class="center-panel"><div class="mark">!</div><h1>Parcours indisponible</h1><p>${escapeHtml(error.message)}</p></section>`;
  }
}

function renderForm() {
  app.replaceChildren(document.querySelector('#form-template').content.cloneNode(true));
  const fields = document.querySelector('#form-fields');
  state.form.fields.forEach((field, index) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'field';
    const inputMode = field.id === 'whatsapp' ? 'tel' : 'text';
    wrapper.innerHTML = `
      <span class="field-index">${String(index + 1).padStart(2, '0')}</span>
      <label for="field-${field.id}">${escapeHtml(field.question)}</label>
      <input id="field-${field.id}" name="${field.id}" inputmode="${inputMode}"
        minlength="${field.minLength}" maxlength="${field.maxLength}"
        placeholder="${escapeHtml(field.example || '')}" ${field.required ? 'required' : ''}>
      ${field.helper ? `<small>${escapeHtml(field.helper)}</small>` : ''}`;
    fields.append(wrapper);
  });
  document.querySelector('#access-token').value = state.token;
  document.querySelector('#merchant-form').addEventListener('submit', submitForm);
}

async function submitForm(event) {
  event.preventDefault();
  const formElement = event.currentTarget;
  const button = formElement.querySelector('button[type=submit]');
  const errorElement = document.querySelector('#form-error');
  errorElement.textContent = '';
  if (!formElement.reportValidity()) return;
  state.token = document.querySelector('#access-token').value.trim();
  sessionStorage.setItem('t5-client-token', state.token);
  state.merchant = Object.fromEntries(state.form.fields.map((field) => [field.id, formElement.elements[field.id].value.trim()]));
  state.idempotencyKey = `t5-client-${crypto.randomUUID()}`;
  button.disabled = true;
  button.firstChild.textContent = 'PRÉPARATION… ';
  try {
    const response = await api('/v1/jobs', {
      method: 'POST',
      headers: { ...authHeaders(), 'content-type': 'application/json', 'idempotency-key': state.idempotencyKey },
      body: JSON.stringify({ merchant_payload: state.merchant }),
    });
    state.jobId = response.job_id;
    sessionStorage.setItem('t5-active-job', state.jobId);
    await ensureCamera();
    state.screenIndex = 0;
    renderCaptureScreen();
  } catch (error) {
    button.disabled = false;
    button.firstChild.textContent = 'COMMENCER LES 12 ÉCRANS ';
    errorElement.textContent = error.status === 401 ? 'Code d’accès incorrect.' : error.message;
  }
}

async function ensureCamera() {
  if (state.stream?.active) return state.stream;
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
    throw new Error('Ce navigateur ne permet pas l’enregistrement caméra. Utilise Safari ou Chrome récent.');
  }
  state.stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: 'environment' }, width: { ideal: 1080 }, height: { ideal: 1920 }, frameRate: { ideal: 30, max: 30 } },
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  return state.stream;
}

function mountCaptureShell() {
  app.replaceChildren(document.querySelector('#capture-template').content.cloneNode(true));
  const video = document.querySelector('#camera');
  video.srcObject = state.stream;
  video.removeAttribute('src');
  video.muted = true;
  video.controls = false;
  video.classList.remove('review');
  video.play().catch(() => {});
}

function renderCaptureScreen() {
  mountCaptureShell();
  const screen = state.screens[state.screenIndex];
  document.querySelector('#scene-counter').textContent = `SCÈNE ${screen.scene_index}/4`;
  document.querySelector('#screen-ordinal').textContent = screen.ordinal;
  const content = document.querySelector('#capture-content');
  const hud = document.querySelector('#recording-hud');
  if (screen.state === 'A_GUIDE') {
    const copy = screen.resolved_text;
    const seconds = Math.round(screen.capture_duration_ms / 1000);
    content.innerHTML = `
      <article class="guide-card">
        <span class="duration-pill">${seconds} SECONDES</span>
        <h2>${escapeHtml(copy.title)}</h2>
        <p class="instruction">${escapeHtml(copy.instruction)}</p>
        <div class="lists">
          <section><h3>${escapeHtml(copy.film_section_title)}</h3><ul>${copy.film_list.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul></section>
          <section><h3>${escapeHtml(copy.avoid_section_title)}</h3><ul>${copy.avoid_list.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul></section>
        </div>
        <p class="voice-note"><strong>${escapeHtml(copy.action_section_title)}</strong><br>${escapeHtml(copy.required_action)}</p>
        <p class="voice-note">${escapeHtml(copy.speech_note)}</p>
        <p class="example">${escapeHtml(copy.optional_example)}</p>
        <button id="start-recording" class="primary" type="button">${escapeHtml(copy.primary_action)} <span>●</span></button>
      </article>`;
    document.querySelector('#start-recording').addEventListener('click', beginCapture);
  } else if (screen.state === 'B_RECORDING') {
    content.replaceChildren();
    hud.hidden = false;
  } else if (screen.state === 'C_REVIEW') {
    renderReview(screen);
  }
}

async function beginCapture() {
  const errorElement = document.querySelector('#capture-error');
  errorElement.textContent = '';
  try {
    await ensureCamera();
    const countdown = document.querySelector('#countdown');
    countdown.hidden = false;
    for (const value of state.flow.transient_states[0].sequence) {
      countdown.textContent = value;
      await sleep(850);
    }
    countdown.textContent = '';
    await sleep(250);
    countdown.hidden = true;
    state.screenIndex += 1;
    renderCaptureScreen();
    await recordCurrentScene();
  } catch (error) {
    errorElement.textContent = error.name === 'NotAllowedError' ? 'Autorise la caméra et le micro pour continuer.' : error.message;
  }
}

function selectMimeType() {
  const candidates = [
    'video/mp4;codecs=avc1.42E01E,mp4a.40.2',
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm',
  ];
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) || '';
}

async function recordCurrentScene() {
  const screen = state.screens[state.screenIndex];
  const duration = screen.capture.duration_ms;
  const mimeType = selectMimeType();
  const options = { videoBitsPerSecond: 5_000_000, audioBitsPerSecond: 128_000 };
  if (mimeType) options.mimeType = mimeType;
  const chunks = [];
  const recorder = new MediaRecorder(state.stream, options);
  state.recorder = recorder;
  const stopped = new Promise((resolve, reject) => {
    recorder.addEventListener('dataavailable', (event) => { if (event.data.size) chunks.push(event.data); });
    recorder.addEventListener('error', (event) => reject(event.error || new Error('Échec de l’enregistrement.')), { once: true });
    recorder.addEventListener('stop', resolve, { once: true });
  });
  const started = performance.now();
  recorder.start(250);
  state.timer = window.setInterval(() => {
    const elapsed = Math.min(duration, performance.now() - started);
    const remaining = Math.max(0, duration - elapsed);
    const seconds = Math.ceil(remaining / 1000);
    const timer = document.querySelector('#timer');
    const progress = document.querySelector('#record-progress');
    if (timer) timer.textContent = `00:${String(seconds).padStart(2, '0')}`;
    if (progress) progress.style.width = `${(elapsed / duration) * 100}%`;
  }, 50);
  await sleep(duration);
  if (recorder.state !== 'inactive') recorder.stop();
  await stopped;
  clearInterval(state.timer);
  const type = recorder.mimeType || mimeType || 'video/webm';
  const blob = new Blob(chunks, { type });
  if (!blob.size) throw new Error('La capture est vide. Recommence cette scène.');
  const settings = state.stream.getVideoTracks()[0]?.getSettings() || {};
  const fps = Math.round(Number(settings.frameRate || 30) * 1000) / 1000;
  state.capture = {
    blob,
    mime: type.split(';')[0].toLowerCase(),
    fullMime: type,
    width: Math.round(settings.width || document.querySelector('#camera').videoWidth || 1080),
    height: Math.round(settings.height || document.querySelector('#camera').videoHeight || 1920),
    fps,
    frames: Math.max(1, Math.round((fps * duration) / 1000)),
    duration,
    videoCodec: /vp9/i.test(type) ? 'vp9' : /vp8/i.test(type) ? 'vp8' : /avc|mp4/i.test(type) ? 'h264' : 'browser_mediarecorder',
    hasAudio: state.stream.getAudioTracks().some((track) => track.readyState === 'live'),
    audioCodec: /opus|webm/i.test(type) ? 'opus' : 'aac',
  };
  state.screenIndex += 1;
  renderCaptureScreen();
}

function renderReview(screen) {
  const video = document.querySelector('#camera');
  video.srcObject = null;
  if (state.reviewUrl) URL.revokeObjectURL(state.reviewUrl);
  state.reviewUrl = URL.createObjectURL(state.capture.blob);
  video.src = state.reviewUrl;
  video.muted = false;
  video.controls = true;
  video.loop = true;
  video.classList.add('review');
  video.play().catch(() => {});
  const copy = screen.resolved_text;
  const content = document.querySelector('#capture-content');
  content.innerHTML = `
    <article class="review-card">
      <span class="check">✓</span>
      <h2>${escapeHtml(copy.review_question)}</h2>
      <ul style="text-align:left;color:#d7c8ba;line-height:1.55">${copy.review_checks.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
      <p>${escapeHtml(copy.audio_status)}</p>
      <div class="review-actions">
        <button id="retake" class="secondary" type="button">${escapeHtml(copy.redo_action)}</button>
        <button id="accept" class="primary" type="button">${escapeHtml(copy.positive_action)} <span>→</span></button>
      </div>
    </article>`;
  document.querySelector('#retake').addEventListener('click', retake);
  document.querySelector('#accept').addEventListener('click', acceptCapture);
}

function retake() {
  if (state.reviewUrl) URL.revokeObjectURL(state.reviewUrl);
  state.reviewUrl = null;
  state.capture = null;
  state.screenIndex -= 2;
  renderCaptureScreen();
}

async function sha256(blob) {
  const buffer = await blob.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buffer);
  return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, '0')).join('');
}

async function acceptCapture() {
  const screen = state.screens[state.screenIndex];
  const slot = screen.scene_id;
  const button = document.querySelector('#accept');
  const errorElement = document.querySelector('#capture-error');
  button.disabled = true;
  button.firstChild.textContent = 'ENVOI SÉCURISÉ… ';
  try {
    const digest = await sha256(state.capture.blob);
    const uploadHeaders = {
      ...authHeaders(),
      'content-type': state.capture.fullMime,
      'x-content-sha256': digest,
      'x-video-width': String(state.capture.width),
      'x-video-height': String(state.capture.height),
      'x-video-fps': String(state.capture.fps),
      'x-video-frames': String(state.capture.frames),
      'x-video-duration-ms': String(state.capture.duration),
      'x-video-codec': state.capture.videoCodec,
      'x-has-audio': String(state.capture.hasAudio),
    };
    if (state.capture.hasAudio) uploadHeaders['x-audio-codec'] = state.capture.audioCodec;
    await api(`/v1/jobs/${state.jobId}/captures/${slot}`, {
      method: 'PUT', headers: uploadHeaders, body: state.capture.blob,
    });
    if (state.reviewUrl) URL.revokeObjectURL(state.reviewUrl);
    state.reviewUrl = null;
    state.capture = null;
    if (screen.scene_index < 4) {
      state.screenIndex += 1;
      renderCaptureScreen();
    } else {
      await submitRender();
    }
  } catch (error) {
    button.disabled = false;
    button.firstChild.textContent = `${screen.resolved_text.positive_action} `;
    errorElement.textContent = error.message;
  }
}

async function submitRender() {
  for (const track of state.stream?.getTracks() || []) track.stop();
  await api(`/v1/jobs/${state.jobId}/dispatch`, { method: 'POST', headers: authHeaders() });
  renderStatus();
  pollStatus();
}

function renderStatus() {
  app.replaceChildren(document.querySelector('#status-template').content.cloneNode(true));
  document.querySelector('#job-reference').textContent = state.jobId;
  document.querySelector('#restart').addEventListener('click', () => {
    sessionStorage.removeItem('t5-active-job');
    location.reload();
  });
  document.querySelector('#download-video').addEventListener('click', downloadVideo);
}

async function downloadVideo() {
  const button = document.querySelector('#download-video');
  button.disabled = true;
  try {
    const response = await fetch(`/v1/jobs/${state.jobId}/output`, { headers: authHeaders() });
    if (!response.ok) throw new Error(`Téléchargement impossible (${response.status}).`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'VIDEO_T5_FORMULE_RUNTIME_DYNAMIQUE_V2_A_VALIDER.mp4';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 30_000);
  } catch (error) {
    document.querySelector('#status-copy').textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function pollStatus() {
  try {
    const status = await api(`/v1/jobs/${state.jobId}`);
    const title = document.querySelector('#status-title');
    const copy = document.querySelector('#status-copy');
    const step = document.querySelector('#render-step');
    const symbol = document.querySelector('#status-symbol');
    const link = document.querySelector('#github-link');
    const download = document.querySelector('#download-video');
    if (!title) return;
    if (status.github?.run_url) {
      link.href = status.github.run_url;
      link.hidden = false;
    }
    if (status.status === 'COMPLETED') {
      title.textContent = 'Ton montage est prêt';
      copy.textContent = 'Les 4 scènes et les 6 réponses ont passé le contrôle qualité sur GitHub.';
      step.textContent = 'Rendu dynamique + contrôle qualité validés';
      step.classList.add('done');
      symbol.classList.add('complete');
      download.hidden = false;
      sessionStorage.removeItem('t5-active-job');
      return;
    }
    if (status.status === 'FAILED') {
      title.textContent = 'Le rendu doit être vérifié';
      copy.textContent = status.error?.message || 'Le serveur a arrêté le parcours sans publier de vidéo incomplète.';
      step.textContent = `Arrêt contrôlé · ${status.error?.code || 'T5_RENDER_FAILED'}`;
      symbol.classList.add('failed');
      return;
    }
    window.setTimeout(pollStatus, 5000);
  } catch (error) {
    document.querySelector('#status-copy').textContent = `Suivi temporairement indisponible : ${error.message}`;
    window.setTimeout(pollStatus, 8000);
  }
}

boot();
