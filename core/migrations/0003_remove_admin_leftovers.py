from django.db import migrations

SQL = [
    'DROP TABLE IF EXISTS django_admin_log',
    'DROP TABLE IF EXISTS django_session',
    "DELETE FROM django_migrations WHERE app IN ('admin', 'sessions')",
]


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_osh_addresses'),
    ]

    operations = [
        migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop),
    ]
