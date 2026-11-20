# RESTAURATION‑T5 — Questions, scènes et 12 écrans à valider

**Statut : PROPOSITION LOCALE — NON PUBLIÉE SUR GITHUB**

**Direction déjà choisie : V1 + T1.** L’adaptation garde l’idée de montrer toute la formule, de prouver chaque élément, de revenir au prix puis de finir sur la commande. Les glissements utilisent uniquement les vrais plats, le plateau, le sac ou la boîte du commerçant.

---

# 1. Les 6 questions proposées

| N° | Question affichée | Exemple | Donnée JSON |
|---:|---|---|---|
| 1 | **Comment s'appelle ton restaurant, ton maquis ou ton activité ?** | Chez Mariam | `merchant_payload.nom` |
| 2 | **Comment s'appelle la formule, le combo ou l'offre que tu veux montrer ?** | Formule poulet braisé | `merchant_payload.offre` |
| 3 | **Qu'est-ce qu'il y a dedans ? Écris chaque plat, boisson ou produit avec sa quantité.** | 1 poulet braisé, 1 portion d'alloco et 2 jus | `merchant_payload.contenu` |
| 4 | **Quel est le prix exact de cette formule ?** | 5 000 FCFA pour 2 personnes | `merchant_payload.prix` |
| 5 | **Sur quel numéro WhatsApp les clients peuvent-ils commander ?** | +229 01 97 00 00 00 | `merchant_payload.whatsapp` |
| 6 | **Dans quel quartier ou quelle zone peut-on venir chercher la commande ?** | Kandi, près du marché central | `merchant_payload.quartier` |

## Décision de données proposée

- Les **six réponses sont obligatoires** pour T5.
- Le champ facultatif « accroche » de T1–T4 est remplacé par deux données utiles à cette offre : `offre` et `contenu`.
- Le contenu et les quantités doivent venir du commerçant. Le moteur n’ajoute aucun produit.
- Le prix peut inclure une condition vraie, par exemple « pour 2 personnes » ou une période réelle.

---

# 2. Les 4 scènes proposées

| Scène | Durée | Ce qui est filmé | Réponses utilisées |
|---|---:|---|---|
| S1 — LA FORMULE | 6 s | Toute la formule glisse dans l’image puis s’arrête au centre. | `merchant_payload.nom`, `merchant_payload.offre` |
| S2 — CE QU'ELLE CONTIENT | 8 s | Chaque élément et sa quantité apparaissent au même endroit. | `merchant_payload.contenu` |
| S3 — LE PRIX | 7 s | Toute la formule reste stable pour afficher le prix. | `merchant_payload.offre`, `merchant_payload.contenu`, `merchant_payload.prix` |
| S4 — COMMANDER | 9 s | La commande est fermée ou présentée, puis la fin reste stable. | `merchant_payload.nom`, `merchant_payload.whatsapp`, `merchant_payload.quartier` |

---

# 3. Contenu exact proposé pour les 12 écrans

## Scène 1 — LA FORMULE — 6 secondes

### ÉCRAN 01 — A / GUIDE

**SCÈNE 1 SUR 4 — 6 SECONDES**

**LA FORMULE**

**CE QUE TU VAS FILMER**

Montre toute la formule dès le début. On doit voir en même temps tous les plats, boissons ou produits qui sont vendus ensemble.

**À FILMER**

- Tous les éléments de la formule.
- Le plateau, la table, la boîte ou le sac qui les réunit.
- Une image propre où rien n'est caché.

**À ÉVITER**

- Oublier un élément de la formule.
- Cacher un produit derrière un autre.
- Filmer sur une table sale ou en désordre.

**CE QUE TU DOIS FAIRE**

Pose ton téléphone à un endroit stable, face à la table. Mets tous les éléments sur un plateau ou sur la table. Fais glisser doucement la formule dans l'image, puis arrête-la au centre.

**TU PEUX PARLER PENDANT QUE TU FILMES**

Tu peux parler en fon, yoruba, français, anglais ou dans une autre langue que tu maîtrises. Tu peux aussi ne pas parler si tu préfères.

**COMMENCER À FILMER**

### ÉCRAN 02 — B / ENREGISTREMENT

**SCÈNE 1 SUR 4 — 6 SECONDES**

**REC**

**FAIS GLISSER LA FORMULE DANS L'IMAGE**

Temps restant : 00:00 / 00:06

Son activé.

Vidéo verticale.

Arrêt automatique à la fin des 6 secondes.

### ÉCRAN 03 — C / VÉRIFICATION

**PRISE 1 — 0:06**

Son activé.

**EST-CE QU'ON VOIT TOUTE LA FORMULE ?**

- Tous les éléments sont visibles en même temps.
- Rien n'est caché derrière un autre produit.
- La formule s'arrête bien au centre de l'image.

**REFAIRE**

**SCÈNE SUIVANTE**

---

## Scène 2 — CE QU'ELLE CONTIENT — 8 secondes

### ÉCRAN 04 — A / GUIDE

**SCÈNE 2 SUR 4 — 8 SECONDES**

**CE QU'ELLE CONTIENT**

**CE QUE TU VAS FILMER**

Montre chaque élément de la formule, un après l'autre. Si la formule contient deux boissons ou trois morceaux, montre bien toute la quantité.

**À FILMER**

- Chaque plat, boisson ou produit inclus.
- La vraie quantité donnée au client.
- Chaque élément placé au même endroit dans l'image.

**À ÉVITER**

- Oublier un élément ou une quantité.
- Mettre un produit trop loin du téléphone.
- Bouger le téléphone entre les éléments.

