# Vitrine Vidéo — RESTAURATION‑T5 · Formule, combo et offre

T5 produit une publicité verticale de **30 secondes** pour une seule formule, à partir de **six réponses** et de **quatre captures vidéo**.

## Contrat propriétaire

- référence vidéo : **V1 — Combo individuel complet** ;
- référence de raccord : **T1 — dish swipe / camera whip** ;
- une seule formule par publicité ;
- le même plat, la même boisson et les mêmes accompagnements restent cohérents dans les quatre scènes ;
- six réponses obligatoires : commerce, formule, contenu exact avec quantités, prix, WhatsApp et lieu de retrait ;
- quatre scènes de **6 s, 8 s, 7 s et 9 s** ;
- douze écrans de capture : **A / Guide**, **B / Enregistrement**, **C / Vérification** pour chacune des quatre scènes.

Les textes approuvés sont conservés sans réécriture dans `form/questions_T5.json` et `capture-guide/consignes_T5.json`.

## Rendu V3 plein écran

Le moteur V3 remplace entièrement l’ancien montage à cartes :

- chaque rush remplit les **720 × 1280 pixels** ;
- aucune carte permanente, fenêtre vidéo arrondie, grille, mosaïque, barre de progression ou interface n’est dessinée ;
- aucun titre générique ni libellé technique n’est brûlé dans la publicité ;
- les seuls textes visibles sont les valeurs exactes de `merchant_payload` ;
- chaque valeur apparaît comme un **bloc complet et stable**, synchronisé par son intervalle de scène, sans animation lettre par lettre ;
- la police active reste exactement **Playfair Display ExtraBold/Black**, sous licence OFL‑1.1 ;
- les glyphes partagent une baseline droite, sans rotation ni décalage vertical ; kerning, ligatures et variantes décoratives sont désactivés afin de garantir un espacement régulier ;
- le texte est centré, limité à deux lignes, avec interligne 1,2, marges de sécurité, contour sombre fin et ombre légère ; une scène ne montre jamais plus de deux champs simultanément ;
- les raccords occupent exactement huit images aux coupes **180, 420 et 630** ;
- la fin est stable sur les images **810 à 899**.

Le contrat complet est `montage/T5_MONTAGE_COMPLET_V3_0_0.json`. Les liaisons exécutables sont dans `config/T5_RUNTIME_CONTRACT_V3_0_0.json` et la mise en forme stable active est pilotée par `config/T5_TEXT_MOTION_V4_0_0.json`.

## Audio approuvé : Afrofire + voix B

Après validation séparée de la musique puis de la voix, la livraison complète utilise :

- **4 — Afrofire / DPStudioMusic**, Pixabay ID `300338`, depuis le début du morceau ;
- **B — voix française masculine `voice-11`**, répartie sur les quatre scènes ;
- ducking de la musique à **−3 dB hors parole et −10 dB sous parole**, avec attaque 120 ms et relâchement 450 ms ;
- master cible **−16 LUFS / −2 dBTP** ;
- livraison AAC stéréo 48 kHz à 192 kb/s.

Le fichier musical Pixabay intégral n’est jamais versionné ni publié. GitHub Actions le télécharge temporairement depuis l’URL officielle, vérifie son SHA‑256, construit le mix, puis le supprime avec le répertoire de travail. La Release ne contient que l’œuvre complète et son master voix + musique.

Le contrat reproductible est `config/T5_AUDIO_MIX_V1_0_0.json`; l’approbation propriétaire est `approvals/APPROBATION_MUSIQUE_ET_VOIX_T5_2026-11-18.json`.

Le RenderJob transporte désormais ce contrat complet : empreinte du contrat, identité et SHA‑256 d’Afrofire, manifeste et quatre empreintes de la voix `voice-11`, paramètres de mix et politique de commit. Le Worker refuse un callback `COMPLETED` qui n’atteste pas à la fois le QC visuel, le QC audio, le MP4 vérifié dans R2 et ces mêmes sources. L’état audio R2 n’est incrémenté qu’après ce callback complet et son rejeu reste idempotent.

```text
formulaire Cloudflare : 6 réponses + 12 écrans de capture
        ↓
RenderJob RESTAURATION‑T5
        ↓
4 captures S1…S4 stockées dans R2 et liées par SHA‑256
        ↓ repository_dispatch
GitHub Actions télécharge et revérifie les captures
        ↓
tools/build_t5_runtime_visual_inputs.py
        ↓
engine/render_runtime.py : plein cadre + sous-titres Playfair centrés et stables + raccords T1
        ↓
MP4 visuel silencieux + QC 21/21 + résultat intermédiaire VISUAL_COMPLETED
        ↓
téléchargement éphémère et contrôle SHA-256 d’Afrofire
        ↓
audio/scripts/build_t5_complete_audio.py : voix B + ducking + mastering + mux bit-exact vidéo
        ↓
tools/finalize_t5_render_result.py : liaison des preuves audio et visuelles
        ↓
MP4 complet 30 s + QC audio/vidéo 26/26 + RenderResult COMPLETED, ou RenderError
```

