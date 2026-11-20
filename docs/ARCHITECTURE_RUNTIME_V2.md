# T5 V2 — choix d’architecture après audit de T1, T2, T3 et T4

> **Document historique remplacé.** Il décrit la décision V2 initiale, pas l’état livré. La chaîne active est V3 plein écran avec audio complet ; voir `docs/T5_COMPLETE_AUDIO_AND_CONTROL_PLANE.md`, `STATUS.json` et l’audit de clôture dans `reports/`. Les mentions `runtime_hybrid_render` ou de sortie silencieuse ci-dessous ne doivent plus être utilisées comme statut courant.

## Conclusion de l’audit

T5 ne doit pas créer une simulation parallèle. Il reprend les invariants déjà éprouvés dans les gabarits précédents :

- **T1** : protocole des contrats, horloge 30 secondes et famille de transitions `dish_swipe` ;
- **T2** : liaison explicite `merchant_payload → blocs graphiques`, tests où une réponse modifiée doit changer de vrais pixels, et rendu GitHub ;
- **T3** : adaptateur qui lie `merchant_payload` et `captures.S1…S4`, mais pas son ancien moteur silencieux pris isolément, car celui-ci lisait un manifeste de rushs séparé ;
- **T4** : chemin runtime de référence : plan de contrôle Cloudflare, quatre captures vérifiées par SHA‑256, manifeste visuel construit sur le runner GitHub, moteur dynamique, QC et callback.

Le mode manuel T4 qui rematérialise un master visuel approuvé n’est volontairement **pas** utilisé. T5 impose `runtime_hybrid_render` dans tous les RenderJobs, y compris la fixture manuelle.

## Chaîne T5 retenue

1. Le formulaire charge les six questions canoniques depuis `/v1/contracts/form`.
2. Le navigateur crée un job idempotent avec les six réponses.
3. Les douze écrans approuvés guident quatre enregistrements S1, S2, S3 et S4.
4. Chaque fichier est envoyé avec son SHA‑256 et ses métadonnées ; R2 recalcule et confirme l’empreinte.
5. Quand les quatre slots sont prêts, le Worker construit le RenderJob et envoie `t5_render_job` à GitHub.
6. GitHub récupère le RenderJob, télécharge chaque capture, revérifie son SHA‑256 et construit le manifeste runtime.
7. Le moteur ne reçoit aucun chemin implicite : il lit uniquement ce manifeste et le RenderJob.
8. Les textes sont résolus exclusivement depuis `merchant_payload`.
9. Le validateur contrôle le MP4, les six preuves de pixels, les quatre liaisons de captures, l’intégrité et la stabilité finale.
10. GitHub émet soit un `RenderResult` conforme, soit un `RenderError` ; Cloudflare n’accepte `COMPLETED` qu’après dépôt du MP4 vérifié dans R2.

## Interdictions testées

- aucune valeur métier codée en dur dans le moteur ;
- aucun identifiant Pexels ni chemin `rushes/manifest.json` dans le moteur ;
- aucune scène sans capture déclarée ;
- aucun rush brut dans l’artefact ou la Release ;
- aucun rendu vidéo sur Cloudflare ;
- aucune simulation présentée comme résultat final ;
- aucun retour possible vers `approved_master_stream_copy` dans le schéma RenderJob T5.

## Matrice de preuve

| Exigence | Preuve |
|---|---|
| Six réponses liées | `config/T5_RUNTIME_CONTRACT_V2_0_0.json`, `tests/test_t5_dynamic_runtime.py` |
| Quatre captures réellement consommées | `tools/build_t5_runtime_visual_inputs.py`, rapport `scene_capture_evidence` |
| Substitution isolée | test `test_substituting_one_capture_changes_only_its_scene_window` |
| Rendu serveur | `.github/workflows/render-runtime.yml` |
| Formulaire et R2 | `cloudflare/src/index.ts`, test boîte noire `cloudflare/test/control_plane_integration.py` |
| RenderResult/Error | schémas `T5_render_result` et `T5_render_error` |
| MP4 réel | `tools/validate_runtime_render.py` et artefact GitHub |
