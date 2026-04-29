import pandas as pd
from datetime import datetime
from decimal import Decimal
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

    errors = []

    try:
        for chunk in pd.read_csv(file_path, chunksize=1000):
            chunk_failed = 0

            batch = []
            for index, row in chunk.iterrows():
                try:
                    if row.isna().any():
                        missing = list(row.index[row.isna()])
                        raise ValueError(f"empty fields: {missing}")
                    t = Transaction(
                        reference=row["reference"],
                        amount=Decimal(str(row["amount"])),
                        currency=row["currency"],
                        category=row["category"],
                        merchant=row["merchant"],
                        status=row["status"],
                        transacted_at=datetime.fromisoformat(str(row["transacted_at"])),
                    )
                    batch.append(t)
                except Exception as e:
                    chunk_failed += 1
                    errors.append(f"Error on row {index} ({row.get('reference', '?')}): {e}")

            refs_in_batch = [t.reference for t in batch]
            existing_refs = set(
                Transaction.objects.filter(reference__in=refs_in_batch).values_list("reference", flat=True)
            )

            seen = set()
            to_insert = []
            for t in batch:
                if t.reference in existing_refs or t.reference in seen:
                    chunk_failed += 1
                    errors.append(f"Duplicate: {t.reference}")
                else:
                    seen.add(t.reference)
                    to_insert.append(t)

            Transaction.objects.bulk_create(to_insert, batch_size=1000, ignore_conflicts=True)

            job.total_rows += len(chunk)
            job.imported_rows += len(to_insert)
            job.failed_rows += chunk_failed
            job.error_log = "\n".join(errors)
            job.save()

        job.status = "done"

    except Exception as e:
        job.status = "failed"
        errors.append(f"Task aborted: {type(e).__name__}: {e}")
        job.error_log = "\n".join(errors)
        raise

    finally:
        job.finished_at = timezone.now()
        job.save()
