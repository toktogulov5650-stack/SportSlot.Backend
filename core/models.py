from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Profile(models.Model):

    ROLES = [
        ('user', 'Игрок'),
        ('owner', 'Владелец'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLES, default='user')

    def __str__(self):
        return f'{self.user.first_name} ({self.get_role_display()})'


class Venue(models.Model):

    SPORTS = [
        ('Футбол', 'Футбол'),
        ('Теннис', 'Теннис'),
        ('Волейбол', 'Волейбол'),
        ('Баскетбол', 'Баскетбол'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='venues')
    sport = models.CharField(max_length=20, choices=SPORTS)
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    price = models.PositiveIntegerField(help_text='Цена за час, сом')
    rating = models.FloatField(default=0)
    surface = models.CharField(max_length=30, default='Газон')
    capacity = models.CharField(max_length=20, default='5×5')
    open_hour = models.PositiveSmallIntegerField(default=10)
    close_hour = models.PositiveSmallIntegerField(default=22)
    is_active = models.BooleanField(default=True)

    def hours(self):
        return list(range(self.open_hour, self.close_hour))

    def __str__(self):
        return self.name


class VenuePhoto(models.Model):

    venue = models.OneToOneField(Venue, on_delete=models.CASCADE, related_name='photo')
    data = models.BinaryField()
    content_type = models.CharField(max_length=30)
    updated_at = models.DateTimeField(auto_now=True)


class BlockedSlot(models.Model):

    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='blocked_slots')
    date = models.DateField()
    hour = models.PositiveSmallIntegerField()

    class Meta:
        unique_together = ('venue', 'date', 'hour')


class Booking(models.Model):

    STATUSES = [
        ('active', 'Активна'),
        ('cancelled', 'Отменена'),
    ]

    code = models.CharField(max_length=10, unique=True)
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='bookings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    date = models.DateField()
    start_hour = models.PositiveSmallIntegerField()
    hours_count = models.PositiveSmallIntegerField(default=1)
    price = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUSES, default='active')
    cancelled_by = models.CharField(max_length=10, blank=True)
    reason = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def start(self):
        return timezone.make_aware(datetime.combine(self.date, time(self.start_hour)))

    @property
    def end(self):
        return self.start + timedelta(hours=self.hours_count)

    @property
    def is_upcoming(self):
        return self.status == 'active' and self.end > timezone.localtime()

    def __str__(self):
        return f'{self.code} {self.venue.name} {self.date}'


class BookedHour(models.Model):

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='slots')
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE)
    date = models.DateField()
    hour = models.PositiveSmallIntegerField()

    class Meta:
        unique_together = ('venue', 'date', 'hour')


class Notification(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=100)
    text = models.CharField(max_length=300)
    sport = models.CharField(max_length=20, default='Футбол')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Favorite(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'venue')
