import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core import services
from core.models import BookedHour, Booking, Favorite, Notification, Profile, Venue

PASSWORD = '123456'


def make_user(name, email, role):
    user = User.objects.create_user(username=email, email=email, password=PASSWORD, first_name=name)
    Profile.objects.create(user=user, role=role)
    return user


class Command(BaseCommand):
    help = 'Заполняет базу тестовыми данными'

    def handle(self, *args, **options):
        if User.objects.filter(username='aibek@gmail.com').exists():
            self.stdout.write('Тестовые данные уже есть. Чтобы создать заново, удалите db.sqlite3 '
                              'и выполните: python manage.py migrate')
            return

        aibek = make_user('Айбек', 'aibek@gmail.com', 'user')
        ruslan = make_user('Руслан', 'ruslan@gmail.com', 'owner')
        mira = make_user('Мира', 'mira@gmail.com', 'owner')
        clients = [
            make_user('Нурлан', 'nurlan@gmail.com', 'user'),
            make_user('Айгуль', 'aigul@gmail.com', 'user'),
            make_user('Эмиль', 'emil@gmail.com', 'user'),
            make_user('Салтанат', 'saltanat@gmail.com', 'user'),
        ]

        def venue(owner, sport, name, address, price, rating, surface, capacity):
            return Venue.objects.create(owner=owner, sport=sport, name=name, address=address,
                                        price=price, rating=rating, surface=surface,
                                        capacity=capacity)

        green = venue(ruslan, 'Футбол', 'Green Arena', 'г. Ош, ул. Курманжан Датка, 12', 1200, 4.9, 'Газон', '10×10')
        venue(ruslan, 'Футбол', 'City Field', 'г. Ош, ул. Масалиева, 40', 1000, 4.6, 'Искусств.', '7×7')
        venue(ruslan, 'Футбол', 'Mini Stadium', 'г. Ош, ул. Ленина, 22', 1500, 4.8, 'Газон', '11×11')
        tennis = venue(mira, 'Теннис', 'Tennis Hall', 'г. Ош, ул. Монуева, 8', 900, 4.7, 'Хард', '2–4')
        venue(mira, 'Волейбол', 'Sport Hall', 'г. Ош, ул. Исанова, 14', 1500, 4.5, 'Паркет', '6×6')
        venue(mira, 'Баскетбол', 'Hoop Center', 'г. Ош, ул. Навои, 120', 1100, 4.8, 'Паркет', '5×5')

        rng = random.Random(1)
        number = 2000
        for v in Venue.objects.all():
            for i in range(7):
                day = services.today() + timedelta(days=i)
                for hour in v.hours():
                    if services.is_past(day, hour):
                        continue
                    chance = 0.30 if hour >= 18 else 0.12
                    if rng.random() < chance:
                        number += 1
                        booking = Booking.objects.create(
                            code=f'SS-{number}', venue=v, user=rng.choice(clients),
                            date=day, start_hour=hour, hours_count=1, price=v.price)
                        BookedHour.objects.create(booking=booking, venue=v, date=day, hour=hour)

        old = services.today() - timedelta(days=3)
        done = Booking.objects.create(code='SS-1041', venue=tennis, user=aibek, date=old,
                                      start_hour=20, hours_count=1, price=900)
        BookedHour.objects.create(booking=done, venue=tennis, date=old, hour=20)
        Booking.objects.create(code='SS-1187', venue=green, user=aibek,
                               date=services.today() - timedelta(days=9), start_hour=18,
                               hours_count=2, price=2400, status='cancelled', cancelled_by='user')

        Favorite.objects.create(user=aibek, venue=tennis)
        Notification.objects.create(user=aibek, title='Добро пожаловать',
                                    text='Выберите площадку и забронируйте время')
        Notification.objects.create(user=ruslan, title='Добро пожаловать',
                                    text='Добавьте площадки и управляйте расписанием')

        self.stdout.write(self.style.SUCCESS('Готово! Тестовые аккаунты (пароль 123456):'))
        self.stdout.write('  игрок:    aibek@gmail.com')
        self.stdout.write('  владелец: ruslan@gmail.com  (площадки Green Arena, City Field, Mini Stadium)')
        self.stdout.write('  владелец: mira@gmail.com    (площадки Tennis Hall, Sport Hall, Hoop Center)')
