# T5 — chaîne audio complète, rotation stricte et plan de contrôle

Ce document décrit l’architecture active. Les descriptions historiques où T5 utilisait une musique fixe ou pouvait produire un résultat terminal silencieux ne sont plus normatives.

## Rotation musicale canonique

Le pack `config/T5_MUSIC_PACK_V1_0_0.json` contient exactement quatre instrumentales approuvées, dans cet ordre :

1. `t5_music_300338` — Pixabay `300338`, **Afrofire** — DPStudioMusic ;
2. `t5_music_324016` — Pixabay `324016`, **Afro 10** — DasDrum ;
3. `t5_music_292156` — Pixabay `292156`, **Afro Trap x Football x Sport (Snitch)** — 47643651 ;
4. `t5_music_345669` — Pixabay `345669`, **Dance Fever Dreams — Afrobeats** — musicofthefuture_MOF.

L’état initial n’a aucune dernière réussite et sélectionne donc la piste 1. Chaque nouveau succès doit être exactement le successeur de la dernière réussite : **1→2→3→4→1**. Une sélection explicite peut confirmer le successeur attendu, mais ne peut pas le contourner.

L’état persistant respecte `schemas/T5_music_selection_state.schema.json` et contient :

- `last_successful_music_id` ;
- `last_successful_render_job_id` ;
- `successful_render_count` ;
- `successful_render_jobs`, registre durable de chaque association `render_job_id → music_id` validée.

Il n’est modifié qu’après un résultat `COMPLETED`, un QC visuel `21/21 PASS`, un QC audio `26/26 PASS`, la vérification du MP4 dans R2 et la concordance de toutes les preuves musicales. Un échec laisse l’état inchangé. Le rejeu de tout ancien succès est sans effet, y compris après un tour complet. Deux succès concurrents construits sur le même ancien état ne peuvent pas avancer deux fois : seul le successeur encore attendu est accepté.

## Actifs musicaux

Les quatre fichiers sous `audio/music/t5-afrobeat-v1/` sont des dérivés instrumentaux locaux de 30 secondes : 48 kHz, stéréo, 192 kb/s, zéro échantillon écrêté et aucune voix. `SHA256SUMS.txt`, `source_manifest.json`, `BUILD_PROVENANCE.json` et `evidence/` lient chaque dérivé à sa source officielle.

Les sources Pixabay intégrales ne sont pas embarquées et ne doivent jamais être redistribuées comme actifs autonomes. Le RenderJob conserve leur URL, taille, SHA‑256 et point de départ uniquement comme provenance. La vidéo finale peut intégrer l’instrumentale dans une œuvre plus large conformément au contrat de droits documenté.

## Architecture active

1. Le Worker Cloudflare reçoit les six réponses commerçant et les quatre captures vérifiées.
2. Au dispatch, il lit l’état musical R2 et sélectionne le successeur strict dans le pack approuvé.
3. Le `RenderJob` lie immuablement l’ID choisi, le dérivé local, sa provenance officielle, les hashes du pack et du contrat de mix, ainsi que la voix française masculine `voice-11`.
4. GitHub Actions rend un MP4 visuel silencieux intermédiaire.
5. `tools/validate_runtime_render.py` valide ce visuel et émet `VISUAL_COMPLETED` avec QC **21/21**.
6. Le workflow vérifie le SHA‑256 du dérivé local choisi, place les quatre clips vocaux, applique le ducking et produit le mix final sans réencoder le flux H.264.
7. `tools/finalize_t5_render_result.py` lie le résultat visuel, le RenderJob, les deux contrats, le rapport **26/26** et le MP4 complet.
8. Le résultat terminal est `COMPLETED` avec le profil `T5_GITHUB_ACTIONS_COMPLETE_V1`.
9. En parcours Cloudflare, le Worker vérifie à nouveau le résultat et commite atomiquement le choix musical réussi.

Cloudflare est uniquement le plan de contrôle et de stockage ; le rendu reste exécuté sur GitHub Actions.

## Invariants terminaux

Un résultat terminal valide prouve au minimum :

- QC visuel : `21/21 PASS` ;
- QC audio/vidéo : `26/26 PASS` ;
- ID musical égal à celui du RenderJob ;
- SHA‑256 du dérivé local et SHA‑256 de la source de provenance égaux à ceux du RenderJob ;
- hash du pack musical et hash du contrat audio égaux à ceux du RenderJob ;
- voix `voice-11`, manifeste et quatre clips liés au RenderJob ;
- un seul flux audio AAC, stéréo, 48 kHz ;
- niveau intégré entre −16,6 et −15,4 LUFS ;
- pic vrai inférieur ou égal à −1 dBTP ;
- copie bitstream du flux vidéo pendant le mux ;
- `audio_state_commit_allowed: true` seulement après toutes ces preuves.

## Validation locale du 18 novembre 2026

- tests Python : **59 réussis** ;
- contrats TypeScript Cloudflare : type-check réussi ;
- Wrangler `4.165.0` : dry-build réussi avec Node 24 ;
- intégration Worker/R2 : échec sans mutation, choix explicite hors cycle rejeté, succès exacts **1→2→3→4→1** et rejeu du premier succès après le tour complet sans mutation ;
- rendu visuel réel : **21/21 PASS** ;
- mix piste 1 : **26/26 PASS**, MP4 SHA‑256 `d65d821e24c2363c7acd24451f380f10d539d2aec901a283c72979064c740adb` ;
- mix pistes 2, 3 et 4 : **26/26 PASS** chacun.

La pré‑Release `t5-full-frame-v3-candidate-10` et le commit `34886de7581bdd6ee1e959fd647338746b7097e6` restent des preuves historiques de la chaîne antérieure à musique fixe. Ils ne prouvent pas la nouvelle rotation.

## État de déploiement

La validation n’est pas un déploiement. Aucun Worker Cloudflare de production n’a été déployé dans cette migration. Le déploiement exige les secrets Cloudflare autorisés et le déclenchement manuel explicite du workflow.

## Limite de périmètre connue

Les quatre clips vocaux approuvés récitent la copie de démonstration Burger Atelier Kandi. Ils sont intégrés et vérifiés, mais ne synthétisent pas dynamiquement les réponses d’un autre commerçant. Une chaîne TTS dynamique relève d’une évolution distincte.
