# RESTAURATION‑T5 — Reverse engineering V1 + T1

Date : 2026-11-18  
État : direction V1 + T1 approuvée ; adaptation T5 appliquée au premier candidat silencieux.

## Sources sélectionnées

- **V1** — [Combo individuel complet — Domino’s Ciudad Juárez](https://www.tiktok.com/@dominos.pizza.cd/video/7391902659709586694), 24,00 s, 480 × 848, 30 i/s.
- **T1** — [Dish swipe et camera whip — Socialdrop](https://www.tiktok.com/@socialdrop/video/7345936171647667461), 56,27 s, 576 × 1024, 30 i/s ; la démonstration finale occupe approximativement les dix dernières secondes.

Les copies privées ont seulement servi à mesurer les plans et les ruptures. Elles ne sont pas versionnées.

---

# 1. OBSERVÉ

## 1.1 V1 — grammaire de la vidéo choisie

| Temps approximatif | Observation factuelle |
|---:|---|
| 0,00–1,63 s | Ouverture immédiate sur le combo complet vu en plongée oblique ; les éléments sont déjà réunis. |
| 1,63–2,57 s | Présentateur derrière les boîtes ouvertes ; échelle humaine et preuve de quantité. |
| 2,57–4,30 s | Gros plan produit chaud dans le four ; rupture nette avec l’ouverture. |
| 4,30–5,97 s | Révélation d’un accompagnement dans son emballage. |
| 5,97–9,30 s | Retour au présentateur et à l’ensemble du combo ; gestes vers les différents éléments. |
| 9,30–13,10 s | Intercalaires courts de préparation : base, sauce, garniture et cuisson. |
| 13,10–14,47 s | Gros plan d’ajout de sauce sur le produit principal. |
| 14,47–16,47 s | Dégustation et réaction du présentateur. |
| 16,47–18,27 s | Gros plan d’ajout de sauce sur l’accompagnement. |
| 18,27–20,43 s | Deuxième dégustation et réaction. |
| 20,43–21,90 s | Coupe du produit principal avec un outil visible. |
| 21,90–24,00 s | Plan final large : les éléments sont montrés ensemble à hauteur de poitrine. |

### Principes observés

- le combo complet est visible dès la première seconde et revient à la fin ;
- les plans produit alternent avec une présence humaine ;
- les composants sont prouvés visuellement plutôt que seulement énumérés ;
- la publicité tient par des cuts courts, des gestes réels et des changements d’échelle ;
- le prix est communiqué par la parole/caption de la publication plutôt que par une carte de prix durable dans l’image ;
- l’identité de marque, les emballages et les couleurs appartiennent à la référence et ne sont pas transférables.

## 1.2 T1 — grammaire de transition choisie

### Démonstration de tournage observée

- plusieurs bols sont préparés et tenus à une hauteur comparable ;
- le cadre et l’arrière-plan restent presque identiques entre les prises ;
- une main ou un geste bref fournit un point de coupe ;
- chaque passage est tourné plusieurs fois afin de disposer de matière avant et après le balayage ;
- le changement de lieu et la lumière naturelle servent la lisibilité, mais ne constituent pas une obligation moteur.

### Montage final observé

- le sujet est centré dans une composition stable ;
- une impulsion latérale très rapide et un flou de mouvement masquent chaque coupe ;
- les variantes de plat occupent une position et une taille proches ;
- le spectateur perçoit un remplacement instantané plutôt qu’une transition décorative ;
- une sortie plus ample vers le ciel, suivie d’un retour au plat, clôt la séquence.

---

# 2. ADAPTÉ À T5

## 2.1 Ce qui est conservé comme logique

- révéler la formule complète immédiatement ;
- prouver séparément les éléments inclus ;
- revenir à un hero shot complet pour annoncer le prix ;
- utiliser l’emballage, le plateau et les mains réelles comme raccords ;
- terminer par une action de commande ou de remise du pack.

## 2.2 Ce qui est volontairement changé

- aucun présentateur n’est obligatoire ; les mains du commerçant suffisent ;
- le prix devient un élément visuel stable et lisible, pas seulement une parole ;
- la dégustation est facultative : T5 vend la composition et la valeur, contrairement à T4 qui vend l’expérience client ;
- les composants ne sont jamais inventés pour remplir l’image ;
- l’identité visuelle dépend du commerce et de T5, jamais de Domino’s ou Socialdrop ;
- le CTA final utilise les données réelles du commerçant.

## 2.3 Structure proposée 6/8/7/9 s

### S1 — LA FORMULE · 0–6 s

- plan complet dès l’image 1 ;
- une vue d’ensemble puis un angle plus proche ;
- nom du commerce et nom de la formule ;
- sortie par déplacement réel de la boîte ou du plateau.

### S2 — CE QU’ELLE CONTIENT · 6–14 s

- trois ou quatre fragments correspondant aux éléments réels ;
- quantité visible ou explicitement écrite ;
- matched item swaps inspirés de T1, avec position constante ;
- aucun composant ne doit être dissimulé par un effet.

### S3 — LE PRIX · 14–21 s

- retour à la formule complète ;
- prix exact en grande taille après stabilisation du plan ;
- condition ou période uniquement si le commerçant l’a fournie ;
- plan suffisamment long pour lire sans pause.

### S4 — COMMANDER · 21–30 s

- emballage, fermeture, remise ou point de retrait ;
- quartier/zone et WhatsApp ;
- proposition : verrouiller les trois dernières secondes sans mouvement de transition.

---

# 3. DÉCISION MOTEUR RETENUE POUR LE PREMIER CANDIDAT

## 3.1 Contrat temporel

- durée : 30,00 s ;
- format : 720 × 1280 ;
- cadence : 30 i/s ;
- total : 900 images ;
- frontières : images 180, 420 et 630 ;
- transitions courtes centrées sur les frontières, sans modifier les durées 6/8/7/9 s.

## 3.2 PACK SWIPE / MATCHED ITEM SWAP

Chaque raccord doit être déterministe et décrit dans le JSON :

- direction du vecteur ;
- fenêtre d’entrée et de sortie ;
- niveau maximal d’occlusion ;
- durée du flou ;
- position cible du produit ;
- fallback en cut sec si le rush ne fournit pas le mouvement nécessaire.

Le premier candidat utilise une zone de rupture de 8 images, sans masque permanent. Le moteur ne fabrique ni boîte, ni main, ni quantité absente du rush.

## 3.3 Règles de lisibilité

- le prix n’apparaît qu’une fois le plan S3 stabilisé ;
- le texte ne recouvre jamais plus d’un tiers de la formule ;
- WhatsApp et lieu restent fixes pendant la fin stable proposée ;
- aucun flash décoratif, aucune barre unie et aucun élément de marque de la référence ;
- les transitions internes de S2 ne peuvent pas réduire le temps utile de preuve des composants.

## 3.4 Frontières des approbations

La direction V1 + T1, puis les six questions et les douze écrans, ont été approuvés séparément. Le premier montage silencieux reste un candidat à juger. Aucune approbation n’est encore déclarée pour :

- une palette ou des polices de production finales ;
- une musique ou une voix ;
- le premier montage en tant que master final ;
- un déploiement Cloudflare.
