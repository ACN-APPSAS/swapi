"""
Star Wars API — resource test suite.

Run with: SECRET_KEY=test-secret python manage.py test
"""
from __future__ import unicode_literals

import json
from unittest.mock import MagicMock

from django.test import TestCase

from .models import People, Planet, Film, Species, Vehicle, Starship
from .renderers import WookieeRenderer
from .utils import get_resource_stats


FIXTURES = [
    'planets.json', 'people.json', 'species.json',
    'starships.json', 'vehicles.json', 'transport.json', 'films.json',
]


# ── Model Tests ───────────────────────────────────────────────────────────────

class PlanetModelTests(TestCase):
    def setUp(self):
        self.planet = Planet.objects.create(
            name='Tatooine', rotation_period='23', orbital_period='304',
            diameter='10465', climate='arid', gravity='1 standard',
            terrain='desert', surface_water='1', population='200000',
        )

    def test_str(self):
        self.assertEqual(str(self.planet), 'Tatooine')

    def test_fields_persisted(self):
        p = Planet.objects.get(pk=self.planet.pk)
        self.assertEqual(p.climate, 'arid')
        self.assertEqual(p.terrain, 'desert')
        self.assertEqual(p.population, '200000')

    def test_timestamps_auto_set(self):
        self.assertIsNotNone(self.planet.created)
        self.assertIsNotNone(self.planet.edited)


class PeopleModelTests(TestCase):
    def setUp(self):
        self.planet = Planet.objects.create(
            name='Tatooine', rotation_period='23', orbital_period='304',
            diameter='10465', climate='arid', gravity='1 standard',
            terrain='desert', surface_water='1', population='200000',
        )
        self.person = People.objects.create(
            name='Luke Skywalker', height='172', mass='77',
            hair_color='blond', skin_color='fair', eye_color='blue',
            birth_year='19BBY', gender='male', homeworld=self.planet,
        )

    def test_str(self):
        self.assertEqual(str(self.person), 'Luke Skywalker')

    def test_homeworld_foreign_key(self):
        self.assertEqual(self.person.homeworld.name, 'Tatooine')

    def test_optional_fields_blank_by_default(self):
        person = People.objects.create(name='Unnamed', homeworld=self.planet)
        self.assertEqual(person.height, '')
        self.assertEqual(person.mass, '')
        self.assertEqual(person.gender, '')

    def test_planet_residents_reverse_relation(self):
        self.assertIn(self.person, self.planet.residents.all())


class FilmModelTests(TestCase):
    def setUp(self):
        self.film = Film.objects.create(
            title='A New Hope', episode_id=4,
            opening_crawl='It is a period of civil war...',
            director='George Lucas', producer='Gary Kurtz',
            release_date='1977-05-25',
        )

    def test_str(self):
        self.assertEqual(str(self.film), 'A New Hope')

    def test_episode_id_stored(self):
        self.assertEqual(Film.objects.get(pk=self.film.pk).episode_id, 4)


class SpeciesModelTests(TestCase):
    def setUp(self):
        self.planet = Planet.objects.create(
            name='Kashyyyk', rotation_period='26', orbital_period='381',
            diameter='12765', climate='tropical', gravity='1 standard',
            terrain='forests', surface_water='60', population='45000000',
        )
        self.species = Species.objects.create(
            name='Wookiee', classification='mammal', designation='sentient',
            average_height='210', skin_colors='gray', hair_colors='black, brown',
            eye_colors='blue, green', average_lifespan='400',
            homeworld=self.planet, language='Shyriiwook',
        )

    def test_str(self):
        self.assertEqual(str(self.species), 'Wookiee')

    def test_optional_homeworld_can_be_null(self):
        s = Species.objects.create(
            name='Unknown', classification='mammal', designation='sentient',
            average_height='150', skin_colors='brown', hair_colors='none',
            eye_colors='black', average_lifespan='unknown',
            homeworld=None, language='unknown',
        )
        self.assertIsNone(s.homeworld)


# ── WookieeRenderer Tests ─────────────────────────────────────────────────────

