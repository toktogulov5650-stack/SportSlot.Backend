import base64
import binascii

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import services
from .models import BlockedSlot, Booking, Favorite, Notification, Profile, Venue, VenuePhoto
from .serializers import (
    BookingCreateSerializer, BookingSerializer, LoginSerializer,
    NotificationSerializer, RegisterSerializer, VenueSerializer,
    role_of, user_data,
)


def error(message, status=400):
    return Response({'error': message}, status=status)


def first_error(errors):
    for value in errors.values():
        if isinstance(value, (list, tuple)) and value:
            return str(value[0])
        return str(value)
    return 'Неверные данные'


def wrong_role():
    return error('Это действие недоступно для вашей роли', 403)


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return error(first_error(serializer.errors))
    data = serializer.validated_data

    user = User.objects.create_user(
        username=data['email'],
        email=data['email'],
        password=data['password'],
        first_name=data['name'],
    )
    Profile.objects.create(user=user, role=data['role'])

    text = ('Добавьте площадки и управляйте расписанием' if data['role'] == 'owner'
            else 'Выберите площадку и забронируйте время')
    services.notify(user, 'Добро пожаловать', text)

    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': user_data(user)}, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return error('Введите email и пароль')
    email = serializer.validated_data['email'].strip().lower()

    user = authenticate(username=email, password=serializer.validated_data['password'])
    if user is None:
        return error('Неверный email или пароль')

    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': user_data(user)})


@api_view(['GET'])
def me(request):
    return Response(user_data(request.user))


@api_view(['GET'])
def venues_list(request):
    venues = Venue.objects.filter(is_active=True).order_by('id')
    sport = request.query_params.get('sport')
    if sport:
        venues = venues.filter(sport=sport)
    return Response(VenueSerializer(venues, many=True, context={'request': request}).data)


@api_view(['GET'])
def venue_slots(request, venue_id):
    venue = get_object_or_404(Venue, id=venue_id)
    is_owner = venue.owner_id == request.user.id
    if not venue.is_active and not is_owner:
        return error('Площадка недоступна', 404)

    day = parse_date(request.query_params.get('date', '')) or services.today()
    slots = services.day_slots(venue, day)

    if is_owner:
        bookings = Booking.objects.filter(id__in=[s['booking_id'] for s in slots if 'booking_id' in s])
        names = {b.id: b.user.first_name for b in bookings.select_related('user')}
        for slot in slots:
            if 'booking_id' in slot:
                slot['user_name'] = names.get(slot['booking_id'], '')
    else:
        for slot in slots:
            slot.pop('booking_id', None)

    return Response({'venue_id': venue.id, 'date': day.isoformat(), 'slots': slots})


@api_view(['GET'])
@permission_classes([AllowAny])
def venue_photo(request, venue_id):
    photo = get_object_or_404(VenuePhoto, venue_id=venue_id)
    response = HttpResponse(bytes(photo.data), content_type=photo.content_type)
    response['Cache-Control'] = 'public, max-age=86400'
    return response


@api_view(['POST'])
def favorite_toggle(request, venue_id):
    venue = get_object_or_404(Venue, id=venue_id)
    favorite, created = Favorite.objects.get_or_create(user=request.user, venue=venue)
    if not created:
        favorite.delete()
    return Response({'is_favorite': created})


@api_view(['GET', 'POST'])
def booking_list_create(request):
    role = role_of(request.user)

    if request.method == 'GET':
        if role == 'owner':
            bookings = Booking.objects.filter(venue__owner=request.user)
        else:
            bookings = Booking.objects.filter(user=request.user)
        bookings = bookings.select_related('venue', 'user').order_by('-date', '-start_hour')
        return Response(BookingSerializer(bookings, many=True).data)

    if role != 'user':
        return wrong_role()
    serializer = BookingCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return error(first_error(serializer.errors))
    data = serializer.validated_data

    venue = get_object_or_404(Venue, id=data['venue'])
    try:
        booking = services.create_booking(request.user, venue, data['date'], data['hours'])
    except services.BookingError as e:
        return error(str(e))
    return Response(BookingSerializer(booking).data, status=201)


@api_view(['POST'])
def booking_cancel(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    try:
        if booking.user_id == request.user.id:
            services.cancel_by_player(booking)
        elif booking.venue.owner_id == request.user.id:
            services.cancel_by_owner(booking, request.data.get('reason', ''))
        else:
            return error('Бронь не найдена', 404)
    except services.BookingError as e:
        return error(str(e))
    return Response(BookingSerializer(booking).data)


@api_view(['GET'])
def notifications(request):
    items = Notification.objects.filter(user=request.user)[:50]
    return Response(NotificationSerializer(items, many=True).data)


@api_view(['POST'])
def notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return Response({'ok': True})


@api_view(['GET', 'POST'])
def owner_venues(request):
    if role_of(request.user) != 'owner':
        return wrong_role()

    if request.method == 'GET':
        venues = Venue.objects.filter(owner=request.user).order_by('id')
        return Response(VenueSerializer(venues, many=True, context={'request': request}).data)

    serializer = VenueSerializer(data=request.data, context={'request': request})
    if not serializer.is_valid():
        return error(first_error(serializer.errors))
    venue = serializer.save(owner=request.user)
    return Response(VenueSerializer(venue, context={'request': request}).data, status=201)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def owner_venue_detail(request, venue_id):
    if role_of(request.user) != 'owner':
        return wrong_role()
    venue = get_object_or_404(Venue, id=venue_id, owner=request.user)

    if request.method == 'DELETE':
        has_future = any(b.is_upcoming for b in venue.bookings.filter(status='active'))
        if has_future:
            return error('Сначала отмените будущие брони')
        venue.delete()
        return Response(status=204)

    if request.method in ('PUT', 'PATCH'):
        serializer = VenueSerializer(venue, data=request.data, partial=True,
                                     context={'request': request})
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        venue = serializer.save()

    return Response(VenueSerializer(venue, context={'request': request}).data)


@api_view(['POST', 'DELETE'])
def owner_venue_photo(request, venue_id):
    if role_of(request.user) != 'owner':
        return wrong_role()
    venue = get_object_or_404(Venue, id=venue_id, owner=request.user)

    if request.method == 'DELETE':
        VenuePhoto.objects.filter(venue=venue).delete()
    else:
        try:
            data = base64.b64decode(request.data.get('image', ''), validate=True)
        except (binascii.Error, ValueError, TypeError):
            return error('Не удалось прочитать фото')
        try:
            services.save_photo(venue, data)
        except services.PhotoError as e:
            return error(str(e))
    return Response(VenueSerializer(venue, context={'request': request}).data)


@api_view(['POST'])
def owner_block_slot(request, venue_id):
    if role_of(request.user) != 'owner':
        return wrong_role()
    venue = get_object_or_404(Venue, id=venue_id, owner=request.user)

    day = parse_date(str(request.data.get('date', '')))
    try:
        hour = int(request.data.get('hour'))
    except (TypeError, ValueError):
        return error('Укажите час')
    if day is None or hour not in venue.hours():
        return error('Неверная дата или час')

    blocked = BlockedSlot.objects.filter(venue=venue, date=day, hour=hour).first()
    if blocked:
        blocked.delete()
        return Response({'blocked': False})

    state = {s['hour']: s['state'] for s in services.day_slots(venue, day)}[hour]
    if state != 'free':
        return error('Этот час нельзя закрыть')
    BlockedSlot.objects.create(venue=venue, date=day, hour=hour)
    return Response({'blocked': True})
