from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ImportJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                ("filename", models.CharField(max_length=256)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("total_rows", models.IntegerField(default=0)),
                ("imported_rows", models.IntegerField(default=0)),
                ("failed_rows", models.IntegerField(default=0)),
                ("status", models.CharField(default="pending", max_length=16)),
                ("error_log", models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="Transaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                ("reference", models.CharField(max_length=64)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(max_length=3)),
                ("category", models.CharField(max_length=64)),
                ("merchant", models.CharField(max_length=128)),
                ("status", models.CharField(max_length=16)),
                ("transacted_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
