from django.db import migrations

CHANGES = [
    ('Green Arena', 'ул. Спортивная, 10', 'г. Ош, ул. Курманжан Датка, 12'),
    ('City Field', 'пр. Мира, 5', 'г. Ош, ул. Масалиева, 40'),
    ('Mini Stadium', 'ул. Ленина, 22', 'г. Ош, ул. Ленина, 22'),
    ('Tennis Hall', 'ул. Токтогула, 8', 'г. Ош, ул. Монуева, 8'),
    ('Sport Hall', 'ул. Абая, 14', 'г. Ош, ул. Исанова, 14'),
    ('Hoop Center', 'пр. Чуй, 120', 'г. Ош, ул. Навои, 120'),
]


def to_osh(apps, schema_editor):
    Venue = apps.get_model('core', 'Venue')
    for name, old, new in CHANGES:
        Venue.objects.filter(name=name, address=old).update(address=new)


def back(apps, schema_editor):
    Venue = apps.get_model('core', 'Venue')
    for name, old, new in CHANGES:
        Venue.objects.filter(name=name, address=new).update(address=old)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(to_osh, back),
    ]
