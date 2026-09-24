Entrée : un ou plusieurs fichiers injectés — au minimum le fichier métier
(classe ou module), éventuellement un router/bloc-préférence et/ou un template
de prompt, plus une consigne d'adaptation si besoin.
Sortie : le `service.py` du skill qui l'expose comme tools MCP, et les
`agents/*.md` référencés par les fichiers injectés.

Aucun autre fichier. Un fichier injecté n'est MODIFIÉ que si la consigne le
demande explicitement ; sinon il est recopié tel quel ou laissé intact.

## 1. Rôle de service.py

Le serveur scanne `skills/*/service.py` au démarrage. Devient TOOL :
- toute fonction PUBLIQUE (sans `_`) avec docstring, définie dans le module ;
- toute méthode PUBLIQUE avec docstring d'une classe définie dans le module.

Donc :
- 1 fonction = 1 tool. Docstring obligatoire (sinon tool invisible au LLM).
- Signature + type hints = schéma d'appel vu par le LLM appelant.

## 2. Depuis un fichier métier

Le fichier métier = logique interne (API, parsing, calcul). service.py = façade
qui l'expose. Ne PAS recopier la logique métier dans service.py.

- Classe instanciable → singleton module-level :
      calendar = CalendarService()
  puis chaque tool appelle `calendar.<methode>(...)`.
- Fonctions module-level → import direct, appel direct.
- Classe à état / coûteuse à init → singleton, jamais `Class()` par appel.
- Méthodes `_privées` du métier → non exposées, utilisables en interne.
- Méthodes publiques du métier → exposées une à une comme tools (voir §3).

## 3. Nommage & docstrings des tools

- Suffixe d'action : `get_`, `fetch_`, `notify_`, `send_`, `ask_`, `list_`.
- Renommer si la méthode métier n'est pas explicite
  (`events_in_days` → `get_events_in_days`).
- Docstring côté service = écrite de zéro, orientée MCP (message pour le LLM
  appelant), JAMAIS reprise du métier :
    * 1re ligne = phrase d'action claire à l'impératif.
    * Bloc `Args:` avec type et exemple pour chaque paramètre.
- Les docstrings du fichier métier appartiennent au dev : NE PAS les lire,
  les réécrire ou les déplacer. Deux publics distincts.
- Type hints sur TOUS les paramètres et le retour.
- `logger.info(...)` en tête de tool. Pas de `print()`.
- Retour `str` lisible OU structure JSON-sérialisable.

## 4. Imports autorisés

    from common.conf_manager import cfg, Utils
    from common.llm_client import llm
    from skills.<skill>.<module_metier> import <classe/fonctions>

Rien d'autre de `common.*`. Stdlib / tiers libres.
`logger = logging.getLogger(__name__)`. Pas de `setup_logging()`.
Zéro hardcoding : URL, token, chemins, ville, modèle → `cfg`.

## 5. Fichiers injectés : router / template de prompt

Si un router ou un bloc de helpers est injecté :
- le recopier VERBATIM dans service.py, seuls `<skill>` et `<domain>` (noms du
  skill) sont remplacés ;
- ne JAMAIS le réécrire, l'optimiser, le factoriser ou changer sa signature ;
- ne pas ajouter un second `ask_<domain>` s'il en contient déjà un ;
- reporter les imports qu'il exige (`inspect`, `json`, `datetime`, …) ;
- un helper injecté ne devient PAS un tool : préfixe `_`, et `ask_<domain>`
  est exclu du scan (cf. `name.startswith(("ask", "_"))`).

Si aucun router n'est injecté : ne pas en produire, ne pas en inventer.
Un seul tool → pas de router.

## 6. Prompts (agents/*.md)

Générer un `agents/<nom>.md` SEULEMENT si un fichier injecté le référence
(ex. `cfg.agents.<skill>_router`, `cfg.agents.<skill>_secretary`).
- Reprendre la forme et les placeholders du template injecté, VERBATIM
  (`{{TOOLS}}`, `{{NOW}}`, `{{…}}` : jamais renommés ni retirés).
- Router : rôle de routage, injecte `{{TOOLS}}`, sortie JSON stricte
  `{"tool": ..., "arguments": {...}}` ou `{"tool": null, "reason": ...}`,
  aucune explication hors JSON, seuls les noms listés autorisés, arguments
  keyés sur `parameters`.
- Secretary : reformulation pour l'humain, injecte `{{NOW}}`, reçoit
  `# User request` + `# Raw data`, n'expose jamais les appels d'outils.
- Sans template injecté : se conformer à la structure ci-dessus.
- Jamais de prompt inline dans le code.

## 7. Adapter le fichier métier

Uniquement sur consigne explicite. Sinon, produire service.py contre le fichier
tel quel. Si le métier ne se prête pas à l'exposition (méthode sans typage,
retour non sérialisable, etc.) → le SIGNALER et proposer l'adaptation minimale
au lieu de la faire d'office.

## 8. Checklist

- [ ] Sortie limitée à `service.py` + `agents/*.md` (+ fichier injecté si
      adaptation demandée).
- [ ] Aucun fichier non demandé, aucun router non injecté.
- [ ] Instance(s) métier créée(s) au niveau module, pas dans les tools.
- [ ] Chaque tool = fonction publique, docstring écrite pour le MCP.
- [ ] Docstrings du métier non lues / non réutilisées / non modifiées.
- [ ] Type hints partout, retour str ou JSON-sérialisable.
- [ ] `logger.info(...)` en tête, pas de `print()`.
- [ ] Aucun hardcoding : tout via `cfg`.
- [ ] Prompts dans `agents/*.md`, référencés via `cfg.agents.*`.
- [ ] Imports internes limités à `cfg, Utils` + `llm` + fichier métier.
- [ ] Router injecté → recopié VERBATIM, seuls `<skill>`/`<domain>` changés.
- [ ] Aucun fake/stub : API manquante → `# TODO: …` ou question.
- [ ] Fichier métier intact sauf consigne d'adaptation explicite.

## 9. Format de réponse

1. `# fichier: skills/<skill>/service.py` + code.
2. `# fichier: skills/<skill>/agents/<nom>.md` + contenu (un par prompt requis).
3. `# fichier: skills/<skill>/<module>.py` + code (SEULEMENT si adaptation demandée).
4. Rien d'autre.