Cloudflare reste uniquement le **plan de contrôle et de stockage**. Le rendu vidéo est interdit sur Cloudflare et exécuté sur **GitHub Actions**.

### Liaisons des six réponses

| Valeur du RenderJob | Scènes |
|---|---|
| `merchant_payload.nom` | S1 et S4 |
| `merchant_payload.offre` | S1 et S3 |
| `merchant_payload.contenu` | S1, S2 et S3 |
| `merchant_payload.prix` | S3 |
| `merchant_payload.whatsapp` | S4 |
| `merchant_payload.quartier` | S4 |

Les tests modifient chaque valeur séparément et exigent une différence de pixels dans sa zone déclarée. Une capture substituée ne doit changer que sa scène.

## Quatre rushs de validation

La fixture serveur V3 utilise quatre vidéos Pexels distinctes d’**Aida Shukuhi**, issues du même tournage burger, frites et soda :

1. `32092904` — assemblage du double burger ;
2. `32092902` — découpe des pickles ;
3. `32092903` — burger et frites terminés ;
4. `32092901` — soda versé à côté de la formule.

Les URL, dimensions, durées, tailles et SHA‑256 sont dans `rushes/manifest.json`. Les médias bruts sont téléchargés uniquement dans un cache ignoré par Git ; ils ne sont ni commités ni publiés dans les artefacts ou Releases.

## État vérifié

La référence courante est le commit `34886de7581bdd6ee1e959fd647338746b7097e6` et la pré‑Release `t5-full-frame-v3-candidate-10` : CI principale, plan de contrôle Cloudflare et rendu complet réussis, QC visuel **21/21**, QC audio/vidéo **26/26**. Le MP4 complet a le SHA‑256 `9cc8b63cea41d221ceb2bfb02ca959400b53244609e04c585d57d218b3785425`. Le Worker Cloudflare de production n’a pas été déployé. Voir `STATUS.json`, `docs/T5_COMPLETE_AUDIO_AND_CONTROL_PLANE.md` et `reports/T5_FINAL_AUDIT_2026-11-20.md`.

## Fichiers principaux

- `form/questions_T5.json` — les six questions ;
- `capture-guide/consignes_T5.json` — les instructions des quatre captures ;
- `config/T5_CAPTURE_FLOW_V1_0_0.json` — les douze écrans A/B/C ;
- `config/T5_TEXT_MOTION_V4_0_0.json` — baseline uniforme, centrage, deux lignes maximum et apparition en bloc ;
- `config/T5_AUDIO_MIX_V1_0_0.json` — Afrofire, voix B, placements, ducking, mastering et contrôles ;
- `audio/voice/t5-voice-v1/` — quatre clips source `voice-11` approuvés et verrouillés par SHA‑256 ;
- `audio/scripts/build_t5_complete_audio.py` — construction et validation du master complet ;
- `schemas/T5_audio_mix.schema.json` — schéma strict du contrat audio ;
- `assets/fonts/playfair-display/` — police Playfair Display variable embarquée, métadonnées et licence OFL‑1.1 ;
- `montage/T5_MONTAGE_COMPLET_V3_0_0.json` — JSON complet de montage ;
- `adapter/t5_adapter.py` — six réponses + quatre captures → RenderJob ;
- `schemas/T5_render_job.schema.json` — contrat d’entrée ;
- `schemas/T5_text_motion_v4.schema.json` — schéma strict des sous-titres Playfair stables actifs ;
- `tools/build_t5_runtime_visual_inputs.py` — vérification SHA‑256 et manifeste runtime ;
- `engine/runtime_visual.py` — plein cadre, valeurs dynamiques et raccords ;
- `engine/render_runtime.py` — rendu des 900 images ;
- `tools/validate_runtime_render.py` — QC visuel et résultat intermédiaire non terminal ;
- `tools/finalize_t5_render_result.py` — RenderResult final lié au QC 21/21, au mix 26/26 et aux sources audio approuvées ;
- `cloudflare/` — formulaire, captures, R2, contrat audio, dispatch GitHub, stockage de sortie, état audio transactionnel et callbacks ;
- `.github/workflows/render-runtime.yml` — rendu serveur reproductible ;
- `.github/workflows/cloudflare-control-plane.yml` — validation systématique et déploiement Cloudflare conditionnel sur secrets de production ;
- `simulation/T5_12_ECRANS_EXECUTABLE.html` — simulation du parcours, jamais une livraison vidéo.

