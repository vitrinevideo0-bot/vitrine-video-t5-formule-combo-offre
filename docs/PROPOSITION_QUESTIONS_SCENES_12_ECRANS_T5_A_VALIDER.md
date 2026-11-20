# T5 RESTAURATION — FORMULE, COMBO ET OFFRE

## Questions et 12 écrans corrigés à valider

**Statut : PROPOSITION LOCALE — NON PUBLIÉE SUR GITHUB**

**30 secondes · 4 scènes**

**Règle propriétaire :** Une seule formule par publicité. Le même plat, la même boisson et les mêmes accompagnements restent présents dans les quatre scènes.

---

# 1. Les 6 questions proposées

| N° | Question affichée | Exemple | Donnée JSON | Scènes |
|---:|---|---|---|---|
| 1 | **Comment s'appelle ton restaurant, ton maquis ou ton activité ?** | Chez Mariam | `merchant_payload.nom` | S1, S4 |
| 2 | **Comment s'appelle la formule, le combo ou l'offre que tu veux montrer ?** | Formule poulet braisé | `merchant_payload.offre` | S1, S3 |
| 3 | **Qu'est-ce qu'il y a dedans ? Écris chaque plat, boisson ou produit avec sa quantité.** | 1 poulet braisé, 1 portion d'alloco et 2 jus | `merchant_payload.contenu` | S1, S2, S3 |
| 4 | **Quel est le prix exact de cette formule ?** | 5 000 FCFA pour 2 personnes | `merchant_payload.prix` | S3 |
| 5 | **Sur quel numéro WhatsApp les clients peuvent-ils commander ?** | +229 01 97 00 00 00 | `merchant_payload.whatsapp` | S4 |
| 6 | **Dans quel quartier ou quelle zone peut-on venir chercher la commande ?** | Kandi, près du marché central | `merchant_payload.quartier` | S4 |

## Règles proposées pour les réponses

- Les six réponses sont obligatoires pour T5.
- Une publicité présente une seule formule.
- Le commerçant donne le contenu exact et les vraies quantités.
- Le moteur n’ajoute aucun plat, aucune boisson et aucun accompagnement.
- Le prix peut inclure une condition seulement si elle est vraie.

---

# 2. Les 4 scènes

| Scène | Durée | Réponses utilisées |
|---|---:|---|
| S1 — LA FORMULE | 6 s | `merchant_payload.nom`, `merchant_payload.offre`, `merchant_payload.contenu` |
| S2 — CE QU'IL Y A DANS LA FORMULE | 8 s | `merchant_payload.contenu` |
| S3 — LE PRIX | 7 s | `merchant_payload.offre`, `merchant_payload.prix` |
| S4 — COMMANDER | 9 s | `merchant_payload.nom`, `merchant_payload.whatsapp`, `merchant_payload.quartier` |

---

# 3. Texte corrigé des 12 écrans

## SCÈNE 1 — LA FORMULE

### ÉCRAN 01 — A / GUIDE

**SCÈNE 1 SUR 4 — 6 SECONDES**

**VOICI NOTRE FORMULE !**

**CE QUE TU VAS FILMER**

Montre toute ta formule. On doit voir le plat, la boisson et tout ce qui est vendu ensemble.

**À FILMER**

- Le plat et la boisson.
- Tout ce qui est dans la formule.
- Le plateau bien présenté.

**À ÉVITER**

- Oublier un élément.
- Cacher le plat ou la boisson.
- Filmer sur une table sale.

**CE QUE TU DOIS FAIRE**

Mets toute ta formule sur la table. Pose ton téléphone devant et montre tout en même temps. Ne touche plus au plateau pendant que tu filmes.

**TU PEUX PARLER PENDANT QUE TU FILMES**

Tu peux parler en fon, yoruba, français, anglais ou dans une autre langue que tu maîtrises. Tu peux aussi ne pas parler si tu préfères.

**EXEMPLE DE PHRASE (FACULTATIF)**

« Voici notre formule du jour ! Tout est prêt pour toi. »

**COMMENCER À FILMER**

### ÉCRAN 02 — B / ENREGISTREMENT

**SCÈNE 1 SUR 4 — 6 SECONDES**

**REC**

00:00 / 00:06

**MONTRE TOUTE TA FORMULE.**

Micro activé.

Vidéo verticale.

Arrêt automatique à la fin des 6 secondes.

### ÉCRAN 03 — C / VÉRIFICATION

**PRISE 1 — 0:06**

Son activé.

**EST-CE QU'ON VOIT BIEN TOUTE LA FORMULE ?**

- Le plat et la boisson sont visibles.
- Rien n'est caché.
- Toute la formule est bien dans la vidéo.

**REFAIRE**

**SCÈNE SUIVANTE**

---

## SCÈNE 2 — CE QU'IL Y A DANS LA FORMULE

### ÉCRAN 04 — A / GUIDE

**SCÈNE 2 SUR 4 — 8 SECONDES**

**REGARDE TOUT CE QU'IL Y A DEDANS !**

**CE QUE TU VAS FILMER**

Montre de plus près les différents éléments de ta formule pour que les clients voient bien ce qu'ils vont recevoir.

**À FILMER**

- Le plat principal.
- La boisson.
- L'accompagnement, s'il y en a.

**À ÉVITER**

- Cacher un élément.
- Mettre ta main devant le plat.
- Filmer trop vite.

**CE QUE TU DOIS FAIRE**

Garde ton téléphone posé. Avec ton doigt, montre le plat, puis la boisson et le reste de la formule.

