# Provenance des quatre prises de validation T5 V2

Les quatre vidéos de validation proviennent de **Pexels**, créateur **Artem Podrez**, et du même tournage apparent. Elles servent uniquement à exercer le chemin dynamique `formulaire → RenderJob → captures vérifiées → manifeste runtime → rendu GitHub`.

| Scène | Pexels | Page | SHA-256 du fichier inspecté |
|---|---:|---|---|
| S1 — formule complète | 4731057 | https://www.pexels.com/video/man-sitting-on-a-table-with-food-4731057/ | `2a5f66dd1ffe656d2f3211d3ecd8714233784790460a1bd6b24b026d40762520` |
| S2 — contenu | 4731063 | https://www.pexels.com/video/man-eating-a-burger-and-fries-4731063/ | `d6df57374a781c4c101c21937ad20009dd39f063d505d7e2beb98ee5df07cbac` |
| S3 — prix | 4731066 | https://www.pexels.com/video/man-eating-at-the-fastfood-4731066/ | `ff4b3642cc9ce5d50191384175d1a4fa7b1f49fc8653154ccb97c9216aa6baee` |
| S4 — commander | 4731132 | https://www.pexels.com/video/man-having-a-meal-4731132/ | `5bb285f21ca7ed90607224afd4325fc437e789fe344ca3516e23f37a3c519341` |

Licence consultée : https://www.pexels.com/license/

Chaque fichier réel inspecté est en 2560 × 1440, H.264, 30 i/s et sans piste audio. Les planches d’inspection confirment le même double burger, la même portion de frites et le même verre de cola dans les quatre prises.

## Règle de publication

- les médias bruts sont téléchargés seulement dans le cache du runner GitHub ou le stockage runtime ;
- ils ne sont jamais commités ;
- ils ne sont jamais ajoutés aux artefacts ni aux Releases ;
- seuls le MP4 monté, les contrats, les rapports, les empreintes et les preuves visuelles dérivées peuvent être publiés.