**CE QUE TU DOIS FAIRE**

Pose le téléphone sans bouger, face à un endroit vide sur la table. Mets le premier élément au centre. Toutes les deux secondes, fais-le glisser sur le côté et mets l'élément suivant à la même place.

**TU PEUX PARLER PENDANT QUE TU FILMES**

Tu peux parler en fon, yoruba, français, anglais ou dans une autre langue que tu maîtrises. Tu peux aussi ne pas parler si tu préfères.

**COMMENCER À FILMER**

### ÉCRAN 05 — B / ENREGISTREMENT

**SCÈNE 2 SUR 4 — 8 SECONDES**

**REC**

**MONTRE CHAQUE ÉLÉMENT**

Temps restant : 00:00 / 00:08

Son activé.

Vidéo verticale.

Arrêt automatique à la fin des 8 secondes.

### ÉCRAN 06 — C / VÉRIFICATION

**PRISE 2 — 0:08**

Son activé.

**EST-CE QU'ON VOIT CHAQUE ÉLÉMENT ET SA QUANTITÉ ?**

- Tous les éléments annoncés sont montrés.
- Les quantités sont faciles à compter.
- Le téléphone ne bouge pas pendant les changements.

**REFAIRE**

**SCÈNE SUIVANTE**

---

## Scène 3 — LE PRIX — 7 secondes

### ÉCRAN 07 — A / GUIDE

**SCÈNE 3 SUR 4 — 7 SECONDES**

**LE PRIX**

**CE QUE TU VAS FILMER**

Montre encore toute la formule. Cette image servira à afficher le prix exact sans cacher les plats ou les boissons.

**À FILMER**

- Toute la formule réunie.
- Les quantités bien visibles.
- Un espace libre au-dessus ou à côté de la formule.

**À ÉVITER**

- Couper un plat ou une boisson dans l'image.
- Mettre la formule trop près du bord.
- Bouger le téléphone pendant la prise.

**CE QUE TU DOIS FAIRE**

Remets toute la formule sur la table. Pose ton téléphone à un endroit stable et cadre tous les éléments. Ne bouge plus jusqu'à la fin des 7 secondes.

**TU PEUX PARLER PENDANT QUE TU FILMES**

Tu peux parler en fon, yoruba, français, anglais ou dans une autre langue que tu maîtrises. Tu peux aussi ne pas parler si tu préfères.

**COMMENCER À FILMER**

### ÉCRAN 08 — B / ENREGISTREMENT

**SCÈNE 3 SUR 4 — 7 SECONDES**

**REC**

**GARDE TOUTE LA FORMULE DANS L'IMAGE**

Temps restant : 00:00 / 00:07

Son activé.

Vidéo verticale.

Arrêt automatique à la fin des 7 secondes.

### ÉCRAN 09 — C / VÉRIFICATION

**PRISE 3 — 0:07**

Son activé.

**EST-CE QU'ON VOIT TOUTE LA FORMULE SANS BOUGER ?**

- Tous les éléments restent visibles.
- Il y a une place libre pour afficher le prix.
- Le téléphone reste stable du début à la fin.

**REFAIRE**

**SCÈNE SUIVANTE**

---

## Scène 4 — COMMANDER — 9 secondes

### ÉCRAN 10 — A / GUIDE

**SCÈNE 4 SUR 4 — 9 SECONDES**

**COMMANDER**

**CE QUE TU VAS FILMER**

Montre la formule prête à partir. Ferme la boîte ou le sac, ou montre le plateau prêt à être remis au client.

**À FILMER**

- La boîte, le sac ou le plateau avec la formule.
- Tes mains quand tu fermes ou présentes la commande.
- La commande prête à être prise.

**À ÉVITER**

- Cacher complètement la commande avec tes mains.
- Montrer un emballage sale ou abîmé.
- Bouger le téléphone pendant les trois dernières secondes.

**CE QUE TU DOIS FAIRE**

Pose ton téléphone face à la table ou au comptoir. Ferme la boîte ou le sac, puis place la commande au centre. Pendant les trois dernières secondes, retire tes mains et ne bouge plus le téléphone.

**TU PEUX PARLER PENDANT QUE TU FILMES**

Tu peux parler en fon, yoruba, français, anglais ou dans une autre langue que tu maîtrises. Tu peux aussi ne pas parler si tu préfères.

**COMMENCER À FILMER**

### ÉCRAN 11 — B / ENREGISTREMENT

**SCÈNE 4 SUR 4 — 9 SECONDES**

**REC**

**FERME LA BOÎTE OU LE SAC PUIS NE BOUGE PLUS**

Temps restant : 00:00 / 00:09

Son activé.

Vidéo verticale.

Arrêt automatique à la fin des 9 secondes.

### ÉCRAN 12 — C / VÉRIFICATION

**PRISE 4 — 0:09**

Son activé.

**EST-CE QUE LA COMMANDE EST PRÊTE ET LA FIN BIEN STABLE ?**

- La boîte, le sac ou le plateau est bien visible.
- La commande paraît prête à être remise au client.
- Le téléphone ne bouge plus pendant les trois dernières secondes.

**REFAIRE**

**VOIR MON MONTAGE**

---

# 4. Ce qui n’est pas encore fait

- aucun dépôt GitHub T5 public ;
- aucun formulaire final ;
- aucun contrat exécutable ;
- aucun PNG ni simulation ;
- aucun rush téléchargé ou publié ;
- aucun montage T5.

La publication et l’implémentation commenceront seulement après validation du propriétaire.