**TU PEUX PARLER PENDANT QUE TU FILMES**

Tu peux parler en fon, yoruba, français, anglais ou dans une autre langue que tu maîtrises. Tu peux aussi ne pas parler si tu préfères.

**EXEMPLE DE PHRASE (FACULTATIF)**

« Voici le plat, la boisson et tout ce qui accompagne notre formule ! »

**COMMENCER À FILMER**

### ÉCRAN 05 — B / ENREGISTREMENT

**SCÈNE 2 SUR 4 — 8 SECONDES**

**REC**

00:00 / 00:08

**MONTRE LE PLAT, LA BOISSON ET L'ACCOMPAGNEMENT.**

Micro activé.

Vidéo verticale.

Arrêt automatique à la fin des 8 secondes.

### ÉCRAN 06 — C / VÉRIFICATION

**PRISE 2 — 0:08**

Son activé.

**EST-CE QU'ON VOIT BIEN CE QU'IL Y A DANS LA FORMULE ?**

- Le plat est bien visible.
- La boisson est bien visible.
- On voit aussi les accompagnements.

**REFAIRE**

**SCÈNE SUIVANTE**

---

## SCÈNE 3 — LE PRIX

### ÉCRAN 07 — A / GUIDE

**SCÈNE 3 SUR 4 — 7 SECONDES**

**VOICI LE PRIX DE LA FORMULE !**

**CE QUE TU VAS FILMER**

Montre encore toute ta formule. Le prix sera ajouté sur ta vidéo.

**À FILMER**

- Le plat et la boisson.
- Tous les éléments de la formule.
- Une belle présentation sur la table.

**À ÉVITER**

- Cacher une partie du plat.
- Mettre le plateau trop près du bord.
- Bouger le téléphone.

**CE QUE TU DOIS FAIRE**

Laisse toute la formule sur la table. Pose ton téléphone bien devant et filme sans le bouger.

**TU PEUX PARLER PENDANT QUE TU FILMES**

Tu peux parler en fon, yoruba, français, anglais ou dans une autre langue que tu maîtrises. Tu peux aussi ne pas parler si tu préfères.

**EXEMPLE DE PHRASE (FACULTATIF)**

« Tout ça est disponible au prix affiché ! »

**COMMENCER À FILMER**

### ÉCRAN 08 — B / ENREGISTREMENT

**SCÈNE 3 SUR 4 — 7 SECONDES**

**REC**

00:00 / 00:07

**GARDE TOUTE LA FORMULE DANS LA VIDÉO.**

Micro activé.

Vidéo verticale.

Arrêt automatique à la fin des 7 secondes.

### ÉCRAN 09 — C / VÉRIFICATION

**PRISE 3 — 0:07**

Son activé.

**EST-CE QU'ON VOIT BIEN TOUTE LA FORMULE ?**

- Tous les éléments sont visibles.
- Le plat est bien présenté.
- La vidéo reste stable.

**REFAIRE**

**SCÈNE SUIVANTE**

---

## SCÈNE 4 — COMMANDER

### ÉCRAN 10 — A / GUIDE

**SCÈNE 4 SUR 4 — 9 SECONDES**

**ENVIE DE COMMANDER ?**

**CE QUE TU VAS FILMER**

Montre ta formule prête à être servie. Fais une dernière belle présentation pour donner envie aux clients de commander.

**À FILMER**

- Toute la formule prête.
- Le plat et la boisson bien présentés.
- Le plateau ou la commande.

**À ÉVITER**

- Cacher une partie de la formule.
- Montrer une table sale.
- Bouger le téléphone à la fin.

**CE QUE TU DOIS FAIRE**

Mets ta formule devant ton téléphone. Filme-la bien et garde ton téléphone sans bouger jusqu'à la fin.

**TU PEUX PARLER PENDANT QUE TU FILMES**

Tu peux parler en fon, yoruba, français, anglais ou dans une autre langue que tu maîtrises. Tu peux aussi ne pas parler si tu préfères.

**EXEMPLE DE PHRASE (FACULTATIF)**

« Tu veux cette formule ? Écris-nous sur WhatsApp pour commander ! »

**COMMENCER À FILMER**

### ÉCRAN 11 — B / ENREGISTREMENT

**SCÈNE 4 SUR 4 — 9 SECONDES**

**REC**

00:00 / 00:09

**MONTRE TA FORMULE BIEN PRÉSENTÉE.**

Micro activé.

Vidéo verticale.

Arrêt automatique à la fin des 9 secondes.

### ÉCRAN 12 — C / VÉRIFICATION

**PRISE 4 — 0:09**

Son activé.

**EST-CE QUE TA FORMULE EST BIEN PRÉSENTÉE ?**

- Le plat et la boisson sont visibles.
- Toute la formule est bien présentée.
- La vidéo reste stable jusqu'à la fin.

**REFAIRE**

**VOIR MON MONTAGE**

---

# 4. Interprétation des boutons collés dans le message

- `REFAIRESCÈNE SUIVANTE` devient deux boutons : **REFAIRE** et **SCÈNE SUIVANTE**.
- `REFAIREVOIR MON MONTAGE` devient deux boutons : **REFAIRE** et **VOIR MON MONTAGE**.

# 5. État de publication

- dépôt GitHub T5 public : **non créé** ;
- formulaire et contrat exécutables : **non créés** ;
- PNG et simulation : **non créés** ;
- rushs et montage : **non commencés**.

La publication commencera seulement après confirmation des six questions.
