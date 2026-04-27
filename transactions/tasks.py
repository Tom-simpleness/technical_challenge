import pandas as pd
from datetime import datetime
from celery import shared_task
from django.utils import timezone

from .models import ImportJob, Transaction


@shared_task
def import_transactions(job_id, file_path):
    """
    Reads the uploaded CSV and imports all transactions into the database.
    Called asynchronously after the file is saved to disk.
    """
    job = ImportJob.objects.get(id=job_id)
    job.status = "running"
    job.save()

    for chunk in pd.read_csv(file_path, chunksize=1000):
        job.total_rows += len(chunk)
        job.save()

        batch = []
        for index, row in chunk.iterrows():
            try:
                t = Transaction(
                    reference=row["reference"],
                    amount=row["amount"],
                    currency=row["currency"],
                    category=row["category"],
                    merchant=row["merchant"],
                    status=row["status"],
                    transacted_at=datetime.fromisoformat(str(row["transacted_at"])),
                )
                batch.append(t)
            except Exception as e:
                job.failed_rows += 1
                job.error_log += f"Error on row {index} ({row.get('reference', '?')}): {e}\n"
                job.save()

        refs_in_batch = [t.reference for t in batch]
        existing_refs = set(
            Transaction.objects.filter(reference__in=refs_in_batch).values_list("reference", flat=True)
        )

        seen = set()
        to_insert = []
        for t in batch:
            if t.reference in existing_refs or t.reference in seen:
                job.failed_rows += 1
                job.error_log += f"Duplicate: {t.reference}\n"
                job.save()
            else:
                seen.add(t.reference)
                to_insert.append(t)

        Transaction.objects.bulk_create(to_insert, batch_size=1000, ignore_conflicts=True)
        job.imported_rows += len(to_insert)
        job.save()

    job.status = "done"
    job.finished_at = timezone.now()
    job.save()
