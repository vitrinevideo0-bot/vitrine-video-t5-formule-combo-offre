# Audit T5 — rotation musicale stricte — 18 novembre 2026

## Verdict

**VALIDÉ LOCALEMENT, NON DÉPLOYÉ EN PRODUCTION.**

T5 sélectionne désormais quatre instrumentales selon le cycle strict `300338 → 324016 → 292156 → 345669 → 300338`. L’état n’avance qu’après un rendu complet et un QC audio `PASS`; un échec ne le modifie pas. Le registre durable `successful_render_jobs` rend tout ancien succès idempotent, y compris après un tour complet.

## Matrice de preuves

| Portée | Résultat | Preuve locale |
|---|---:|---|
| Tests Python | 59/59 PASS | `pytest -q` |
| Contrats JSON et actifs | PASS | schémas, hashes, tailles et `SHA256SUMS.txt` |
| Worker TypeScript | PASS | `tsc --noEmit` |
| Wrangler | PASS | dry-build `4.165.0` avec Node 24 |
| Intégration Worker/R2 | PASS | rejet d’un saut, échec sans mutation, `1→2→3→4→1`, puis rejeu de l’ancien succès sans mutation |
| QC visuel réel | 21/21 PASS | rendu local depuis les quatre captures verrouillées |
| QC audio piste 1 | 26/26 PASS | Afrofire / `t5_music_300338` |
| QC audio piste 2 | 26/26 PASS | Afro 10 / `t5_music_324016` |
| QC audio piste 3 | 26/26 PASS | Snitch / `t5_music_292156` |
| QC audio piste 4 | 26/26 PASS | Dance Fever Dreams / `t5_music_345669` |
| RenderResult terminal piste 1 | PASS | `T5_COMPLETE_RENDER_RESULT_PASS` |
| Déploiement Cloudflare production | NON EXÉCUTÉ | secrets et autorisation non fournis |

## Artefact de référence local

- fichier : `VIDEO_T5_FORMULE_PLEIN_ECRAN_V3_A_VALIDER.mp4`
- musique : `t5_music_300338`, première piste du nouvel état initial
- SHA‑256 : `d65d821e24c2363c7acd24451f380f10d539d2aec901a283c72979064c740adb`
- taille : 11 837 226 octets
- vidéo : H.264, 720×1280, 30 fps, 900 images
- audio : AAC, stéréo, 48 kHz, un flux
- durée : 30,000 s
- QC visuel : 21/21 PASS
- QC audio/vidéo : 26/26 PASS

## Sélection et état

Ordre canonique :

1. `t5_music_300338` — Pixabay 300338 ;
2. `t5_music_324016` — Pixabay 324016 ;
3. `t5_music_292156` — Pixabay 292156 ;
4. `t5_music_345669` — Pixabay 345669.

Le Worker lit `music/t5-last-success.json`, lie le successeur au RenderJob, puis refuse tout callback dont l’ID, le SHA‑256 du dérivé, la provenance ou les preuves de QC divergent. Le commit R2 utilise une écriture conditionnelle et ajoute l’association au registre `successful_render_jobs`. Une concurrence construite sur un état périmé produit un conflit au lieu d’avancer hors cycle; le rejeu du premier succès après `1→2→3→4` ne modifie rien.

## Sécurité, droits et intégrité

- Le contrat musical strict est verrouillé par le SHA‑256 `428d5826e96a87bcddb1d585104968a1aa5ee29483ac00da60c50f85747a6c54`.
- Les quatre dérivés instrumentaux de 30 s sont versionnés et verrouillés par SHA‑256.
- Ils ne contiennent aucune voix et passent les mesures de durée, format, loudness, pic vrai et écrêtage.
- Les sources Pixabay intégrales ne sont pas embarquées ni publiées.
- La provenance, la licence et l’observation Content ID datée sont conservées pour chaque piste.
- Aucun MP3 autonome n’est inclus dans la livraison vidéo du workflow.
- Les rushs bruts restent hors Git et hors artefacts.

## Baseline historique

Le commit `34886de7581bdd6ee1e959fd647338746b7097e6`, les runs `44783481812`, `44783482195`, `44783491714` et la pré‑Release `t5-full-frame-v3-candidate-10` prouvaient la chaîne antérieure à musique fixe. Ils sont conservés pour audit, mais ne prouvent pas la rotation à quatre pistes.

## Réserves explicites

1. **Pas de déploiement production :** les preuves portent sur le code, Wrangler local et l’intégration R2 locale, pas sur une URL Worker de production.
2. **Voix non dynamique :** les clips `voice-11` restent figés sur la démonstration Burger Atelier Kandi.
3. **Musique tierce :** l’absence de mention Content ID observée le 18 novembre 2026 ne garantit pas l’absence future de revendication.
