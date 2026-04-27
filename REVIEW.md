Suite au process_path, je challenge la découverte du temps d'ingestion trop long avec Claude. Évidence sur le traitement line by line à transformer en traitement par chunk. Je challenge mes idées avec différents contextes : "est-ce applicable sur une prod fonctionnelle avec 100M de lignes ?". Pair-programming du nouveau tasks.py avec Claude, 5 commits atomiques pour que l'historique git raconte le cheminement et pas juste l'arrivée. Sur un projet, j'aurais créé une branche propore à ce fix/upgrade. 
 
 1. Ingestion CSV ligne par ligne
 
 What.
 import_transactions traite le CSV ligne par ligne. Pour chaque ligne, elle exécute trois opérations base de données :
  - un SELECT pour vérifier si la référence existe déjà (tasks.py:28)
  - un INSERT pour sauvegarder la nouvelle Transaction (tasks.py:44)
  - un UPDATE sur ImportJob pour incrémenter les compteurs (tasks.py:31, :47, :52)

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