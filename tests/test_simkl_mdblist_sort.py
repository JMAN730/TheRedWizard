import sys
import unittest

from test_trakt_sync_list_sort import list_sort, OVERRIDES, SETTINGS

# Other test modules in this suite install their own fake 'caches'/'modules' stubs into
# sys.modules at import time with no cleanup. list_sort.resolve() re-reads sys.modules lazily
# on every call, so a test module that runs before this one (order is randomised) can clobber
# the stub that test_trakt_sync_list_sort installed. Reinstall it here before each test,
# mirroring the save/restore idiom in tests/test_list_sort_resolve.py and
# tests/test_trakt_sync_list_sort.py, so these tests see OVERRIDES/SETTINGS regardless of
# collection order.
_STUB_KEYS = ('caches', 'caches.list_sort_cache', 'caches.settings_cache', 'modules', 'modules.settings')


def _install_stubs():
	import types
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


class _StubbedTestCase(unittest.TestCase):
	def setUp(self):
		self._original_sys_modules = {}
		for key in _STUB_KEYS:
			if key in sys.modules:
				self._original_sys_modules[key] = sys.modules[key]
		_install_stubs()
		OVERRIDES.clear()
		SETTINGS.clear()

	def tearDown(self):
		for key in _STUB_KEYS:
			if key in self._original_sys_modules:
				sys.modules[key] = self._original_sys_modules[key]
			else:
				sys.modules.pop(key, None)
		OVERRIDES.clear()
		SETTINGS.clear()


SIMKL_ROWS = [
	{'order': 1, 'title': 'Banana', 'collected_at': '2024-01-02', 'released': '2001-01-01'},
	{'order': 2, 'title': 'Alpha', 'collected_at': '2024-01-03', 'released': '1999-01-01'},
]

MDBLIST_WATCHLIST_ROWS = [
	{'title': 'Banana', 'watchlist_at': '2024-01-02', 'release_date': '2001-01-01'},
	{'title': 'Alpha', 'watchlist_at': '2024-01-03', 'release_date': '1999-01-01'},
]

MDBLIST_COLLECTION_ROWS = [
	{'title': 'Banana', 'collected_at': '2024-01-02', 'year': 2001},
	{'title': 'Alpha', 'collected_at': '2024-01-03', 'year': 1999},
]


class SimklSortTests(_StubbedTestCase):
	def test_shows_and_movies_differ(self):
		SETTINGS['redlight.sort.default.movies'] = 'date_added:desc'
		SETTINGS['redlight.sort.default.shows'] = 'title:asc'
		movies = list_sort.sort_source(list(SIMKL_ROWS), 'simkl', 'movies', 'simkl')
		shows = list_sort.sort_source(list(SIMKL_ROWS), 'simkl', 'shows', 'simkl')
		self.assertEqual(['Alpha', 'Banana'], [i['title'] for i in movies])
		self.assertEqual(['Alpha', 'Banana'], [i['title'] for i in shows])

	def test_release_date_ascending(self):
		SETTINGS['redlight.sort.default.movies'] = 'release_date:asc'
		result = list_sort.sort_source(list(SIMKL_ROWS), 'simkl', 'movies', 'simkl')
		self.assertEqual(['Alpha', 'Banana'], [i['title'] for i in result])


class MdblistSortTests(_StubbedTestCase):
	def test_watchlist_date_added_descending(self):
		SETTINGS['redlight.sort.default.movies'] = 'date_added:desc'
		result = list_sort.sort_source(list(MDBLIST_WATCHLIST_ROWS), 'mdblist.watchlist', 'movies', 'mdblist_watchlist')
		self.assertEqual(['Alpha', 'Banana'], [i['title'] for i in result])

	def test_collection_release_date_ascending_now_supported(self):
		SETTINGS['redlight.sort.default.movies'] = 'release_date:asc'
		result = list_sort.sort_source(list(MDBLIST_COLLECTION_ROWS), 'mdblist.collection', 'movies', 'mdblist_collection')
		self.assertEqual(['Alpha', 'Banana'], [i['title'] for i in result])

	def test_collection_override_independent_of_watchlist(self):
		SETTINGS['redlight.sort.default.movies'] = 'title:asc'
		OVERRIDES['mdblist.collection:movies'] = 'release_date:desc'
		collection = list_sort.sort_source(list(MDBLIST_COLLECTION_ROWS), 'mdblist.collection', 'movies', 'mdblist_collection')
		watchlist = list_sort.sort_source(list(MDBLIST_WATCHLIST_ROWS), 'mdblist.watchlist', 'movies', 'mdblist_watchlist')
		self.assertEqual(['Banana', 'Alpha'], [i['title'] for i in collection])
		self.assertEqual(['Alpha', 'Banana'], [i['title'] for i in watchlist])


if __name__ == '__main__':
	unittest.main()
