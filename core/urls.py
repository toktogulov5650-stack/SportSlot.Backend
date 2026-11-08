from django.urls import path

from . import views

urlpatterns = [
    path('auth/register/', views.register),
    path('auth/login/', views.login),
    path('auth/me/', views.me),

    path('venues/', views.venues_list),
    path('venues/<int:venue_id>/slots/', views.venue_slots),
    path('venues/<int:venue_id>/favorite/', views.favorite_toggle),
    path('venues/<int:venue_id>/photo/', views.venue_photo),

    path('bookings/', views.booking_list_create),
    path('bookings/<int:booking_id>/cancel/', views.booking_cancel),

    path('notifications/', views.notifications),
    path('notifications/read/', views.notifications_read),

    path('owner/venues/', views.owner_venues),
    path('owner/venues/<int:venue_id>/', views.owner_venue_detail),
    path('owner/venues/<int:venue_id>/block/', views.owner_block_slot),
    path('owner/venues/<int:venue_id>/photo/', views.owner_venue_photo),
]
