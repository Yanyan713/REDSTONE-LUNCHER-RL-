# Redstone Launcher (RL)

Un lanceur Minecraft complet, open-source et personnalisable, pour Windows.

> Copyright (c) 2026 yyley2015@hotmail.com — Tous droits réservés.

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Démarrage](#démarrage)
- [Utilisation](#utilisation)
  - [Sélection de version](#sélection-de-version)
  - [Mode Vanilla ou Shaders](#mode-vanilla-ou-shaders)
  - [Comptes](#comptes)
  - [Skins](#skins)
  - [Mods](#mods)
  - [Minecraft Bedrock](#minecraft-bedrock)
  - [Réglages](#réglages)
- [Dépannage](#dépannage)
- [Architecture technique](#architecture-technique)
- [Licence](#licence)

---

## Fonctionnalités

- **Toutes les versions Minecraft Java** : Alpha, Beta, Snapshot, Release — depuis 2010 jusqu'à la dernière version.
- **Mise à jour automatique** : connecté aux serveurs de Mojang, les nouvelles versions apparaissent automatiquement.
- **Téléchargement du jeu et de Java** : Java est téléchargé automatiquement si nécessaire (Adoptium / Temurin).
- **Choix du dossier d'installation** : installe le jeu où tu veux.
- **Comptes** : connexion Microsoft (OAuth) ou compte local (hors-ligne, à des fins éducatives).
- **Skins personnalisés** : upload de skin PNG, appliqué automatiquement via un resource pack.
- **Mods** :
  - Mode **Vanilla** (sans mods).
  - Mode **Shaders** : Fabric + Sodium + Sodium Extra + Entity Culling + Iris + 3 packs de shaders (BSL, Complementary, SEUS), tout pré-installé.
  - Upload de mods `.jar` personnalisés.
- **Minecraft Bedrock** : lancement de la version Bedrock installée via le Microsoft Store, gestion des resource packs `.mcpack`.
- **Proxy local** : support d'un proxy HTTP local pour les téléchargements.
- **Multi-miroirs** : plusieurs sources de téléchargement (Mojang, BMCLAPI, MCBBS) avec basculement automatique.
- **Reprise des téléchargements** : les téléchargements interrompus reprennent là où ils se sont arrêtés (ne bloquent plus à 99,9 %).

---

## Prérequis

- **Windows 10 ou 11** (64 bits).
- **Python 3.8+** (pour exécuter le lanceur depuis les sources).
- **Connexion Internet** (pour télécharger le jeu, Java, les mods et les shaders).
- **Compte Microsoft** (pour jouer en ligne avec un compte officiel) — optionnel, le mode hors-ligne est disponible.
- **Minecraft Bedrock** (optionnel) : installé via le Microsoft Store pour la fonctionnalité Bedrock.

---

## Installation

1. Télécharge ou clone le projet dans un dossier de ton choix.
2. Assure-toi que Python 3.8+ est installé :
   ```
   python --version
   ```
3. Aucune dépendance Python supplémentaire n'est nécessaire (le lanceur utilise uniquement la bibliothèque standard).

---

## Démarrage

Double-clique sur `start.bat` ou exécute dans un terminal :

```
cd redstone-launcher
python -m launcher
```

Le serveur démarre sur `http://127.0.0.1:8765/`. Ouvre cette adresse dans ton navigateur.

> Le lanceur fonctionne en local : aucun serveur distant n'est utilisé, tes données restent sur ton ordinateur.

---

## Utilisation

### Sélection de version

1. Dans la section **Versions**, choisis une catégorie :
   - **Release** : versions stables officielles.
   - **Snapshot** : versions de développement.
   - **Beta** : anciennes versions beta (2010-2011).
   - **Alpha** : toutes premières versions (2010).
2. Clique sur une version pour la sélectionner.
3. Si la version n'est pas téléchargée, clique sur **Télécharger**.
4. Une fois téléchargée, clique sur **JOUER**.

### Mode Vanilla ou Shaders

- **Vanilla** : Minecraft sans aucun mod, comme la version officielle.
- **Shaders** : installe automatiquement Fabric + Sodium + Sodium Extra + Entity Culling + Iris, ainsi que 3 packs de shaders :
  - BSL Shaders
  - Complementary Shaders
  - SEUS (Sonic Ether's Unbelievable Shaders)

La première fois que tu lances en mode Shaders, tous les mods et shaders sont téléchargés et installés automatiquement. Les fois suivantes, c'est instantané.

### Comptes

Clique sur **Comptes** dans l'en-tête.

- **Compte Microsoft** : clique sur « Connecter avec Microsoft ». Une fenêtre d'authentification OAuth s'ouvre. Connecte-toi avec ton compte Microsoft qui possède Minecraft.
- **Compte local (hors-ligne)** : entre un nom d'utilisateur et clique sur « Ajouter un compte local ». Ce mode permet de jouer en solo sans connexion Internet, à des fins éducatives.

Plusieurs comptes peuvent être ajoutés et switchés facilement.

### Skins

1. Clique sur **Comptes** → sélectionne un compte.
2. Clique sur **Changer le skin**.
3. Sélectionne un fichier PNG de skin (format 64x64 ou 64x32).
4. Le skin est appliqué automatiquement via un resource pack généré pour la version sélectionnée.

> Le skin fonctionne en solo et sur les serveurs qui acceptent les comptes hors-ligne. Pour les serveurs premium, le skin est lié à ton compte Microsoft.

### Mods

Clique sur **Mods** dans la section de la version sélectionnée.

- **Voir les mods installés** : liste avec activation/désactivation.
- **Ajouter un mod** : glisse-dépose un fichier `.jar` ou clique pour choisir.
- **Supprimer un mod** : clique sur la croix.
- **Ouvrir le dossier mods** : accès direct au dossier.

En mode Shaders, les mods de base (Sodium, Iris, etc.) sont protégés et ne peuvent pas être supprimés individuellement.

### Minecraft Bedrock

Clique sur **Bedrock** dans l'en-tête.

- **Lancer Bedrock** : clique sur « JOUER À BEDROCK ». Le jeu se lance via le Microsoft Store.
- **Resource packs** :
  - Glisse-dépose un fichier `.mcpack` pour l'installer.
  - Liste des packs installés avec suppression.
  - Bouton pour ouvrir le dossier des resource packs.

> Bedrock utilise ton compte Microsoft connecté au Store. Aucune connexion supplémentaire n'est nécessaire dans le lanceur. Les anciennes versions Bedrock ne sont pas disponibles officiellement (contrairement à Java).

### Réglages

Clique sur **Réglages** dans l'en-tête.

- **Dossier d'installation** : choisis où le jeu est installé (par défaut `%APPDATA%\.minecraft`).
- **Mémoire allouée (RAM)** : quantité de RAM réservée à Minecraft (par défaut 4 Go).
- **Proxy local** : adresse d'un proxy HTTP local (ex: `http://127.0.0.1:7890`) pour les téléchargements.
- **Miroir de téléchargement** : choix entre Mojang (officiel), BMCLAPI, et MCBBS.

---

## Dépannage

### Le jeu crash avec le code 1

- Vérifie que Java est bien installé et à jour.
- Vérifie les logs dans `[dossier d'installation]\logs\`.
- Essaie d'augmenter la RAM allouée dans les Réglages.
- Désactive les mods récemment ajoutés.

### Le jeu se ferme avec le code 4294967295 (0xFFFFFFFF)

- C'est souvent un problème de carte graphique ou de pilotes.
- Mets à jour tes pilotes graphiques (NVIDIA / AMD / Intel).
- Essaie de lancer en mode Vanilla (sans shaders).

### Les téléchargements s'arrêtent à 99,9 %

- Ce bug a été corrigé. Les téléchargements utilisent maintenant la reprise et la vérification de hash.
- Si le problème persiste, change de miroir dans les Réglages.
- Vérifie ta connexion Internet et ton proxy.

### Rien ne se télécharge

- Vérifie ta connexion Internet.
- Si tu utilises un proxy, vérifie qu'il est bien configuré dans les Réglages.
- Change de miroir de téléchargement.
- Vérifie que le dossier d'installation est accessible en écriture.

### Le skin ne s'applique pas

- Le skin est appliqué via un resource pack généré automatiquement.
- Vérifie que le resource pack est activé dans Minecraft → Options → Resource Packs.
- Le pack est régénéré à chaque nouvelle version si incompatible.

### Minecraft Bedrock ne se lance pas

- Vérifie que Minecraft Bedrock est bien installé via le Microsoft Store.
- Essaie de le lancer manuellement depuis le menu Démarrer pour confirmer qu'il fonctionne.
- Le lanceur utilise `cmd /c start shell:appsFolder\...!Game` pour le lancer.

### « name 'st' is not defined »

- Ce bug a été corrigé. Redémarre le serveur.

---

## Architecture technique

```
redstone-launcher/
├── launcher/
│   ├── __init__.py      # Point d'entrée, démarre le serveur HTTP
│   ├── server.py        # Serveur HTTP local + API REST
│   ├── state.py         # État global (config, comptes, progression)
│   ├── versions.py      # Gestion des versions (manifest Mojang, catégories)
│   ├── download.py      # Téléchargements multi-miroirs avec reprise
│   ├── java.py          # Gestion de Java (détection, téléchargement)
│   ├── launch.py        # Lancement de Minecraft Java
│   ├── auth.py          # Authentification Microsoft OAuth + comptes locaux
│   ├── fabric.py        # Installation de Fabric Loader
│   ├── mods.py          # Gestion des mods (upload, activation, suppression)
│   ├── shaders_pack.py  # Pack Shaders pré-configuré (Sodium, Iris, etc.)
│   ├── skin.py          # Gestion des skins (génération de resource pack)
│   ├── bedrock.py       # Gestion de Minecraft Bedrock (lancement, resource packs)
│   └── paths.py         # Gestion des chemins de fichiers
├── web/
│   ├── index.html       # Interface utilisateur
│   ├── style.css        # Styles (thème GitHub / Modrinth)
│   └── app.js           # Logique frontend (appels API, rendu)
├── start.bat            # Script de démarrage Windows
├── LICENSE              # Licence
└── README.md            # Ce fichier
```

### API REST

Le serveur expose une API REST sur `http://127.0.0.1:8765/api/` :

| Endpoint | Méthode | Description |
|---|---|---|
| `/versions` | GET | Liste des versions (avec filtre par type) |
| `/versions/{id}` | GET | Détails d'une version |
| `/versions/{id}/download` | POST | Télécharger une version |
| `/launch` | POST | Lancer Minecraft |
| `/auth/microsoft` | POST | Connexion Microsoft OAuth |
| `/auth/local` | POST | Ajouter un compte local |
| `/accounts` | GET | Liste des comptes |
| `/mods` | GET/POST | Gestion des mods |
| `/mods/{name}` | DELETE | Supprimer un mod |
| `/shaders/install` | POST | Installer le pack Shaders |
| `/bedrock/status` | GET | État de Minecraft Bedrock |
| `/bedrock/launch` | POST | Lancer Minecraft Bedrock |
| `/bedrock/packs` | GET/POST | Resource packs Bedrock |
| `/settings` | GET/POST | Paramètres |
| `/progress` | GET | Progression des téléchargements |

---

## Licence

Ce logiciel est la propriété de **yyley2015@hotmail.com**. Tous droits réservés.

Voir le fichier [LICENSE](LICENSE) pour les détails complets.

Minecraft est une marque de Mojang AB / Microsoft Corporation. Ce logiciel n'est pas affilié à, endossé par, ou sponsorisé par Mojang AB ou Microsoft Corporation.

---

*Pour toute question ou suggestion : yyley2015@hotmail.com*
