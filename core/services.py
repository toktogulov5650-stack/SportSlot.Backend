import random
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import BlockedSlot, BookedHour, Booking, Notification, VenuePhoto

MAX_HOURS = 4
DAYS_AHEAD = 14
CANCEL_BEFORE_MINUTES = 60
MAX_PHOTO_BYTES = 5 * 1024 * 1024


class BookingError(Exception):
    pass


class PhotoError(Exception):
    pass


def detect_image_type(data):
    if data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    return None


def save_photo(venue, data):
    kind = detect_image_type(data)
    if kind is None:
        raise PhotoError('Загрузите фото в формате JPG, PNG или WebP')
    if len(data) > MAX_PHOTO_BYTES:
        raise PhotoError('Фото слишком большое, максимум 5 МБ')
    VenuePhoto.objects.update_or_create(
        venue=venue, defaults={'data': data, 'content_type': kind})


def now():
    return timezone.localtime()


def today():
    return timezone.localdate()


def is_past(day, hour):
    if day < today():
        return True
    return day == today() and hour <= now().hour


def notify(user, title, text, sport='Футбол'):
    Notification.objects.create(user=user, title=title, text=text, sport=sport)


def day_slots(venue, day):
    booked = {s.hour: s for s in BookedHour.objects.filter(venue=venue, date=day)}
    blocked = set(
        BlockedSlot.objects.filter(venue=venue, date=day).values_list('hour', flat=True)
    )

    result = []
    for hour in venue.hours():
        if is_past(day, hour):
            state = 'past'
        elif hour in booked:
            state = 'booked'
        elif hour in blocked:
            state = 'blocked'
        else:
            state = 'free'

        item = {'hour': hour, 'state': state}
        if state == 'booked':
            item['booking_id'] = booked[hour].booking_id
        result.append(item)
    return result


def next_free(venue):
    for i in range(7):
        day = today() + timedelta(days=i)
        for slot in day_slots(venue, day):
            if slot['state'] == 'free':
                return {'date': day.isoformat(), 'hour': slot['hour']}
    return None


def _new_code():
    while True:
        code = f'SS-{random.randint(1000, 9999)}'
        if not Booking.objects.filter(code=code).exists():
            return code


def create_booking(user, venue, day, hours):
    if not venue.is_active:
        raise BookingError('Площадка недоступна')
    if day < today() or day > today() + timedelta(days=DAYS_AHEAD - 1):
        raise BookingError('Выберите дату в ближайшие две недели')

    hours = sorted(set(hours))
    if not hours:
        raise BookingError('Выберите время')
    if len(hours) > MAX_HOURS:
        raise BookingError(f'Максимум {MAX_HOURS} часа подряд')
    if hours != list(range(hours[0], hours[-1] + 1)):
        raise BookingError('Часы должны идти подряд')
    if any(h not in venue.hours() for h in hours):
        raise BookingError('Площадка в это время закрыта')

    states = {s['hour']: s['state'] for s in day_slots(venue, day)}
    if any(states[h] != 'free' for h in hours):
        raise BookingError('Это время уже занято')

    if BookedHour.objects.filter(booking__user=user, date=day, hour__in=hours).exists():
        raise BookingError('У вас уже есть бронь на это время')

    try:
        with transaction.atomic():
            booking = Booking.objects.create(
                code=_new_code(),
                venue=venue,
                user=user,
                date=day,
                start_hour=hours[0],
                hours_count=len(hours),
                price=venue.price * len(hours),
            )
            for hour in hours:
                BookedHour.objects.create(booking=booking, venue=venue, date=day, hour=hour)
    except IntegrityError:
        raise BookingError('Это время только что заняли')

    when = f'{day:%d.%m}, {hours[0]:02d}:00'
    notify(user, 'Бронь подтверждена', f'{venue.name}, {when}', venue.sport)
    notify(venue.owner, 'Новая бронь', f'{user.first_name} · {venue.name}, {when}', venue.sport)
    return booking


def _cancel(booking, who, reason=''):
    booking.status = 'cancelled'
    booking.cancelled_by = who
    booking.reason = reason
    booking.save()
    booking.slots.all().delete()


def cancel_by_player(booking):
    if booking.status != 'active':
        raise BookingError('Бронь уже отменена')
    if booking.start - now() < timedelta(minutes=CANCEL_BEFORE_MINUTES):
        raise BookingError('Отмена возможна не позже чем за 1 час')

    _cancel(booking, 'user')
    when = f'{booking.date:%d.%m}, {booking.start_hour:02d}:00'
    venue = booking.venue
    notify(booking.user, 'Бронь отменена', f'{venue.name}, {when}', venue.sport)
    notify(venue.owner, 'Бронь отменена клиентом',
           f'{booking.user.first_name} · {venue.name}, {when}', venue.sport)


def cancel_by_owner(booking, reason):
    if not booking.is_upcoming:
        raise BookingError('Эту бронь уже нельзя отменить')

    reason = reason or 'Другое'
    _cancel(booking, 'owner', reason)
    when = f'{booking.date:%d.%m}, {booking.start_hour:02d}:00'
    venue = booking.venue
    notify(booking.user, 'Бронь отменена владельцем',
           f'{venue.name}, {when}. Причина: {reason}', venue.sport)
