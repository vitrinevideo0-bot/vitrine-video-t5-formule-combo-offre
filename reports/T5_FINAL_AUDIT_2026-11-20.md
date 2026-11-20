# Audit final T5 — 20 novembre 2026

## Verdict

**VALIDÉ, NON DÉPLOYÉ EN PRODUCTION.**

La chaîne T5 complète est reproductible au commit `34886de7581bdd6ee1e959fd647338746b7097e6` : formulaire/captures, RenderJob audio-lié, rendu visuel, mix Afrofire + `voice-11`, QC 21/21 puis 26/26, RenderResult terminal et pré‑Release. Le plan de contrôle Cloudflare est validé en intégration et en dry-build, mais le Worker n’a pas été déployé.

## Matrice de preuves

| Portée | Résultat | Preuve |
|---|---:|---|
| Tests locaux et CI | 48/48 PASS | CI `44783481812` |
| Contrat des 12 écrans | PASS | reconstruction déterministe dans `44783481812` |
| Worker TypeScript | PASS | type-check et Wrangler dry-build dans `44783481812` et `44783482195` |
| Intégration Worker/R2/dispatch/callback | PASS | `T5_CLOUDFLARE_CONTROL_PLANE_INTEGRATION_OK` dans les deux CI |
| QC visuel | 21/21 PASS | rendu `44783491714` |
| QC audio/vidéo | 26/26 PASS | rendu `44783491714` |
| RenderResult terminal | PASS | `T5_COMPLETE_RENDER_RESULT_PASS` |
| Pré‑Release | PASS | `t5-full-frame-v3-candidate-10`, 28 actifs |
| Checksums de livraison | PASS | `sha256sum -c SHA256SUMS.txt` sur les 27 actifs indexés |
| Déploiement Cloudflare production | NON EXÉCUTÉ | job `deploy-worker` ignoré |

## Artefact principal

- fichier : `VIDEO_T5_FORMULE_PLEIN_ECRAN_V3_A_VALIDER.mp4`
- SHA‑256 : `9cc8b63cea41d221ceb2bfb02ca959400b53244609e04c585d57d218b3785425`
- taille : 11 828 634 octets
- vidéo : H.264, 720×1280, 30 fps, 900 images
- audio : AAC, stéréo, 48 kHz, un flux
- durée : 30,000 s
- niveau intégré : −16,13 LUFS
- pic vrai : −1,89 dBTP
- sources liées : Afrofire Pixabay 300338 et voix masculine B `voice-11`

## Incident détecté et corrigé

Le premier rendu du nouveau parcours, run `44782878148` au commit `303301d`, a correctement produit le mix 26/26 mais a échoué dans le finaliseur : un chemin relatif `config/T5_AUDIO_MIX_V1_0_0.json` était appliqué directement à `Path.relative_to(ROOT)`. Le correctif résout d’abord ce chemin en chemin absolu, et un test de non-régression invoque désormais explicitement le finaliseur avec un chemin relatif.

- correctif : commit `34886de7581bdd6ee1e959fd647338746b7097e6`
- validation après correctif : CI principale, CI Cloudflare et rendu complet tous réussis.

## Sécurité et intégrité

- Afrofire est téléchargée temporairement puis contrôlée par taille et SHA‑256.
- La source musicale temporaire est supprimée avant assemblage de la livraison.
- Aucun MP3 source ni rush brut n’est présent dans la pré‑Release.
- Le Worker refuse les résultats terminaux incomplets ou aux preuves audio discordantes.
- La mise à jour de l’état audio n’est permise qu’après validation complète ; les rejeux sont idempotents.

## Réserves explicites

1. **Pas de déploiement production :** les résultats prouvent le code et l’intégration simulée, pas une URL Worker Cloudflare active ni un objet R2 de production.
2. **Voix non dynamique :** les clips `voice-11` sont figés sur la démonstration Burger Atelier Kandi. Les réponses libres d’un autre commerçant peuvent ne pas correspondre à cette narration.
3. **Musique tierce :** la licence et la provenance sont documentées ; la source Afrofire n’est pas redistribuée seule. L’absence actuelle de revendication Content ID ne constitue pas une garantie future.

## Liens

- CI principale : https://github.com/vitrinevideo0-bot/vitrine-video-t5-formule-combo-offre/actions/runs/44783481812
- CI Cloudflare : https://github.com/vitrinevideo0-bot/vitrine-video-t5-formule-combo-offre/actions/runs/44783482195
- rendu complet : https://github.com/vitrinevideo0-bot/vitrine-video-t5-formule-combo-offre/actions/runs/44783491714
- pré‑Release : https://github.com/vitrinevideo0-bot/vitrine-video-t5-formule-combo-offre/releases/tag/t5-full-frame-v3-candidate-10
