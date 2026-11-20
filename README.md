# Vitrine Vidéo — RESTAURATION‑T5 · Formule, combo et offre

T5 présente **une seule formule** en quatre scènes : la formule complète, son contenu, son prix, puis la commande.

## Règles propriétaire conservées

- référence vidéo : **V1 — Combo individuel complet** ;
- transitions : **T1 — dish swipe** ;
- une seule formule par publicité ;
- le même plat, la même boisson et les mêmes accompagnements restent présents dans les quatre scènes ;
- six réponses obligatoires : nom du commerce, nom de l’offre, contenu exact avec quantités, prix exact, WhatsApp et lieu de retrait ;
- quatre scènes de **6 s, 8 s, 7 s et 9 s** ;
- douze écrans de capture, exactement trois états par scène : **A / Guide**, **B / Enregistrement**, **C / Vérification**.

Les textes approuvés restent dans `form/questions_T5.json` et `capture-guide/consignes_T5.json`.

## Architecture runtime V2

```text
formulaire Cloudflare (6 réponses)
        ↓
RenderJob RESTAURATION‑T5
        ↓
4 captures S1…S4 stockées dans R2 et vérifiées par SHA‑256
        ↓ repository_dispatch
GitHub Actions télécharge et revérifie chaque capture
        ↓
outils/build_t5_runtime_visual_inputs.py
        ↓
manifest runtime explicite S1→S1, S2→S2, S3→S3, S4→S4
        ↓
engine/render_runtime.py
        ↓
MP4 30 s + QC + RenderResult, ou RenderError
```

Cloudflare est uniquement le **plan de contrôle et de stockage**. Le rendu vidéo est interdit sur Cloudflare et exécuté exclusivement sur **GitHub Actions**.

### Liaisons métier

| Réponse | Pixels rendus |
|---|---|
| `merchant_payload.nom` | S1 et S4 |
| `merchant_payload.offre` | S1 et S3 |
| `merchant_payload.contenu` | S1, S2 et S3 |
| `merchant_payload.prix` | S3 |
| `merchant_payload.whatsapp` | S4 |
| `merchant_payload.quartier` | S4 |

Les tests changent chaque valeur séparément et exigent une différence dans le bloc de pixels déclaré. Un second test remplace une capture à la fois et exige que seule la fenêtre de sa scène change.

## Quatre prises de validation cohérentes

La fixture serveur utilise quatre vidéos Pexels distinctes d’Artem Podrez, issues du même tournage apparent : `4731057`, `4731063`, `4731066` et `4731132`. Les fichiers inspectés montrent le même double burger, la même portion de frites et le même verre de cola.

- manifeste, URLs, tailles et SHA‑256 : `rushes/manifest.json` ;
- provenance et licence : `docs/LICENCE_RUSH_DEMO_V2.md` ;
- médias bruts : téléchargés seulement dans le cache du runner, jamais commités et jamais publiés dans les artefacts ou Releases.

## Fichiers principaux

- `adapter/t5_adapter.py` — six réponses + quatre captures → RenderJob ;
- `schemas/T5_render_job.schema.json` — contrat d’entrée runtime ;
- `tools/build_t5_runtime_visual_inputs.py` — vérification des médias et manifeste runtime ;
- `engine/runtime_visual.py` — composition des textes provenant du `merchant_payload` ;
- `engine/render_runtime.py` — montage des quatre scènes ;
- `tools/validate_runtime_render.py` — QC technique, preuve des pixels et RenderResult ;
- `schemas/T5_render_result.schema.json` et `schemas/T5_render_error.schema.json` — contrats de sortie ;
- `cloudflare/` — formulaire réel, enregistrement des douze écrans, R2, dispatch GitHub, callbacks et téléchargement ;
- `.github/workflows/render-runtime.yml` — rendu manuel reproductible ou `repository_dispatch` ;
- `config/T5_RUNTIME_CONTRACT_V2_0_0.json` — liaisons champs/scènes/captures ;
- `simulation/T5_12_ECRANS_EXECUTABLE.html` — simulation de parcours uniquement, jamais considérée comme une livraison vidéo.

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
  --capture-dir rushes/cache-v2 \
  --manifest .tmp/t5-runtime-manifest.json
python engine/render_runtime.py \
  --render-job demo/render_job_runtime_demo.json \
  --manifest .tmp/t5-runtime-manifest.json \
  --capture-dir rushes/cache-v2 \
  --output-dir output/runtime/t5-runtime-demo-0001
pytest -q
```

Sortie attendue : 30,000 s, 720 × 1280, 30 i/s, 900 images, H.264/yuv420p, aucune piste audio, trois transitions T1 et appel à l’action stable pendant les trois dernières secondes.

## Publication runtime V2 vérifiée

- commit d’implémentation : [`f8450994a7ede8680a7c10c99141a87031343435`](https://github.com/vitrinevideo0-bot/vitrine-video-t5-formule-combo-offre/commit/f8450994a7ede8680a7c10c99141a87031343435) ;
- CI complète : [run `44720625596`](https://github.com/vitrinevideo0-bot/vitrine-video-t5-formule-combo-offre/actions/runs/44720625596), réussie ;
- rendu GitHub : [run `44720836940`](https://github.com/vitrinevideo0-bot/vitrine-video-t5-formule-combo-offre/actions/runs/44720836940), réussi ;
- pré‑Release du vrai rendu : [`t5-runtime-v2-candidate-1`](https://github.com/vitrinevideo0-bot/vitrine-video-t5-formule-combo-offre/releases/tag/t5-runtime-v2-candidate-1) ;
- MP4 GitHub : SHA‑256 `95715a88801cb386c081c06268581d9f034d23e94b352e6ad5c7d4dce3250a95`, 4 582 380 octets ;
- QC GitHub : **PASS 16/16**, 30,000 s, 720 × 1280, 30 i/s, 900 images, sans piste audio.

Tous les fichiers de l’artefact et de la pré‑Release ont été retéléchargés puis vérifiés avec `SHA256SUMS.txt`. Le MP4 a aussi été sondé indépendamment avec FFprobe. Aucun des quatre rushs bruts n’est présent dans la livraison.

## Ancien candidat rejeté

La pré‑Release `t5-first-montage-v1-candidate-1` est **rejetée et conservée uniquement comme archive d’audit**. Elle recyclait un rush café/gâteau et des libellés génériques. Son titre et ses notes GitHub portent désormais explicitement la mention « REJETÉ — ARCHIVE UNIQUEMENT ».

Elle ne doit pas être utilisée comme référence créative ou architecturale.
