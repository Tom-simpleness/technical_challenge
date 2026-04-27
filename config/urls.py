from django.urls import path
from transactions.views import ImportView, JobStatusView, SummaryView

urlpatterns = [
    path("api/import/", ImportView.as_view()),
    path("api/import/<int:job_id>/", JobStatusView.as_view()),
    path("api/summary/", SummaryView.as_view()),
]