class WookieeRendererTests(TestCase):
    def setUp(self):
        self.renderer = WookieeRenderer()

    def test_known_translation(self):
        self.assertEqual(self.renderer.translate_to_wookie('swapi'), 'cohraakah')

    def test_empty_string(self):
        self.assertEqual(self.renderer.translate_to_wookie(''), '')

    def test_each_lowercase_letter_translated(self):
        for char, expected in self.renderer.lookup.items():
            self.assertEqual(self.renderer.translate_to_wookie(char), expected)

    def test_uppercase_passes_through(self):
        self.assertEqual(self.renderer.translate_to_wookie('ABC'), 'ABC')

    def test_digits_pass_through(self):
        self.assertEqual(self.renderer.translate_to_wookie('0123456789'), '0123456789')

    def test_json_structure_chars_pass_through(self):
        self.assertEqual(self.renderer.translate_to_wookie('{}[]":,'), '{}[]":,')

    def test_mixed_input(self):
        # n→wh, a→ra, m→sc, e→wo
        result = self.renderer.translate_to_wookie('name')
        self.assertEqual(result, 'whrascwo')

    def test_render_returns_bytes(self):
        rendered = self.renderer.render({'key': 'value'})
        self.assertIsInstance(rendered, bytes)

    def test_render_is_utf8_decodable(self):
        rendered = self.renderer.render({'test': 'data'})
        decoded = rendered.decode('utf-8')
        self.assertIsInstance(decoded, str)

    def test_render_output_is_parseable_json(self):
        rendered = self.renderer.render({'hello': 'world'})
        parsed = json.loads(rendered.decode('utf-8'))
        # Keys should be wookiee-translated
        wookiee_key = self.renderer.translate_to_wookie('hello')
        self.assertIn(wookiee_key, parsed)

    def test_render_roundtrip_value(self):
        rendered = self.renderer.render({'name': 'Luke'})
        parsed = json.loads(rendered.decode('utf-8'))
        name_key = self.renderer.translate_to_wookie('name')
        expected_value = self.renderer.translate_to_wookie('Luke')
        # Only lowercase is translated; 'L' is uppercase so passes through
        self.assertIn(name_key, parsed)
        self.assertEqual(parsed[name_key], expected_value)


# ── Utils Tests ───────────────────────────────────────────────────────────────

class UtilsTests(TestCase):
    fixtures = FIXTURES

    def test_returns_all_resource_keys(self):
        stats = get_resource_stats()
        for key in ('people', 'planets', 'films', 'species', 'vehicles', 'starships'):
            self.assertIn(key, stats)

    def test_counts_match_database(self):
        stats = get_resource_stats()
        self.assertEqual(stats['people'], People.objects.count())
        self.assertEqual(stats['planets'], Planet.objects.count())
        self.assertEqual(stats['films'], Film.objects.count())
        self.assertEqual(stats['species'], Species.objects.count())
        self.assertEqual(stats['vehicles'], Vehicle.objects.count())
        self.assertEqual(stats['starships'], Starship.objects.count())

    def test_counts_are_non_negative(self):
        stats = get_resource_stats()
        for count in stats.values():
            self.assertGreaterEqual(count, 0)


# ── API Root ──────────────────────────────────────────────────────────────────

class APIRootTests(TestCase):
    def test_returns_200(self):
        self.assertEqual(self.client.get('/api/').status_code, 200)

    def test_contains_all_resource_keys(self):
        data = json.loads(self.client.get('/api/').content)
        for key in ('people', 'planets', 'films', 'species', 'vehicles', 'starships'):
            self.assertIn(key, data)

    def test_resource_values_are_urls(self):
        data = json.loads(self.client.get('/api/').content)
        for url in data.values():
            self.assertTrue(url.startswith('http'), f'{url!r} is not a URL')

    def test_content_type_is_json(self):
        response = self.client.get('/api/')
        self.assertIn('application/json', response['Content-Type'])

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post('/api/', {}).status_code, 405)


# ── People Endpoint ───────────────────────────────────────────────────────────

