from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Booking, Favorite, Notification, Profile, Venue, VenuePhoto
from .services import next_free


def role_of(user):
    profile = Profile.objects.filter(user=user).first()
    return profile.role if profile else 'user'


def user_data(user):
    return {
        'id': user.id,
        'name': user.first_name,
        'email': user.email,
        'role': role_of(user),
    }


class RegisterSerializer(serializers.Serializer):

    name = serializers.CharField(min_length=2, max_length=50)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6, max_length=50)
    role = serializers.ChoiceField(choices=['user', 'owner'])

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Этот email уже зарегистрирован')
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class VenueSerializer(serializers.ModelSerializer):

    is_favorite = serializers.SerializerMethodField()
    next_free = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Venue
        fields = [
            'id', 'sport', 'name', 'address', 'price', 'rating', 'surface',
            'capacity', 'open_hour', 'close_hour', 'is_active',
            'is_favorite', 'next_free', 'photo_url',
        ]
        read_only_fields = ['id', 'rating']

    def get_photo_url(self, venue):
        updated = VenuePhoto.objects.filter(venue=venue).values_list('updated_at', flat=True).first()
        if updated is None:
            return None
        return f'/api/venues/{venue.id}/photo/?v={int(updated.timestamp())}'

    def get_is_favorite(self, venue):
        user = self.context['request'].user
        return Favorite.objects.filter(user=user, venue=venue).exists()

    def get_next_free(self, venue):
        return next_free(venue)

    def validate(self, data):
        open_hour = data.get('open_hour', getattr(self.instance, 'open_hour', 10))
        close_hour = data.get('close_hour', getattr(self.instance, 'close_hour', 22))
        if close_hour > 24:
            raise serializers.ValidationError('Закрытие не может быть позже 24:00')
        if close_hour <= open_hour:
            raise serializers.ValidationError('Закрытие должно быть позже открытия')
        return data

    def validate_price(self, value):
        if value < 100:
            raise serializers.ValidationError('Цена за час — от 100 сом')
        return value


class BookingSerializer(serializers.ModelSerializer):

    venue_id = serializers.IntegerField(source='venue.id', read_only=True)
    venue_name = serializers.CharField(source='venue.name', read_only=True)
    sport = serializers.CharField(source='venue.sport', read_only=True)
    user_name = serializers.CharField(source='user.first_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    is_upcoming = serializers.BooleanField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'code', 'venue_id', 'venue_name', 'sport', 'date',
            'start_hour', 'hours_count', 'price', 'status', 'cancelled_by',
            'reason', 'is_upcoming', 'user_name', 'user_email', 'created_at',
        ]


class BookingCreateSerializer(serializers.Serializer):

    venue = serializers.IntegerField()
    date = serializers.DateField()
    hours = serializers.ListField(child=serializers.IntegerField(min_value=0, max_value=23))


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'text', 'sport', 'is_read', 'created_at']
