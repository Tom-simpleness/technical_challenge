Suite au process_path, je challenge la découverte du temps d'ingestion trop long avec Claude. Évidence sur le traitement line by line à transformer en traitement par chunk. Je challenge mes idées avec différents contextes : "est-ce applicable sur une prod fonctionnelle avec 100M de lignes ?". Pair-programming du nouveau tasks.py avec Claude, 5 commits atomiques pour que l'historique git raconte le cheminement et pas juste l'arrivée. Sur un projet, j'aurais créé une branche propore à ce fix/upgrade. 
 
 1. Ingestion CSV ligne par ligne
 
 What.
 import_transactions traite le CSV ligne par ligne. Pour chaque ligne, elle exécute trois opérations base de données :
  - un SELECT pour vérifier si la référence existe déjà 
  - un INSERT pour sauvegarder la nouvelle Transaction 
  - un UPDATE sur ImportJob pour incrémenter les compteurs 

  Les erreurs sont accumulées dans le champ error_log par concaténation de string (error_log += ...) et la ligne ImportJob complète est resave à chaque itération.

Why.
  - Performance. Baseline mesurée : 51s pour 5 000 lignes (~100 lignes/s). Extrapolé : ~17 minutes  
  pour 100k lignes et plusieurs heures pour 1M. Endpoint inutilisable en prod.
  - Database load. La colonne reference n'a pas d'index, donc chaque exists() fait un full table scan. 
  - Concurrency safety. La déduplication côté application est racy. Deux imports en parallèle peuvent passer le check exists() et insérer la même référence. Seule une contrainte UNIQUE en base garantit l'unicité.
  - Memory et write amplification. error_log += "..." reconstruit la string complète à chaque itération (immutabilité Python), et job.save() réécrit cette string en croissance à chaque ligne. 
  Avec beaucoup d'erreurs, le champ peut atteindre plusieurs MB avec un coût quadratique.
  - No atomicity. Chaque save() est sa propre transaction. Un crash en cours laisse un état incohérent sans stratégie de recovery.

  How.
  - Ajouter unique=True sur Transaction.reference via migration. La DB devient la source de vérité et ajoute l'index nécessaire.