class PeopleEndpointTests(TestCase):
    fixtures = FIXTURES

    EXPECTED_FIELDS = (
        'name', 'height', 'mass', 'hair_color', 'skin_color', 'eye_color',
        'birth_year', 'gender', 'homeworld', 'films', 'species',
        'vehicles', 'starships', 'created', 'edited', 'url',
    )

    def test_list_returns_200(self):
        self.assertEqual(self.client.get('/api/people/').status_code, 200)

    def test_list_pagination_shape(self):
        data = json.loads(self.client.get('/api/people/').content)
        for key in ('count', 'next', 'previous', 'results'):
            self.assertIn(key, data)

    def test_list_results_is_list(self):
        data = json.loads(self.client.get('/api/people/').content)
        self.assertIsInstance(data['results'], list)

    def test_list_count_is_positive(self):
        data = json.loads(self.client.get('/api/people/').content)
        self.assertGreater(data['count'], 0)

    def test_detail_returns_200(self):
        self.assertEqual(self.client.get('/api/people/1/').status_code, 200)

    def test_detail_all_fields_present(self):
        data = json.loads(self.client.get('/api/people/1/').content)
        for field in self.EXPECTED_FIELDS:
            self.assertIn(field, data, f'Missing field: {field!r}')

    def test_detail_name_matches_db(self):
        data = json.loads(self.client.get('/api/people/1/').content)
        self.assertEqual(data['name'], People.objects.get(pk=1).name)

    def test_detail_homeworld_is_url(self):
        data = json.loads(self.client.get('/api/people/1/').content)
        self.assertTrue(data['homeworld'].startswith('http'))

    def test_detail_films_is_list(self):
        data = json.loads(self.client.get('/api/people/1/').content)
        self.assertIsInstance(data['films'], list)

    def test_detail_url_field_is_self_url(self):
        data = json.loads(self.client.get('/api/people/1/').content)
        self.assertIn('/api/people/1/', data['url'])

    def test_detail_not_found_returns_404(self):
        self.assertEqual(self.client.get('/api/people/99999/').status_code, 404)

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post('/api/people/', {}).status_code, 405)

    def test_put_not_allowed(self):
        self.assertEqual(self.client.put('/api/people/1/', {}).status_code, 405)

    def test_patch_not_allowed(self):
        self.assertEqual(self.client.patch('/api/people/1/', {}).status_code, 405)

    def test_delete_not_allowed(self):
        self.assertEqual(self.client.delete('/api/people/1/').status_code, 405)

    def test_search_by_name_returns_match(self):
        data = json.loads(self.client.get('/api/people/?search=r2').content)
        names = [p['name'] for p in data['results']]
        self.assertIn('R2-D2', names)

    def test_search_narrows_results(self):
        total = json.loads(self.client.get('/api/people/').content)['count']
        filtered = json.loads(self.client.get('/api/people/?search=luke').content)['count']
        self.assertLess(filtered, total)

    def test_search_case_insensitive(self):
        lower = json.loads(self.client.get('/api/people/?search=luke').content)['count']
        upper = json.loads(self.client.get('/api/people/?search=LUKE').content)['count']
        self.assertEqual(lower, upper)

    def test_search_no_results(self):
        data = json.loads(self.client.get('/api/people/?search=zzznomatch99').content)
        self.assertEqual(data['count'], 0)
        self.assertEqual(data['results'], [])

    def test_schema_returns_200(self):
        self.assertEqual(self.client.get('/api/people/schema').status_code, 200)

    def test_schema_is_valid_json_object(self):
        response = self.client.get('/api/people/schema')
        data = json.loads(response.content)
        self.assertIsInstance(data, dict)

    def test_schema_content_type_is_json(self):
        response = self.client.get('/api/people/schema')
        self.assertIn('application/json', response['Content-Type'])


# ── Planet Endpoint ───────────────────────────────────────────────────────────

