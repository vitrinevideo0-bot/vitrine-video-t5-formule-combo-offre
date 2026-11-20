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
- les raccords occupent exactement huit images aux coupes **180, 420 et 630** ;
- la fin est stable sur les images **810 à 899**.

Le contrat complet est `montage/T5_MONTAGE_COMPLET_V3_0_0.json`. Les liaisons exécutables sont dans `config/T5_RUNTIME_CONTRACT_V3_0_0.json`.

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
engine/render_runtime.py : plein cadre + valeurs saisies + raccords T1
        ↓
MP4 30 s + QC 19/19 + RenderResult, ou RenderError
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

## Fichiers principaux

- `form/questions_T5.json` — les six questions ;
- `capture-guide/consignes_T5.json` — les instructions des quatre captures ;
- `config/T5_CAPTURE_FLOW_V1_0_0.json` — les douze écrans A/B/C ;
- `montage/T5_MONTAGE_COMPLET_V3_0_0.json` — JSON complet de montage ;
- `adapter/t5_adapter.py` — six réponses + quatre captures → RenderJob ;
- `schemas/T5_render_job.schema.json` — contrat d’entrée ;
- `tools/build_t5_runtime_visual_inputs.py` — vérification SHA‑256 et manifeste runtime ;
- `engine/runtime_visual.py` — plein cadre, valeurs dynamiques et raccords ;
- `engine/render_runtime.py` — rendu des 900 images ;
- `tools/validate_runtime_render.py` — QC et RenderResult ;
- `cloudflare/` — formulaire, captures, R2, dispatch GitHub et callbacks ;
- `.github/workflows/render-runtime.yml` — rendu serveur reproductible ;
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
  --result output/runtime/t5-runtime-demo-0001/T5_RENDER_RESULT.json
pytest -q
```

Sortie attendue : **30,000 s**, 720 × 1280, 30 i/s, 900 images, H.264/yuv420p, aucune piste audio et QC **19/19**.

## Archives rejetées

Les pré‑Releases `t5-runtime-v2-candidate-1` et `t5-first-montage-v1-candidate-1` sont **rejetées et conservées uniquement pour audit**. Elles ne constituent ni la direction créative ni le moteur de rendu courant.
