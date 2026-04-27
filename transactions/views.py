import os
import tempfile

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import ImportJob, Transaction
from .tasks import import_transactions

UPLOAD_DIR = "/tmp/imports"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@method_decorator(csrf_exempt, name="dispatch")
class ImportView(View):
    """
    Accepts a CSV upload, saves the file, and queues an async import task.
    """

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return JsonResponse({"error": "No file provided."}, status=400)

        # Save uploaded file to a temp location so the worker can read it
        suffix = os.path.splitext(file.name)[1]
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=UPLOAD_DIR)
        for chunk in file.chunks():
            tmp.write(chunk)
        tmp.close()

        job = ImportJob.objects.create(filename=file.name, status="pending")

        import_transactions.delay(job.id, tmp.name)

        return JsonResponse(
            {
                "job_id": job.id,
                "imported": job.imported_rows,
                "failed": job.failed_rows,
            },
            status=202,
        )


class SummaryView(View):
    """
    Returns total amount per category, with optional date range filter.
    """

    def get(self, request):
        date_from = request.GET.get("from")
        date_to = request.GET.get("to")

        transactions = Transaction.objects.all()

        if date_from:
            transactions = transactions.filter(transacted_at__gte=date_from)
        if date_to:
            transactions = transactions.filter(transacted_at__lte=date_to)

        # Aggregate in Python
        summary = {}
        for t in transactions:
            cat = t.category
            if cat not in summary:
                summary[cat] = 0
            summary[cat] += float(t.amount)

        result = [{"category": k, "total": round(v, 2)} for k, v in summary.items()]
        result.sort(key=lambda x: x["total"], reverse=True)

        return JsonResponse({"results": result})


class JobStatusView(View):
    """
    Returns the current status of an import job.
    """

    def get(self, request, job_id):
        try:
            job = ImportJob.objects.get(id=job_id)
        except ImportJob.DoesNotExist:
            return JsonResponse({"error": "Job not found."}, status=404)

        return JsonResponse(
            {
                "id": job.id,
                "status": job.status,
                "filename": job.filename,
                "total_rows": job.total_rows,
                "imported_rows": job.imported_rows,
                "failed_rows": job.failed_rows,
                "started_at": job.started_at.isoformat(),
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            }
        )