class PlanetEndpointTests(TestCase):
    fixtures = FIXTURES

    EXPECTED_FIELDS = (
        'name', 'rotation_period', 'orbital_period', 'diameter', 'climate',
        'gravity', 'terrain', 'surface_water', 'population',
        'residents', 'films', 'created', 'edited', 'url',
    )

    def test_list_returns_200(self):
        self.assertEqual(self.client.get('/api/planets/').status_code, 200)

    def test_list_pagination_shape(self):
        data = json.loads(self.client.get('/api/planets/').content)
        for key in ('count', 'next', 'previous', 'results'):
            self.assertIn(key, data)

    def test_detail_returns_200(self):
        self.assertEqual(self.client.get('/api/planets/1/').status_code, 200)

    def test_detail_all_fields_present(self):
        data = json.loads(self.client.get('/api/planets/1/').content)
        for field in self.EXPECTED_FIELDS:
            self.assertIn(field, data, f'Missing field: {field!r}')

    def test_detail_name_matches_db(self):
        data = json.loads(self.client.get('/api/planets/1/').content)
        self.assertEqual(data['name'], Planet.objects.get(pk=1).name)

    def test_detail_residents_is_list_of_urls(self):
        data = json.loads(self.client.get('/api/planets/1/').content)
        self.assertIsInstance(data['residents'], list)

    def test_detail_not_found_returns_404(self):
        self.assertEqual(self.client.get('/api/planets/99999/').status_code, 404)

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post('/api/planets/', {}).status_code, 405)

    def test_delete_not_allowed(self):
        self.assertEqual(self.client.delete('/api/planets/1/').status_code, 405)

    def test_search_by_name_returns_match(self):
        data = json.loads(self.client.get('/api/planets/?search=yavin').content)
        names = [p['name'] for p in data['results']]
        self.assertIn('Yavin IV', names)

    def test_search_no_results(self):
        data = json.loads(self.client.get('/api/planets/?search=zzznomatch').content)
        self.assertEqual(data['count'], 0)

    def test_schema_returns_200(self):
        self.assertEqual(self.client.get('/api/planets/schema').status_code, 200)

    def test_schema_is_valid_json_object(self):
        data = json.loads(self.client.get('/api/planets/schema').content)
        self.assertIsInstance(data, dict)


# ── Film Endpoint ─────────────────────────────────────────────────────────────

class FilmEndpointTests(TestCase):
    fixtures = FIXTURES

    EXPECTED_FIELDS = (
        'title', 'episode_id', 'opening_crawl', 'director', 'producer',
        'release_date', 'characters', 'planets', 'starships',
        'vehicles', 'species', 'created', 'edited', 'url',
    )

    def test_list_returns_200(self):
        self.assertEqual(self.client.get('/api/films/').status_code, 200)

    def test_list_pagination_shape(self):
        data = json.loads(self.client.get('/api/films/').content)
        for key in ('count', 'next', 'previous', 'results'):
            self.assertIn(key, data)

    def test_detail_returns_200(self):
        self.assertEqual(self.client.get('/api/films/1/').status_code, 200)

    def test_detail_all_fields_present(self):
        data = json.loads(self.client.get('/api/films/1/').content)
        for field in self.EXPECTED_FIELDS:
            self.assertIn(field, data, f'Missing field: {field!r}')

    def test_detail_title_matches_db(self):
        data = json.loads(self.client.get('/api/films/1/').content)
        self.assertEqual(data['title'], Film.objects.get(pk=1).title)

    def test_detail_episode_id_is_integer(self):
        data = json.loads(self.client.get('/api/films/1/').content)
        self.assertIsInstance(data['episode_id'], int)

    def test_detail_characters_is_list(self):
        data = json.loads(self.client.get('/api/films/1/').content)
        self.assertIsInstance(data['characters'], list)

    def test_detail_not_found_returns_404(self):
        self.assertEqual(self.client.get('/api/films/99999/').status_code, 404)

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post('/api/films/', {}).status_code, 405)

    def test_delete_not_allowed(self):
        self.assertEqual(self.client.delete('/api/films/1/').status_code, 405)

    def test_search_by_title_returns_match(self):
        data = json.loads(self.client.get('/api/films/?search=sith').content)
        titles = [f['title'] for f in data['results']]
        self.assertIn('Revenge of the Sith', titles)

    def test_search_narrows_results(self):
        total = json.loads(self.client.get('/api/films/').content)['count']
        filtered = json.loads(self.client.get('/api/films/?search=hope').content)['count']
        self.assertLess(filtered, total)

    def test_search_no_results(self):
        data = json.loads(self.client.get('/api/films/?search=zzznomatch').content)
        self.assertEqual(data['count'], 0)

    def test_schema_returns_200(self):
        self.assertEqual(self.client.get('/api/films/schema').status_code, 200)

    def test_schema_is_valid_json_object(self):
        data = json.loads(self.client.get('/api/films/schema').content)
        self.assertIsInstance(data, dict)


