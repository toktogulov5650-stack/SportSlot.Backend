import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100)),
                ('text', models.CharField(max_length=300)),
                ('sport', models.CharField(default='Футбол', max_length=20)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('user', 'Игрок'), ('owner', 'Владелец')], default='user', max_length=10)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Venue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sport', models.CharField(choices=[('Футбол', 'Футбол'), ('Теннис', 'Теннис'), ('Волейбол', 'Волейбол'), ('Баскетбол', 'Баскетбол')], max_length=20)),
                ('name', models.CharField(max_length=100)),
                ('address', models.CharField(max_length=200)),
                ('price', models.PositiveIntegerField(help_text='Цена за час, сом')),
                ('rating', models.FloatField(default=0)),
                ('surface', models.CharField(default='Газон', max_length=30)),
                ('capacity', models.CharField(default='5×5', max_length=20)),
                ('open_hour', models.PositiveSmallIntegerField(default=10)),
                ('close_hour', models.PositiveSmallIntegerField(default=22)),
                ('is_active', models.BooleanField(default=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='venues', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Booking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=10, unique=True)),
                ('date', models.DateField()),
                ('start_hour', models.PositiveSmallIntegerField()),
                ('hours_count', models.PositiveSmallIntegerField(default=1)),
                ('price', models.PositiveIntegerField()),
                ('status', models.CharField(choices=[('active', 'Активна'), ('cancelled', 'Отменена')], default='active', max_length=10)),
                ('cancelled_by', models.CharField(blank=True, max_length=10)),
                ('reason', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookings', to=settings.AUTH_USER_MODEL)),
                ('venue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookings', to='core.venue')),
            ],
        ),
        migrations.CreateModel(
            name='Favorite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorites', to=settings.AUTH_USER_MODEL)),
                ('venue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.venue')),
            ],
            options={
                'unique_together': {('user', 'venue')},
            },
        ),
        migrations.CreateModel(
            name='BookedHour',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('hour', models.PositiveSmallIntegerField()),
                ('booking', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='slots', to='core.booking')),
                ('venue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.venue')),
            ],
            options={
                'unique_together': {('venue', 'date', 'hour')},
            },
        ),
        migrations.CreateModel(
            name='BlockedSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('hour', models.PositiveSmallIntegerField()),
                ('venue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blocked_slots', to='core.venue')),
            ],
            options={
                'unique_together': {('venue', 'date', 'hour')},
            },
        ),
    ]
