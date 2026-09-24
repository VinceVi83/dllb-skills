Entrée : le fichier métier du skill (injection).
Sortie : UNIQUEMENT le contenu de `config_example.yaml` du skill.

## 1. Rôle

`cfg` (common.conf_manager) charge le YAML en objet à accès pointé :
    cfg.<scope>.<cle>.<sous_cle>
Le YAML est l'UNIQUE source des valeurs configurables du skill.
Règle absolue : toute valeur qui n'est pas une constante métier immuable
DOIT y apparaître. Aucune valeur "magique" en dur dans le code métier.

## 2. Ce qui va dans le YAML (par ordre de priorité)

1. Secrets / identifiants : api_key, token, password, client_id, secret.
   → valeur `""` ou `"CHANGEME"`. JAMAIS une vraie valeur.
2. Endpoints / URLs : base_url, api_url, host, port, webhook.
3. Chemins : dossier de sortie, fichiers de données, templates, icônes.
4. Numériques : timeouts, intervalles, retries, seuils, limites, tailles.
5. Comportements : boolean flags, modes, niveaux de log, canaux (Discord…).
6. Identités : nom du skill, id de tâche cron, description, locale, tz.

## 3. Structure

- Clé racine = nom du skill :
      <skill>:
          ...
- Regrouper par thème (api / paths / behavior / misc), pas en vrac plat.
  Un sous-bloc par source externe ou par composant du métier.
- Valeur par défaut = celle utilisée dans le code si présente,
  sinon une valeur neutre plausible et sûre.
- Commenter (`#`) chaque clé non évidente : unité, format attendu, domaine.

## 4. Ce qui NE va PAS dans le YAML

- Valeurs calculées au runtime (timestamps, hash, id généré).
- Constantes métier immuables (ex : nom d'un fichier de mapping figé).
- Données statiques lourdes (dict de dict de référence) → fichiers dédiés.
- Ce qui relève de secrets d'infra partagés (déjà dans le cfg global).

## 5. Checklist

- [ ] Tout paramètre lu/écrit dans le code métier a sa clé ici.
- [ ] Aucun secret réel, uniquement `""` / `"CHANGEME"`.
- [ ] Groupement logique par thème.
- [ ] Chaque clé non triviale est commentée.
- [ ] Valeurs par défaut cohérentes avec le code métier.
- [ ] YAML valide (indentation 2 espaces, pas de tab).

## 6. Format de réponse

    # fichier: <chemin>/config_example.yaml
    ```yaml
    ...contenu...
    ```
Rien d'autre : ni explication, ni commentaire hors YAML.