# ── Species Endpoint ──────────────────────────────────────────────────────────

class SpeciesEndpointTests(TestCase):
    fixtures = FIXTURES

    EXPECTED_FIELDS = (
        'name', 'classification', 'designation', 'average_height',
        'skin_colors', 'hair_colors', 'eye_colors', 'average_lifespan',
        'homeworld', 'language', 'people', 'films', 'created', 'edited', 'url',
    )

    def test_list_returns_200(self):
        self.assertEqual(self.client.get('/api/species/').status_code, 200)

    def test_list_pagination_shape(self):
        data = json.loads(self.client.get('/api/species/').content)
        for key in ('count', 'next', 'previous', 'results'):
            self.assertIn(key, data)

    def test_detail_returns_200(self):
        self.assertEqual(self.client.get('/api/species/1/').status_code, 200)

    def test_detail_all_fields_present(self):
        data = json.loads(self.client.get('/api/species/1/').content)
        for field in self.EXPECTED_FIELDS:
            self.assertIn(field, data, f'Missing field: {field!r}')

    def test_detail_name_matches_db(self):
        data = json.loads(self.client.get('/api/species/1/').content)
        self.assertEqual(data['name'], Species.objects.get(pk=1).name)

    def test_detail_not_found_returns_404(self):
        self.assertEqual(self.client.get('/api/species/99999/').status_code, 404)

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post('/api/species/', {}).status_code, 405)

    def test_delete_not_allowed(self):
        self.assertEqual(self.client.delete('/api/species/1/').status_code, 405)

    def test_search_by_name_returns_match(self):
        data = json.loads(self.client.get('/api/species/?search=calamari').content)
        names = [s['name'] for s in data['results']]
        self.assertIn('Mon Calamari', names)

    def test_search_no_results(self):
        data = json.loads(self.client.get('/api/species/?search=zzznomatch').content)
        self.assertEqual(data['count'], 0)

    def test_schema_returns_200(self):
        self.assertEqual(self.client.get('/api/species/schema').status_code, 200)

    def test_wookiee_format_returns_200(self):
        self.assertEqual(
            self.client.get('/api/species/1/?format=wookiee').status_code, 200
        )

    def test_wookiee_format_translates_name_key(self):
        renderer = WookieeRenderer()
        response = self.client.get('/api/species/1/?format=wookiee')
        data = json.loads(response.content)
        species = Species.objects.get(pk=1)
        wookiee_name_key = renderer.translate_to_wookie('name')
        self.assertIn(wookiee_name_key, data)
        self.assertEqual(
            renderer.translate_to_wookie(species.name),
            data[wookiee_name_key]
        )


# ── Vehicle Endpoint ──────────────────────────────────────────────────────────

