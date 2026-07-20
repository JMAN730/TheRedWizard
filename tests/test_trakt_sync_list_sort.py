import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIST_SORT_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'modules' / 'list_sort.py'

OVERRIDES = {}
SETTINGS = {}


def _load_list_sort_module():
	caches = types.ModuleType('caches')
	caches.__path__ = []
	list_sort_cache = types.ModuleType('caches.list_sort_cache')
	_media = {'movie': 'movies', 'movies': 'movies', 'show': 'shows', 'shows': 'shows', 'tvshow': 'shows'}

	def scope_key(list_key, media_type=None):
		normalized = _media.get(str(media_type).lower(), '') if media_type else ''
		return '%s:%s' % (list_key, normalized) if normalized else list_key

	list_sort_cache.scope_key = scope_key
	list_sort_cache.normalize_media_type = lambda m: _media.get(str(m).lower(), '') if m else ''
	list_sort_cache.get_override = lambda scope: OVERRIDES.get(scope, '')
	list_sort_cache.set_override = lambda scope, spec: True
	settings_cache = types.ModuleType('caches.settings_cache')
	settings_cache.get_setting = lambda setting_id, fallback='': SETTINGS.get(setting_id, fallback)
	modules = types.ModuleType('modules')
	modules.__path__ = []
	settings = types.ModuleType('modules.settings')
	settings.ignore_articles = lambda: True
	sys.modules['caches'] = caches
	sys.modules['caches.list_sort_cache'] = list_sort_cache
	sys.modules['caches.settings_cache'] = settings_cache
	sys.modules['modules'] = modules
	sys.modules['modules.settings'] = settings
	spec = importlib.util.spec_from_file_location('list_sort_source_under_test', LIST_SORT_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


list_sort = _load_list_sort_module()

MOVIES = [
	{'title': 'Banana', 'collected_at': '2024-01-02', 'released': '2001-01-01'},
	{'title': 'The Apple', 'collected_at': '2024-01-03', 'released': '1999-01-01'},
]
SHOWS = [
	{'title': 'Zulu', 'collected_at': '2024-01-02', 'released': '2001-01-01'},
	{'title': 'Alpha', 'collected_at': '2024-01-03', 'released': '1999-01-01'},
]


class SortSourceTests(unittest.TestCase):
	def setUp(self):
		OVERRIDES.clear()
		SETTINGS.clear()

	def test_movies_and_shows_sort_independently(self):
		SETTINGS['redlight.sort.default.movies'] = 'date_added:desc'
		SETTINGS['redlight.sort.default.shows'] = 'title:asc'
		movies = list_sort.sort_source(list(MOVIES), 'trakt.watchlist', 'movies', 'trakt_sync')
		shows = list_sort.sort_source(list(SHOWS), 'trakt.watchlist', 'shows', 'trakt_sync')
		self.assertEqual(['The Apple', 'Banana'], [i['title'] for i in movies])
		self.assertEqual(['Alpha', 'Zulu'], [i['title'] for i in shows])

	def test_per_list_override_applies_to_one_media_type_only(self):
		SETTINGS['redlight.sort.default.movies'] = 'title:asc'
		OVERRIDES['trakt.collection:movies'] = 'release_date:desc'
		collection = list_sort.sort_source(list(MOVIES), 'trakt.collection', 'movies', 'trakt_sync')
		watchlist = list_sort.sort_source(list(MOVIES), 'trakt.watchlist', 'movies', 'trakt_sync')
		self.assertEqual(['Banana', 'The Apple'], [i['title'] for i in collection])
		self.assertEqual(['The Apple', 'Banana'], [i['title'] for i in watchlist])

	def test_unknown_adapter_returns_input_unchanged(self):
		result = list_sort.sort_source(list(MOVIES), 'trakt.watchlist', 'movies', 'nope')
		self.assertEqual(['Banana', 'The Apple'], [i['title'] for i in result])

	def test_none_data_is_safe(self):
		self.assertEqual(None, list_sort.sort_source(None, 'trakt.watchlist', 'movies', 'trakt_sync'))

	def test_reads_ignore_articles_setting(self):
		SETTINGS['redlight.sort.default.movies'] = 'title:asc'
		result = list_sort.sort_source(list(MOVIES), 'trakt.watchlist', 'movies', 'trakt_sync')
		self.assertEqual(['The Apple', 'Banana'], [i['title'] for i in result])


if __name__ == '__main__':
	unittest.main()
