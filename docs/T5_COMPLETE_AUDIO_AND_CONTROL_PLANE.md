# T5 — état canonique de la chaîne audio complète et du plan de contrôle

Ce document remplace les descriptions historiques où T5 pouvait être interprété comme un rendu terminal silencieux.

## Architecture active

1. Le Worker Cloudflare reçoit les réponses commerçant et les quatre captures vérifiées.
2. Le `RenderJob` lie de façon immuable les captures, **Afrofire** et la voix française masculine **`voice-11`**.
3. GitHub Actions rend d’abord un MP4 visuel silencieux intermédiaire.
4. `tools/validate_runtime_render.py` valide ce visuel et émet un résultat `VISUAL_COMPLETED` avec QC **21/21**.
5. Le workflow télécharge Afrofire depuis sa source officielle, vérifie son SHA‑256, normalise les quatre clips vocaux approuvés et produit le mix final.
6. `tools/finalize_t5_render_result.py` lie le résultat visuel, le `RenderJob`, le contrat audio, le rapport QC **26/26** et le MP4 complet.
7. Le résultat terminal est `COMPLETED` avec le profil `T5_GITHUB_ACTIONS_COMPLETE_V1`.
8. En parcours Cloudflare réel, le Worker n’accepte le callback final qu’après vérification du MP4 complet dans R2 ; l’état audio est alors mis à jour de façon transactionnelle et idempotente.

## Invariants terminaux

Un résultat terminal valide prouve au minimum :

- QC visuel : `21/21 PASS` ;
- QC audio/vidéo : `26/26 PASS` ;
- musique : Pixabay `300338`, Afrofire, SHA‑256 `24e9606e14e4708e8c8ffa3a6a97429dbfc95049d388481392d72b971e932c61` ;
- voix : `voice-11`, manifeste SHA‑256 `a69b3fc92897e9270817c07d5d639a63a661fe5c691820779cdd96f299a88914`, avec les quatre hashes de clips liés au `RenderJob` ;
- un seul flux audio AAC, stéréo, 48 kHz ;
- niveau intégré entre −16,6 et −15,4 LUFS ;
- pic vrai inférieur ou égal à −1 dBTP ;
- copie bitstream du flux vidéo lors du mux audio ;
- `audio_state_commit_allowed: true` seulement après l’ensemble de ces preuves.

Le fichier source Afrofire ne doit pas être redistribué comme actif autonome.

## Preuve validée

- commit : `34886de7581bdd6ee1e959fd647338746b7097e6` ;
- CI principale : run `44783481812`, succès ;
- CI du plan de contrôle Cloudflare : run `44783482195`, succès, déploiement ignoré ;
- rendu complet : run `44783491714`, succès ;
- pré‑Release : `t5-full-frame-v3-candidate-10` ;
- MP4 SHA‑256 : `9cc8b63cea41d221ceb2bfb02ca959400b53244609e04c585d57d218b3785425` ;
- métriques : 30 s, 720×1280, 30 fps, H.264 + AAC stéréo 48 kHz, −16,13 LUFS, −1,89 dBTP.

Les 28 actifs de la pré‑Release ont été téléchargés et vérifiés avec `SHA256SUMS.txt`. Aucun MP3 source Afrofire ni rush brut n’est livré.

## État de déploiement

La validation n’est pas un déploiement. Aucun Worker Cloudflare de production n’a été déployé par ces runs : le job `deploy-worker` a été ignoré. Il faut des secrets Cloudflare de production autorisés et un déclenchement manuel explicite pour franchir cette étape.

## Limite de périmètre connue

Les quatre clips vocaux approuvés récitent la copie de démonstration Burger Atelier Kandi. Ils sont intégrés et vérifiés, mais ils ne synthétisent pas dynamiquement les réponses d’un autre commerçant. Une chaîne TTS dynamique ferait l’objet d’une évolution distincte.