class VehicleEndpointTests(TestCase):
    fixtures = FIXTURES

    EXPECTED_FIELDS = (
        'name', 'model', 'manufacturer', 'cost_in_credits', 'length',
        'max_atmosphering_speed', 'crew', 'passengers', 'cargo_capacity',
        'consumables', 'vehicle_class', 'pilots', 'films',
        'created', 'edited', 'url',
    )

    def test_list_returns_200(self):
        self.assertEqual(self.client.get('/api/vehicles/').status_code, 200)

    def test_list_pagination_shape(self):
        data = json.loads(self.client.get('/api/vehicles/').content)
        for key in ('count', 'next', 'previous', 'results'):
            self.assertIn(key, data)

    def test_detail_returns_200(self):
        self.assertEqual(self.client.get('/api/vehicles/4/').status_code, 200)

    def test_detail_all_fields_present(self):
        data = json.loads(self.client.get('/api/vehicles/4/').content)
        for field in self.EXPECTED_FIELDS:
            self.assertIn(field, data, f'Missing field: {field!r}')

    def test_detail_name_matches_db(self):
        data = json.loads(self.client.get('/api/vehicles/4/').content)
        self.assertEqual(data['name'], Vehicle.objects.get(pk=4).name)

    def test_detail_pilots_is_list(self):
        data = json.loads(self.client.get('/api/vehicles/4/').content)
        self.assertIsInstance(data['pilots'], list)

    def test_detail_not_found_returns_404(self):
        self.assertEqual(self.client.get('/api/vehicles/99999/').status_code, 404)

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post('/api/vehicles/', {}).status_code, 405)

    def test_delete_not_allowed(self):
        self.assertEqual(self.client.delete('/api/vehicles/4/').status_code, 405)

    def test_search_by_name_returns_match(self):
        data = json.loads(self.client.get('/api/vehicles/?search=crawler').content)
        names = [v['name'] for v in data['results']]
        self.assertIn('Sand Crawler', names)

    def test_search_by_model_returns_match(self):
        # Sand Crawler has model="Digger Crawler"
        data = json.loads(self.client.get('/api/vehicles/?search=Digger').content)
        self.assertEqual(data['status_code'] if 'status_code' in data else 200, 200)
        names = [v['name'] for v in data['results']]
        self.assertIn('Sand Crawler', names)

    def test_search_no_results(self):
        data = json.loads(self.client.get('/api/vehicles/?search=zzznomatch').content)
        self.assertEqual(data['count'], 0)

    def test_schema_returns_200(self):
        self.assertEqual(self.client.get('/api/vehicles/schema').status_code, 200)

    def test_schema_is_valid_json_object(self):
        data = json.loads(self.client.get('/api/vehicles/schema').content)
        self.assertIsInstance(data, dict)

    def test_wookiee_format_returns_200(self):
        self.assertEqual(
            self.client.get('/api/vehicles/4/?format=wookiee').status_code, 200
        )


# ── Starship Endpoint ─────────────────────────────────────────────────────────

class StarshipEndpointTests(TestCase):
    fixtures = FIXTURES

    EXPECTED_FIELDS = (
        'name', 'model', 'manufacturer', 'cost_in_credits', 'length',
        'max_atmosphering_speed', 'crew', 'passengers', 'cargo_capacity',
        'consumables', 'hyperdrive_rating', 'MGLT', 'starship_class',
        'pilots', 'films', 'created', 'edited', 'url',
    )

    def test_list_returns_200(self):
        self.assertEqual(self.client.get('/api/starships/').status_code, 200)

    def test_list_pagination_shape(self):
        data = json.loads(self.client.get('/api/starships/').content)
        for key in ('count', 'next', 'previous', 'results'):
            self.assertIn(key, data)

    def test_detail_returns_200(self):
        self.assertEqual(self.client.get('/api/starships/2/').status_code, 200)

    def test_detail_all_fields_present(self):
        data = json.loads(self.client.get('/api/starships/2/').content)
        for field in self.EXPECTED_FIELDS:
            self.assertIn(field, data, f'Missing field: {field!r}')

    def test_detail_name_matches_db(self):
        data = json.loads(self.client.get('/api/starships/2/').content)
        self.assertEqual(data['name'], Starship.objects.get(pk=2).name)

    def test_detail_hyperdrive_rating_present(self):
        data = json.loads(self.client.get('/api/starships/2/').content)
        self.assertIsNotNone(data['hyperdrive_rating'])

    def test_detail_pilots_is_list(self):
        data = json.loads(self.client.get('/api/starships/2/').content)
        self.assertIsInstance(data['pilots'], list)

    def test_detail_not_found_returns_404(self):
        self.assertEqual(self.client.get('/api/starships/99999/').status_code, 404)

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post('/api/starships/', {}).status_code, 405)

    def test_delete_not_allowed(self):
        self.assertEqual(self.client.delete('/api/starships/2/').status_code, 405)

    def test_search_by_name_returns_match(self):
        data = json.loads(self.client.get('/api/starships/?search=x1').content)
        names = [s['name'] for s in data['results']]
        self.assertIn('TIE Advanced x1', names)

    def test_search_by_model_returns_match(self):
        # CR90 corvette has model="CR90 corvette"
        data = json.loads(self.client.get('/api/starships/?search=CR90').content)
        names = [s['name'] for s in data['results']]
        self.assertIn('CR90 corvette', names)

    def test_search_no_results(self):
        data = json.loads(self.client.get('/api/starships/?search=zzznomatch').content)
        self.assertEqual(data['count'], 0)

    def test_schema_returns_200(self):
        self.assertEqual(self.client.get('/api/starships/schema').status_code, 200)

    def test_schema_is_valid_json_object(self):
        data = json.loads(self.client.get('/api/starships/schema').content)
        self.assertIsInstance(data, dict)

    def test_wookiee_format_returns_200(self):
        self.assertEqual(
            self.client.get('/api/starships/2/?format=wookiee').status_code, 200
        )


