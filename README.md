# Vitrine Vidéo — RESTAURATION‑T5 · Formule, combo et offre

Cinquième gabarit restauration : présenter une seule formule, montrer ce qu’elle contient, afficher son prix réel puis expliquer comment commander.

## Décisions propriétaire

- référence vidéo : **V1 — Combo individuel complet** ;
- référence de transition : **T1 — dish swipe / camera whip** ;
- règle de continuité : **une seule formule par publicité ; le même plat, la même boisson et les mêmes accompagnements restent présents dans les quatre scènes** ;
- six questions approuvées : nom, offre, contenu exact, prix, WhatsApp et quartier ;
- texte corrigé des douze écrans fourni par le propriétaire.

Les vidéos de référence ne sont ni copiées, ni versionnées, ni redistribuées. Leur usage se limite au reverse engineering documenté dans `research/REVERSE_ENGINEERING_V1.md`.

## Parcours approuvé

| Scène | Durée | Titre |
|---|---:|---|
| S1 | 6 s | LA FORMULE |
| S2 | 8 s | CE QU’IL Y A DANS LA FORMULE |
| S3 | 7 s | LE PRIX |
| S4 | 9 s | COMMANDER |

Chaque scène possède trois états : **A / Guide**, **B / Enregistrement**, **C / Vérification**. Le décompte 3‑2‑1 est transitoire et ne compte pas comme un treizième écran.

## Questions, JSON et preuves

- `form/questions_T5.json` — six réponses obligatoires reliées à `merchant_payload` ;
- `capture-guide/consignes_T5.json` — texte approuvé et règle de continuité ;
- `config/T5_CAPTURE_FLOW_V1_0_0.json` — contrat exécutable des douze écrans ;
- `ui-screens/manifest.json` — douze PNG 720 × 1280 et leur planche ;
- `simulation/T5_12_ECRANS_EXECUTABLE.html` — simulation autonome ;
- `schemas/` — schémas JSON 2020‑12 des questions, du flow, du rush et du RenderJob ;
- `docs/CONTRAT_QUESTIONS_12_ECRANS_T5.md` — lecture humaine complète.

## Premier montage silencieux à juger

Le premier candidat utilise un seul rush vertical Pexels de démonstration montrant le même gâteau et le même cappuccino. Les quatre scènes sont dérivées de cette source afin de ne jamais changer de formule.

- source et licence : `rushes/manifest.json` et `docs/LICENCE_RUSH_DEMO.md` ;
- RenderJob : `demo/render_job_silent_demo.json` ;
- moteur : `engine/render_first_montage.py` ;
- validation : `tools/validate_first_montage.py` ;
- workflow serveur : `.github/workflows/render-first-montage.yml`.

Le rush brut est hash‑verrouillé, mais il n’est jamais suivi par Git ni publié. Le montage porte la mention **DÉMO — DONNÉES À REMPLACER**. Il est silencieux ; la musique et la voix ne seront traitées qu’après jugement de cette structure.

## Contrôles locaux

```bash
python -m pip install -r requirements.txt
python tools/build_t5_capture_flow.py
python tools/generate_t5_ui_screens.py
python tools/build_t5_simulation.py
pytest -q
python tools/fetch_t5_rush.py
python engine/render_first_montage.py
python tools/validate_first_montage.py
```

Format contrôlé du candidat : 30,000 s, 720 × 1280, 30 i/s, 900 images, H.264/yuv420p, sans piste audio, trois transitions T1 et fin stable pendant trois secondes.
