from django.urls import path, include
from django.contrib import admin

from rest_framework import routers

from resources import views, schemas
from swapi import views as swapi_views

router = routers.DefaultRouter()
router.register(r"people", views.PeopleViewSet)
router.register(r"planets", views.PlanetViewSet)
router.register(r"films", views.FilmViewSet)
router.register(r"species", views.SpeciesViewSet)
router.register(r"vehicles", views.VehicleViewSet)
router.register(r"starships", views.StarshipViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", swapi_views.index),
    path("documentation", swapi_views.documentation),
    path("about", swapi_views.about),
    path("stats", swapi_views.stats),
    path("stripe/donation", swapi_views.stripe_donation),
    path("api/people/schema", schemas.people),
    path("api/planets/schema", schemas.planets),
    path("api/films/schema", schemas.films),
    path("api/species/schema", schemas.species),
    path("api/vehicles/schema", schemas.vehicles),
    path("api/starships/schema", schemas.starships),
    path("api/", include(router.urls)),
]