# ── Pagination Tests ──────────────────────────────────────────────────────────

class PaginationTests(TestCase):
    fixtures = FIXTURES

    def test_page_size_respected(self):
        # All fixtures have more than 10 entries; first page should have ≤10
        data = json.loads(self.client.get('/api/people/').content)
        self.assertLessEqual(len(data['results']), 10)

    def test_next_page_link_present_when_more_results(self):
        data = json.loads(self.client.get('/api/people/').content)
        if data['count'] > 10:
            self.assertIsNotNone(data['next'])

    def test_previous_is_null_on_first_page(self):
        data = json.loads(self.client.get('/api/people/').content)
        self.assertIsNone(data['previous'])

    def test_second_page_has_previous_link(self):
        data = json.loads(self.client.get('/api/people/').content)
        if data['count'] > 10:
            data2 = json.loads(self.client.get('/api/people/?page=2').content)
            self.assertIsNotNone(data2['previous'])


# ── ETag / Conditional GET Tests ─────────────────────────────────────────────

class ETagTests(TestCase):
    def test_api_root_returns_etag_header(self):
        response = self.client.get('/api/')
        self.assertIn('ETag', response)

    def test_conditional_get_returns_304(self):
        first = self.client.get('/api/')
        etag = first.get('ETag')
        if etag:
            self.client.defaults['HTTP_IF_NONE_MATCH'] = etag
            second = self.client.get('/api/')
            self.assertEqual(second.status_code, 304)

    def test_stale_etag_returns_200(self):
        self.client.defaults['HTTP_IF_NONE_MATCH'] = '"stale-etag-value"'
        response = self.client.get('/api/')
        self.assertEqual(response.status_code, 200)


# ── CORS Tests ────────────────────────────────────────────────────────────────

class CORSTests(TestCase):
    def test_api_response_has_cors_header(self):
        response = self.client.get(
            '/api/people/', HTTP_ORIGIN='http://example.com'
        )
        self.assertIn('Access-Control-Allow-Origin', response)

    def test_non_api_route_no_cors_header(self):
        # CORS_URLS_REGEX restricts to /api/* only
        response = self.client.get('/', HTTP_ORIGIN='http://example.com')
        self.assertNotIn('Access-Control-Allow-Origin', response)

    def test_cors_only_allows_get(self):
        # CORS_ALLOW_METHODS = ['GET']
        response = self.client.options(
            '/api/people/',
            HTTP_ORIGIN='http://example.com',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='DELETE',
        )
        allow_methods = response.get('Access-Control-Allow-Methods', '')
        if allow_methods:
            self.assertNotIn('DELETE', allow_methods)