warning: 
Sur une base existante, l'ajout de cette contrainte demanderait d'abord un audit des doublons. 
Sur une grosse table (100M+ lignes), la migration Django prend un lock qui bloque la table le temps de construire l'index.
En prod, je passerais par un *CREATE UNIQUE INDEX CONCURRENTLY* suivi d’un *ADD CONSTRAINT ... USING INDEX* pour éviter le downtime.
Pour le scope du challenge, la migration générée par défaut suffit.


  - Lire le CSV par chunks (pd.read_csv(..., chunksize=1000)).
  - Pour chaque chunk, construire une liste de Transaction(...) et persister avec bulk_create(batch, ignore_conflicts=True). Les doublons sont ignorés par la contrainte DB, les lignes valides insérées en une seule requête.
  - Mettre à jour les compteurs ImportJob une fois par chunk, pas par ligne.
  - Accumuler les erreurs dans une liste Python pendant le traitement, et persister error_log = "\n".join(errors) une fois par chunk (en même temps que l'update des compteurs)


  What next (pas critique) :
   - Déplacer le tracking des erreurs vers une table dédiée ImportJobError(job_id, row_index, error_type, message). Permet le bulk_insert par chunk, le filtrage par type d'erreur, et évite tout risque de bloat sur ImportJob.error_log.

  Résultat : 

51s → 1.9s sur 5000 lignes.
___________________________

2. Problème d'asynchone cassé.

Deuxième problème critique : la vue attend la fin de Celery via result.get avant de répondre → l'asynchrone est cassé. 

What.
La vue ImportView.post met la tâche Celery en file via import_transactions.delay(...) puis appelle immédiatement result.get(timeout=300) (views.py:40), qui poll Redis jusqu’à la fin du worker, jusqu’à 5 minutes.
La réponse HTTP n’est envoyée qu’une fois la tâche terminée.
L’endpoint /api/import/<job_id>/ existe déjà pour suivre l’avancement mais reste inutilisé à cause de ce comportement.

Why it matters.
Annule l’architecture asynchrone. Celery + Redis sont en place pour découpler le travail lent de la requête HTTP. Le .get() synchrone recouple les deux : on paie le coût d’infrastructure sans en récolter le bénéfice.
Timeouts client. Les clients HTTP abandonnent bien avant 5 minutes. Sur un CSV de 100k+ lignes, le client voit une erreur alors que l’import continue côté serveur.
Saturation des workers HTTP. Un worker Django bloqué sur .get() ne peut servir aucune autre requête. Avec 4 workers et 4 imports, tout le site est gelé.
Incohérence du design. L’endpoint /api/import/<job_id>/ expose déjà l’état du job, mais il n’est pas exploité.

How I fix it.
Supprimer result.get(timeout=300) et le refresh_from_db() associé dans ImportView.post.
Répondre immédiatement avec un HTTP 202 Accepted et le même JSON :
{"job_id": ..., "imported": 0, "failed": 0}
Le client suit la progression via GET /api/import/<job_id>/, déjà en place.
Contrat d’API. Les URLs et le format de réponse restent identiques. Seul le timing change : réponse immédiate au lieu d’attendre la fin de l’import. C’est une correction de comportement, pas une rupture.

Avant: 

$ time curl -i -F "file=@sample_transactions.csv" http://localhost:8010/api/import/
HTTP/1.1 200 OK
Date: Mon, 27 Apr 2026 11:22:14 GMT
Server: WSGIServer/0.2 CPython/3.11.14
Content-Type: application/json
Connection: close

{"job_id": 1, "imported": 4930, "failed": 70}
real    0m1.875s
user    0m0.047s
sys     0m0.060s

Après: 
$ time curl -i -F "file=@sample_transactions.csv" http://localhost:8010/api/import/
HTTP/1.1 202 Accepted
Date: Mon, 27 Apr 2026 11:26:50 GMT
Server: WSGIServer/0.2 CPython/3.11.14
Content-Type: application/json
Connection: close

{"job_id": 1, "imported": 0, "failed": 0}
real    0m0.498s
user    0m0.030s
sys     0m0.373s


curl -s http://localhost:8010/api/import/1/ | python -m json.tool

  Au début (juste après le POST, dans la première seconde) :
  {
      "id": 1,
      "status": "running",
      "total_rows": 1000,
      "imported_rows": 985,
      "failed_rows": 15,
      "started_at": "...",
      "finished_at": null
  }

  Au milieu :
  {
      "status": "running",
      "total_rows": 3000,
      "imported_rows": 2960,
      ...
  }

  À la fin:
  {
      "status": "done",
      "total_rows": 5000,
      "imported_rows": 4930,
      "failed_rows": 70,
      "finished_at": "..."
  }

On vois le job vivre. Le client peut faire autre chose, et il check quand il veut.
____________

3. correction de l'agrégation côté Python 

What.
 La vue SummaryView.get agrège les transactions par catégorie côté Python. Elle charge tout le queryset filtré (Transaction.objects.all() puis filtres date), itère en Python, accumule dans un dict avec summary[cat] += float(t.amount), puis trie et sérialise.

Why it matters.
  - Mémoire et latence. Sur un dataset réaliste (millions de lignes), tout le queryset est ramené dans le process Django. Plusieurs Go de RAM, plusieurs minutes de
   boucle. Le worker peut tomber en OOM ou bloquer le serveur, et la requête timeout.
  - Anti-pattern récurrent. Même problème que le fix 1 : on remonte la donnée côté appli pour faire un calcul que la DB sait exécuter en quelques millisecondes avec un GROUP BY.
  - Précision monétaire cassée. float(t.amount) convertit du Decimal en float avant la somme : on accumule des erreurs d'arrondi sur des centimes, ce qui n'est pas
   acceptable en domaine financier.
  - Pas d'index sur transacted_at (en complément). Combiné aux filtres date, le scan reste full-table.

How I fix it.
  - Remplacer la boucle Python par transactions.values("category").annotate(total=Sum("amount")).order_by("-total"). La DB exécute un seul SELECT category, SUM(amount) ... GROUP BY category ORDER BY ... et renvoie autant de lignes qu'il y a de catégories, peu importe le volume sous-jacent.
  - Sum sur un DecimalField retourne un Decimal — la sommation reste exacte. La conversion en float ne se fait qu'à la sérialisation JSON finale, là où elle est sans risque.
  - Le format de sortie reste strictement identique : liste d'objets {"category", "total"} triés par total décroissant.

Test 100k lignes :
Baselines
$ time curl -s "http://localhost:8010/api/summary/?from=2024-01-01&to=2024-12-31" > /dev/null

real    0m1.221s
user    0m0.060s
sys     0m0.030s

Après:

$ time curl -s "http://localhost:8010/api/summary/?from=2024-01-01&to=2024-12-31" > /dev/null

real    0m0.171s
user    0m0.046s
sys     0m0.046s