## Reproduire localement

```bash
python -m pip install -r requirements.txt
python adapter/t5_adapter.py \
  --render-job-id t5-runtime-demo-0001 \
  --answers demo/reponses_runtime_demo.json \
  --captures rushes/manifest.json \
  --control-plane github_actions_fixture \
  --output demo/render_job_runtime_demo.json
python tools/fetch_t5_demo_captures.py
python tools/build_t5_runtime_visual_inputs.py \
  --render-job demo/render_job_runtime_demo.json \
  --capture-dir rushes/cache-v4-aida \
  --manifest .tmp/t5-runtime-manifest.json
python engine/render_runtime.py \
  --render-job demo/render_job_runtime_demo.json \
  --manifest .tmp/t5-runtime-manifest.json \
  --capture-dir rushes/cache-v4-aida \
  --output-dir output/runtime/t5-runtime-demo-0001
python tools/validate_runtime_render.py \
  --video output/runtime/t5-runtime-demo-0001/VIDEO_T5_FORMULE_PLEIN_ECRAN_V3_A_VALIDER.mp4 \
  --render-job demo/render_job_runtime_demo.json \
  --manifest .tmp/t5-runtime-manifest.json \
  --render-report output/runtime/t5-runtime-demo-0001/T5_RUNTIME_RENDER_REPORT.json \
  --validation output/runtime/t5-runtime-demo-0001/T5_RUNTIME_VALIDATION.json \
  --result output/runtime/t5-runtime-demo-0001/T5_VISUAL_RENDER_RESULT.json
mv output/runtime/t5-runtime-demo-0001/VIDEO_T5_FORMULE_PLEIN_ECRAN_V3_A_VALIDER.mp4 \
  output/runtime/t5-runtime-demo-0001/T5_VISUEL_SILENCIEUX_QC_21_21.mp4
curl --fail --location \
  https://cdn.pixabay.com/audio/2025/02/12/audio_bf52f1c5ad.mp3 \
  --output /tmp/afrofire-source.mp3
echo '24e9606e14e4708e8c8ffa3a6a97429dbfc95049d388481392d72b971e932c61  /tmp/afrofire-source.mp3' | sha256sum --check --strict
python audio/scripts/build_t5_complete_audio.py \
  --silent-video output/runtime/t5-runtime-demo-0001/T5_VISUEL_SILENCIEUX_QC_21_21.mp4 \
  --music-source /tmp/afrofire-source.mp3 \
  --config config/T5_AUDIO_MIX_V1_0_0.json \
  --output-dir output/runtime/t5-runtime-demo-0001
python tools/finalize_t5_render_result.py \
  --visual-result output/runtime/t5-runtime-demo-0001/T5_VISUAL_RENDER_RESULT.json \
  --render-job demo/render_job_runtime_demo.json \
  --audio-config config/T5_AUDIO_MIX_V1_0_0.json \
  --audio-report output/runtime/t5-runtime-demo-0001/T5_COMPLETE_AUDIO_RENDER_REPORT.json \
  --video output/runtime/t5-runtime-demo-0001/VIDEO_T5_FORMULE_PLEIN_ECRAN_V3_A_VALIDER.mp4 \
  --output output/runtime/t5-runtime-demo-0001/T5_RENDER_RESULT.json
rm /tmp/afrofire-source.mp3
pytest -q
```

Sortie visuelle intermédiaire : **30,000 s**, 720 × 1280, 30 i/s, 900 images, H.264/yuv420p, aucune piste audio et QC **21/21**. Sortie finale : le même flux vidéo copié bit pour bit, avec une piste AAC stéréo 48 kHz, Afrofire, voix B, master proche de −16 LUFS / −2 dBTP et contrôles audio/vidéo complets.

## Archives rejetées

Les pré‑Releases `t5-full-frame-v3-candidate-6`, `t5-full-frame-v3-candidate-5`, `t5-runtime-v2-candidate-1` et `t5-first-montage-v1-candidate-1` sont **rejetées et conservées uniquement pour audit**. Le candidat #5 est rejeté pour sa Bodoni illisible ; le candidat #6 conserve la bonne famille Playfair mais est rejeté pour son animation lettre par lettre et ses décalages temporaires de baseline.
