import base64
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from . import services
from .models import BookedHour, Booking, Profile, Venue


def make_user(email, role, name='Тест'):
    user = User.objects.create_user(username=email, email=email, password='123456', first_name=name)
    Profile.objects.create(user=user, role=role)
    return user


def client_for(user):
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return client


class BaseTest(TestCase):

    def setUp(self):
        self.player = make_user('player@gmail.com', 'user', 'Игрок')
        self.player2 = make_user('player2@gmail.com', 'user', 'Второй игрок')
        self.owner = make_user('owner@gmail.com', 'owner', 'Владелец')
        self.owner2 = make_user('owner2@gmail.com', 'owner', 'Другой владелец')

        self.venue = self.make_venue(self.owner, 'Тестовая арена')

        self.pc = client_for(self.player)
        self.pc2 = client_for(self.player2)
        self.oc = client_for(self.owner)
        self.oc2 = client_for(self.owner2)
        self.day = services.today() + timedelta(days=1)

    def make_venue(self, owner, name):
        return Venue.objects.create(owner=owner, sport='Футбол', name=name, address='ул. Тестовая, 1',
                                    price=1000, open_hour=0, close_hour=24)

    def book(self, client, hours, venue=None):
        venue = venue or self.venue
        return client.post('/api/bookings/', {'venue': venue.id, 'date': self.day.isoformat(),
                                              'hours': hours}, format='json')


