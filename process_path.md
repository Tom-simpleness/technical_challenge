Process_path.md

1_Discovering ReadMe.md

Première étape lecture du Readme.md je retiens 
"problems that would become apparent in production with real data volumes." et "python generate_csv.py" et
"The stack: **Django · Celery · Redis · PostgreSQL · pandas**"

Premières idées qui me viennent en tête on est donc sur une recherche de dysfonctionnement fonctionnel sur un gros volume de data. On va mettre de côté potentiellement les problèmes d'archi/SOLID/sécu dans un premier temps et focus sur un pipeline de donnée. 

Problèmes qui me viennent possiblement en tête :
- état de la data : doublon, manquante etc...
- import de la donnée : traitement du csv, fichier trop lourd, problème de chunk, problème de loop/loop + traitement pré queue, problème api
- problème de queue : bonne structure de message, bonne structure de file, limit max de redis (+ rare)..
- consommation de la queue : problème de consommation/traitement, data loop, atomicité, worker suffisant,...
- mise à disposition de la data : temps de réponse, temps de chargement, message http, asynchronicité...

2_discovering Docker-compose.yml

Lecture du docker compose pour avoir une idée du system design du projet 

  Django   → le serveur HTTP (gère les requêtes utilisateur)
  Celery   → le worker (exécute les tâches longues en arrière-plan) + API producteur/consommateur
  Redis    → le broker (transporte les messages entre Django et Celery)
  Postgres → le stockage durable (transactions + import jobs)
  pandas   → la lib utilisée DANS la tâche pour parser le CSV

3_discovering migrations files + models.py.

Lecture rapide des fichiers de migrations/models pour avoir une représentation mentale de la db 

4_ génération du csv + lecture du script de génération 

Remarque : quelques doublons/errors incrustés au milieu de 5000 lignes 

5_curl import

baseline avant fix : 

$  time curl -F "file=@sample_transactions.csv" http://localhost:8010/api/import/
{"job_id": 1, "imported": 4930, "failed": 70}
real    0m51.443s

remarque : Le code actuel traite 100 lignes/seconde. À l'échelle de 1M de lignes, c'est inutilisable.

Je pense que c'est déjà un bon point de départ qui va m'amener à creuser tasks.py

En parallèle je demande un état des lieux du projet à Claude en l'orientant sur ces problématiques data et le temps d'ingestion du document 
