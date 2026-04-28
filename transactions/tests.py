from datetime import datetime
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import ImportJob, Transaction


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class ImportFlowTest(TestCase):
    def test_import_inserts_unique_rows_and_counts_all_failure_kinds(self):
        csv_bytes = (
            b"reference,amount,currency,category,merchant,status,transacted_at\n"
            b"ref-1,10.00,EUR,food,Carrefour,completed,2024-01-15T10:00:00\n"          # valid, inserted
            b"ref-2,20.00,USD,travel,SNCF,completed,2024-02-20T11:30:00\n"             # valid, inserted
            b"ref-1,30.00,EUR,food,Carrefour,completed,2024-03-10T09:00:00\n"          # duplicate reference, rejected by intra-batch dedup
            b"ref-3,not-a-number,EUR,health,Doctolib,completed,2024-04-01T08:00:00\n"  # malformed amount, Decimal() raises InvalidOperation
            b"ref-4,,EUR,food,Carrefour,completed,2024-05-01T10:00:00\n"               # empty amount, rejected by isna() check
            b"ref-5,50.00,,food,Carrefour,completed,2024-06-01T10:00:00\n"             # empty currency, rejected by isna() check
            b"ref-6,60.00,EUR,food,Carrefour,completed,not-a-date\n"                   # malformed date, fromisoformat() raises ValueError
            b",70.00,EUR,food,Carrefour,completed,2024-08-01T10:00:00\n"               # empty reference, rejected by isna() check
        )
        upload = SimpleUploadedFile("test.csv", csv_bytes, content_type="text/csv")

        response = self.client.post("/api/import/", {"file": upload})

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertIn("job_id", body)

        # Only ref-1 (first occurrence) and ref-2 pass all checks
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertTrue(Transaction.objects.filter(reference="ref-1").exists())
        self.assertTrue(Transaction.objects.filter(reference="ref-2").exists())

        job = ImportJob.objects.get(id=body["job_id"])
        self.assertEqual(job.status, "done")
        self.assertEqual(job.total_rows, 8)
        self.assertEqual(job.imported_rows, 2)
        self.assertEqual(job.failed_rows, 6)
        self.assertIn("Duplicate: ref-1", job.error_log)
        self.assertIn("Error on row", job.error_log)
        self.assertIn("empty fields", job.error_log)


class SummaryEndpointTest(TestCase):
    def setUp(self):
        Transaction.objects.bulk_create([
            Transaction(reference="a", amount=Decimal("10.10"), currency="EUR",
                        category="food", merchant="m", status="completed",
                        transacted_at=timezone.make_aware(datetime(2024, 3, 1, 10, 0, 0))),
            Transaction(reference="b", amount=Decimal("20.25"), currency="EUR",
                        category="food", merchant="m", status="completed",
                        transacted_at=timezone.make_aware(datetime(2024, 3, 15, 10, 0, 0))),
            Transaction(reference="c", amount=Decimal("5.55"), currency="EUR",
                        category="food", merchant="m", status="completed",
                        transacted_at=timezone.make_aware(datetime(2024, 3, 20, 10, 0, 0))),
            Transaction(reference="d", amount=Decimal("100.00"), currency="EUR",
                        category="travel", merchant="m", status="completed",
                        transacted_at=timezone.make_aware(datetime(2024, 3, 5, 10, 0, 0))),
            Transaction(reference="e", amount=Decimal("200.50"), currency="EUR",
                        category="travel", merchant="m", status="completed",
                        transacted_at=timezone.make_aware(datetime(2024, 3, 10, 10, 0, 0))),
            Transaction(reference="f", amount=Decimal("999.99"), currency="EUR",
                        category="food", merchant="m", status="completed",
                        transacted_at=timezone.make_aware(datetime(2024, 1, 1, 10, 0, 0))),
        ])

    def test_summary_aggregates_by_category_within_date_range(self):
        response = self.client.get("/api/summary/?from=2024-03-01&to=2024-04-01")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["results"], [
            {"category": "travel", "total": 300.50},
            {"category": "food",   "total": 35.90},
        ])