class AuthTests(BaseTest):
    def test_register_login_and_me(self):
        client = APIClient()
        r = client.post('/api/auth/register/', {'name': 'Аня', 'email': 'Anya@Gmail.com',
                                                'password': '123456', 'role': 'owner'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['user']['email'], 'anya@gmail.com')
        self.assertEqual(r.data['user']['role'], 'owner')

        r = client.post('/api/auth/login/', {'email': 'anya@gmail.com', 'password': '123456'}, format='json')
        self.assertEqual(r.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")
        self.assertEqual(client.get('/api/auth/me/').data['name'], 'Аня')

    def test_duplicate_email_is_rejected(self):
        r = APIClient().post('/api/auth/register/', {'name': 'Аня', 'email': 'player@gmail.com',
                                                      'password': '123456', 'role': 'user'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('error', r.data)

    def test_short_password_is_rejected(self):
        r = APIClient().post('/api/auth/register/', {'name': 'Аня', 'email': 'a@gmail.com',
                                                      'password': '123', 'role': 'user'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_wrong_password(self):
        r = APIClient().post('/api/auth/login/', {'email': 'player@gmail.com', 'password': 'nope'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_api_needs_token(self):
        self.assertEqual(APIClient().get('/api/venues/').status_code, 401)


class BookingTests(BaseTest):
    def test_book_and_slot_becomes_busy(self):
        r = self.book(self.pc, [10, 11])
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['price'], 2000)
        self.assertTrue(r.data['code'].startswith('SS-'))

        r = self.pc2.get(f'/api/venues/{self.venue.id}/slots/?date={self.day.isoformat()}')
        states = {s['hour']: s['state'] for s in r.data['slots']}
        self.assertEqual(states[10], 'booked')
        self.assertEqual(states[12], 'free')

    def test_double_booking_is_forbidden(self):
        self.assertEqual(self.book(self.pc, [18]).status_code, 201)
        r = self.book(self.pc2, [18])
        self.assertEqual(r.status_code, 400)
        self.assertIn('занято', r.data['error'])

    def test_database_itself_blocks_duplicate_hour(self):
        self.book(self.pc, [18])
        booking = Booking.objects.get()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BookedHour.objects.create(booking=booking, venue=self.venue, date=self.day, hour=18)

    def test_hours_must_be_in_a_row(self):
        self.assertEqual(self.book(self.pc, [10, 12]).status_code, 400)

    def test_max_four_hours(self):
        self.assertEqual(self.book(self.pc, [10, 11, 12, 13, 14]).status_code, 400)
        self.assertEqual(self.book(self.pc, [10, 11, 12, 13]).status_code, 201)

    def test_owner_cannot_book(self):
        self.assertEqual(self.book(self.oc, [10]).status_code, 403)

    def test_player_cannot_be_in_two_places(self):
        other = self.make_venue(self.owner2, 'Другая арена')
        self.assertEqual(self.book(self.pc, [10]).status_code, 201)
        self.assertEqual(self.book(self.pc, [10], venue=other).status_code, 400)

    def test_past_date_is_rejected(self):
        yesterday = (services.today() - timedelta(days=1)).isoformat()
        r = self.pc.post('/api/bookings/', {'venue': self.venue.id, 'date': yesterday, 'hours': [10]},
                         format='json')
        self.assertEqual(r.status_code, 400)

    def test_players_see_only_their_bookings(self):
        self.book(self.pc, [10])
        self.book(self.pc2, [12])
        self.assertEqual(len(self.pc.get('/api/bookings/').data), 1)

    def test_booking_creates_notifications(self):
        self.book(self.pc, [10])
        self.assertEqual(self.pc.get('/api/notifications/').data[0]['title'], 'Бронь подтверждена')
        self.assertEqual(self.oc.get('/api/notifications/').data[0]['title'], 'Новая бронь')


class CancelTests(BaseTest):
    def test_player_cancel_frees_the_slot(self):
        booking_id = self.book(self.pc, [10]).data['id']
        r = self.pc.post(f'/api/bookings/{booking_id}/cancel/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'cancelled')
        self.assertEqual(self.book(self.pc2, [10]).status_code, 201)

    def test_player_cannot_cancel_less_than_hour_before(self):
        booking_id = self.book(self.pc, [10]).data['id']
        booking = Booking.objects.get(id=booking_id)
        half_hour_before = booking.start - timedelta(minutes=30)
        with patch('core.services.now', return_value=half_hour_before):
            r = self.pc.post(f'/api/bookings/{booking_id}/cancel/')
        self.assertEqual(r.status_code, 400)

    def test_stranger_cannot_cancel(self):
        booking_id = self.book(self.pc, [10]).data['id']
        self.assertEqual(self.pc2.post(f'/api/bookings/{booking_id}/cancel/').status_code, 404)
        self.assertEqual(self.oc2.post(f'/api/bookings/{booking_id}/cancel/').status_code, 404)

    def test_owner_cancel_with_reason_notifies_player(self):
        booking_id = self.book(self.pc, [10]).data['id']
        r = self.oc.post(f'/api/bookings/{booking_id}/cancel/', {'reason': 'Ремонт площадки'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['cancelled_by'], 'owner')
        note = self.pc.get('/api/notifications/').data[0]
        self.assertIn('Ремонт площадки', note['text'])


class OwnerTests(BaseTest):
    def test_player_cannot_use_owner_endpoints(self):
        self.assertEqual(self.pc.get('/api/owner/venues/').status_code, 403)
        self.assertEqual(self.pc.post('/api/owner/venues/', {}, format='json').status_code, 403)

    def test_owner_creates_and_edits_venue(self):
        data = {'sport': 'Теннис', 'name': 'Новый корт', 'address': 'ул. Новая, 5', 'price': 800,
                'surface': 'Хард', 'capacity': '2–4', 'open_hour': 9, 'close_hour': 21}
        r = self.oc.post('/api/owner/venues/', data, format='json')
        self.assertEqual(r.status_code, 201)
        venue_id = r.data['id']
        self.assertEqual(Venue.objects.get(id=venue_id).owner, self.owner)

        r = self.oc.patch(f'/api/owner/venues/{venue_id}/', {'price': 900}, format='json')
        self.assertEqual(r.data['price'], 900)

        r = self.oc.patch(f'/api/owner/venues/{venue_id}/', {'close_hour': 8}, format='json')
        self.assertEqual(r.status_code, 400)

        self.assertEqual(self.oc2.patch(f'/api/owner/venues/{venue_id}/', {'price': 1}, format='json').status_code, 404)

    def test_hidden_venue_is_not_in_catalog(self):
        self.oc.patch(f'/api/owner/venues/{self.venue.id}/', {'is_active': False}, format='json')
        self.assertEqual(len(self.pc.get('/api/venues/').data), 0)
        self.assertEqual(len(self.oc.get('/api/owner/venues/').data), 1)

    def test_block_slot_prevents_booking(self):
        url = f'/api/owner/venues/{self.venue.id}/block/'
        body = {'date': self.day.isoformat(), 'hour': 15}
        self.assertTrue(self.oc.post(url, body, format='json').data['blocked'])
        self.assertEqual(self.book(self.pc, [15]).status_code, 400)
        self.assertFalse(self.oc.post(url, body, format='json').data['blocked'])
        self.assertEqual(self.book(self.pc, [15]).status_code, 201)

    def test_cannot_block_booked_hour(self):
        self.book(self.pc, [15])
        r = self.oc.post(f'/api/owner/venues/{self.venue.id}/block/',
                         {'date': self.day.isoformat(), 'hour': 15}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_owner_sees_client_name_but_player_does_not(self):
        self.book(self.pc, [15])
        url = f'/api/venues/{self.venue.id}/slots/?date={self.day.isoformat()}'
        owner_slot = [s for s in self.oc.get(url).data['slots'] if s['hour'] == 15][0]
        player_slot = [s for s in self.pc2.get(url).data['slots'] if s['hour'] == 15][0]
        self.assertEqual(owner_slot['user_name'], 'Игрок')
        self.assertNotIn('user_name', player_slot)

    def test_cannot_delete_venue_with_future_booking(self):
        self.book(self.pc, [10])
        self.assertEqual(self.oc.delete(f'/api/owner/venues/{self.venue.id}/').status_code, 400)
        Booking.objects.all().delete()
        self.assertEqual(self.oc.delete(f'/api/owner/venues/{self.venue.id}/').status_code, 204)

    def test_owner_sees_only_bookings_of_own_venues(self):
        other = self.make_venue(self.owner2, 'Чужая арена')
        self.book(self.pc, [10])
        self.book(self.pc, [12], venue=other)
        mine = self.oc.get('/api/bookings/').data
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]['venue_name'], 'Тестовая арена')


PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')


def b64(data):
    return base64.b64encode(data).decode()


class PhotoTests(BaseTest):
    def url(self):
        return f'/api/owner/venues/{self.venue.id}/photo/'

    def test_owner_uploads_photo_and_everyone_sees_it(self):
        r = self.oc.post(self.url(), {'image': b64(PNG)}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.data['photo_url'])

        anonymous = APIClient().get(f'/api/venues/{self.venue.id}/photo/')
        self.assertEqual(anonymous.status_code, 200)
        self.assertEqual(anonymous['Content-Type'], 'image/png')
        self.assertEqual(anonymous.content, PNG)

        listed = self.pc.get('/api/venues/').data[0]
        self.assertTrue(listed['photo_url'].startswith(f'/api/venues/{self.venue.id}/photo/'))

    def test_venue_without_photo_has_no_url(self):
        self.assertIsNone(self.pc.get('/api/venues/').data[0]['photo_url'])
        self.assertEqual(APIClient().get(f'/api/venues/{self.venue.id}/photo/').status_code, 404)

    def test_not_an_image_is_rejected(self):
        r = self.oc.post(self.url(), {'image': b64(b'this is not a picture')}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.oc.post(self.url(), {'image': '%%%'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_too_big_photo_is_rejected(self):
        big = PNG + b'0' * (services.MAX_PHOTO_BYTES + 1)
        r = self.oc.post(self.url(), {'image': b64(big)}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('большое', r.data['error'])

    def test_photo_up_to_five_megabytes_is_accepted(self):
        big = PNG + b'0' * (4 * 1024 * 1024 + 500 * 1024)
        r = self.oc.post(self.url(), {'image': b64(big)}, format='json')
        self.assertEqual(r.status_code, 200)
        saved = APIClient().get(f'/api/venues/{self.venue.id}/photo/')
        self.assertEqual(len(saved.content), len(big))

    def test_only_the_owner_can_upload(self):
        self.assertEqual(self.pc.post(self.url(), {'image': b64(PNG)}, format='json').status_code, 403)
        self.assertEqual(self.oc2.post(self.url(), {'image': b64(PNG)}, format='json').status_code, 404)

    def test_owner_can_replace_and_delete_photo(self):
        self.oc.post(self.url(), {'image': b64(PNG)}, format='json')
        self.oc.post(self.url(), {'image': b64(PNG)}, format='json')
        r = self.oc.delete(self.url())
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['photo_url'])
        self.assertEqual(APIClient().get(f'/api/venues/{self.venue.id}/photo/').status_code, 404)


class MiscTests(BaseTest):
    def test_favorite_toggle(self):
        url = f'/api/venues/{self.venue.id}/favorite/'
        self.assertTrue(self.pc.post(url).data['is_favorite'])
        self.assertTrue(self.pc.get('/api/venues/').data[0]['is_favorite'])
        self.assertFalse(self.pc.post(url).data['is_favorite'])

    def test_notifications_read(self):
        self.book(self.pc, [10])
        self.assertFalse(self.pc.get('/api/notifications/').data[0]['is_read'])
        self.pc.post('/api/notifications/read/')
        self.assertTrue(self.pc.get('/api/notifications/').data[0]['is_read'])

    def test_venues_list_has_next_free(self):
        item = self.pc.get('/api/venues/').data[0]
        self.assertIsNotNone(item['next_free'])
