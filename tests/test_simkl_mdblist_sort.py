import ast
import sys
import unittest

from test_trakt_sync_list_sort import ROOT, list_sort, OVERRIDES, SETTINGS

# Other test modules in this suite install their own fake 'caches'/'modules' stubs into
# sys.modules at import time with no cleanup. list_sort.resolve() re-reads sys.modules lazily
# on every call, so a test module that runs before this one (order is randomised) can clobber
# the stub that test_trakt_sync_list_sort installed. Reinstall it here before each test,
# mirroring the save/restore idiom in tests/test_list_sort_resolve.py and
# tests/test_trakt_sync_list_sort.py, so these tests see OVERRIDES/SETTINGS regardless of
# collection order.
_STUB_KEYS = ('caches', 'caches.list_sort_cache', 'caches.settings_cache', 'modules', 'modules.settings')

SIMKL_API = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'apis' / 'simkl_api.py'
MDBLIST_API = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'apis' / 'mdblist_api.py'


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


# Every fixture below is deliberately built so that no two of the four orderings under test
# coincide: the payload order is neither title order nor date order, date_added is NOT in title
# order (Banana is newest but sorts second), and release_date/year is in a third order again. A
# sort_source that ignores media_type, reads the wrong default setting, resolves under the wrong
# list_key, or always falls back to DEFAULT_SPEC (title:asc) therefore produces a visibly wrong
# list instead of accidentally matching the expectation. 'The Alpha' carries a leading article so
# that title:asc also pins the ignore_articles lookup - without the article strip it sorts last.
SIMKL_ROWS = [
	{'order': 1, 'title': 'Cherry', 'collected_at': '2024-01-01', 'released': '1995-01-01'},
	{'order': 2, 'title': 'Banana', 'collected_at': '2024-01-03', 'released': '2001-01-01'},
	{'order': 3, 'title': 'The Alpha', 'collected_at': '2024-01-02', 'released': '1999-01-01'},
]

MDBLIST_WATCHLIST_ROWS = [
	{'title': 'Cherry', 'watchlist_at': '2024-01-01', 'release_date': '1995-01-01'},
	{'title': 'Banana', 'watchlist_at': '2024-01-03', 'release_date': '2001-01-01'},
	{'title': 'The Alpha', 'watchlist_at': '2024-01-02', 'release_date': '1999-01-01'},
]

MDBLIST_COLLECTION_ROWS = [
	{'title': 'Cherry', 'collected_at': '2024-01-01', 'year': 1995},
	{'title': 'Banana', 'collected_at': '2024-01-03', 'year': 2001},
	{'title': 'The Alpha', 'collected_at': '2024-01-02', 'year': 1999},
]

TITLE_ASC = ['The Alpha', 'Banana', 'Cherry']
DATE_ADDED_DESC = ['Banana', 'The Alpha', 'Cherry']
RELEASE_ASC = ['Cherry', 'The Alpha', 'Banana']
RELEASE_DESC = ['Banana', 'The Alpha', 'Cherry']


class SimklSortTests(_StubbedTestCase):
	def test_shows_and_movies_differ(self):
		SETTINGS['redlight.sort.default.movies'] = 'date_added:desc'
		SETTINGS['redlight.sort.default.shows'] = 'title:asc'
		movies = list_sort.sort_source(list(SIMKL_ROWS), 'simkl', 'movies', 'simkl')
		shows = list_sort.sort_source(list(SIMKL_ROWS), 'simkl', 'shows', 'simkl')
		self.assertEqual(DATE_ADDED_DESC, [i['title'] for i in movies])
		self.assertEqual(TITLE_ASC, [i['title'] for i in shows])
		self.assertNotEqual([i['title'] for i in movies], [i['title'] for i in shows])

	def test_release_date_ascending(self):
		SETTINGS['redlight.sort.default.movies'] = 'release_date:asc'
		result = list_sort.sort_source(list(SIMKL_ROWS), 'simkl', 'movies', 'simkl')
		self.assertEqual(RELEASE_ASC, [i['title'] for i in result])

	def test_per_list_override_beats_the_mediatype_default(self):
		SETTINGS['redlight.sort.default.shows'] = 'title:asc'
		OVERRIDES['simkl:shows'] = 'date_added:desc'
		result = list_sort.sort_source(list(SIMKL_ROWS), 'simkl', 'shows', 'simkl')
		self.assertEqual(DATE_ADDED_DESC, [i['title'] for i in result])


class MdblistSortTests(_StubbedTestCase):
	def test_watchlist_date_added_descending(self):
		SETTINGS['redlight.sort.default.movies'] = 'date_added:desc'
		result = list_sort.sort_source(list(MDBLIST_WATCHLIST_ROWS), 'mdblist.watchlist', 'movies', 'mdblist_watchlist')
		self.assertEqual(DATE_ADDED_DESC, [i['title'] for i in result])

	def test_watchlist_shows_read_the_shows_default(self):
		SETTINGS['redlight.sort.default.movies'] = 'title:asc'
		SETTINGS['redlight.sort.default.shows'] = 'release_date:asc'
		result = list_sort.sort_source(list(MDBLIST_WATCHLIST_ROWS), 'mdblist.watchlist', 'shows', 'mdblist_watchlist')
		self.assertEqual(RELEASE_ASC, [i['title'] for i in result])

	def test_collection_release_date_ascending_now_supported(self):
		SETTINGS['redlight.sort.default.movies'] = 'release_date:asc'
		result = list_sort.sort_source(list(MDBLIST_COLLECTION_ROWS), 'mdblist.collection', 'movies', 'mdblist_collection')
		self.assertEqual(RELEASE_ASC, [i['title'] for i in result])

	def test_collection_override_independent_of_watchlist(self):
		SETTINGS['redlight.sort.default.movies'] = 'title:asc'
		OVERRIDES['mdblist.collection:movies'] = 'release_date:desc'
		collection = list_sort.sort_source(list(MDBLIST_COLLECTION_ROWS), 'mdblist.collection', 'movies', 'mdblist_collection')
		watchlist = list_sort.sort_source(list(MDBLIST_WATCHLIST_ROWS), 'mdblist.watchlist', 'movies', 'mdblist_watchlist')
		self.assertEqual(RELEASE_DESC, [i['title'] for i in collection])
		self.assertEqual(TITLE_ASC, [i['title'] for i in watchlist])


def _sort_source_calls(path):
	"""Every list_sort.sort_source(...) call in a module, as (list_key, media_type, adapter_name).

	media_type is None where the call site passes a variable (the media_kind parameter) rather than
	a literal. Parsed from source with ast rather than imported, because the api modules pull in the
	Kodi runtime.
	"""
	with open(str(path), 'r', encoding='utf-8') as f:
		tree = ast.parse(f.read())
	calls = []
	for node in ast.walk(tree):
		if not isinstance(node, ast.Call): continue
		func = node.func
		if not isinstance(func, ast.Attribute) or func.attr != 'sort_source': continue
		if not isinstance(func.value, ast.Name) or func.value.id != 'list_sort': continue
		literals = [a.value if isinstance(a, ast.Constant) else None for a in node.args]
		calls.append((literals[1], literals[2], literals[3]))
	return calls


class CallSiteScopeAgreementTests(_StubbedTestCase):
	"""Pin the agreement between the list_key/adapter literals the api call sites pass and the
	override scopes Task 5's migration writes. Nothing else in the suite would notice a
	one-character drift on either side ('mdblist_watchlist' vs 'mdblist.watchlist'), and the
	result would be every migrated user silently dropped back to title:asc."""

	# sort.simkl deliberately differs from sort.watchlist so the migration emits explicit
	# 'simkl:*' overrides (it skips them when they match the global default it just seeded).
	LEGACY = {'sort.watchlist': '0', 'sort.collection': '2', 'sort.simkl': '1',
		'tmdbsort.watchlist': '4', 'tmdbsort.favorites': '4'}

	def test_simkl_call_sites_use_the_migrated_list_key_and_a_real_adapter(self):
		calls = _sort_source_calls(SIMKL_API)
		self.assertTrue(calls)
		for list_key, _media_type, adapter in calls:
			self.assertEqual('simkl', list_key)
			self.assertIn(adapter, list_sort.ADAPTERS)
			self.assertEqual('simkl', adapter)
		# _simkl_fetch_tv_status re-sorts the merged shows+anime list under a hardcoded 'shows'.
		self.assertIn(('simkl', 'shows', 'simkl'), calls)

	def test_mdblist_call_sites_use_the_migrated_list_keys_and_real_adapters(self):
		calls = _sort_source_calls(MDBLIST_API)
		self.assertEqual({('mdblist.watchlist', 'mdblist_watchlist'), ('mdblist.collection', 'mdblist_collection')},
			set((list_key, adapter) for list_key, _media_type, adapter in calls))
		for _list_key, _media_type, adapter in calls:
			self.assertIn(adapter, list_sort.ADAPTERS)

	def test_every_call_site_resolves_to_the_scope_the_migration_wrote(self):
		overrides = list_sort.migrate_legacy_sort_settings(dict(self.LEGACY))['overrides']
		OVERRIDES.update(overrides)
		calls = _sort_source_calls(SIMKL_API) + _sort_source_calls(MDBLIST_API)
		self.assertTrue(calls)
		for list_key, media_type, _adapter in calls:
			for candidate in ((media_type,) if media_type else ('movies', 'shows')):
				scope = '%s:%s' % (list_key, candidate)
				self.assertIn(scope, overrides)
				self.assertEqual(list_sort.parse_spec(overrides[scope]), list_sort.resolve(list_key, candidate))

	def test_migrated_simkl_and_mdblist_overrides_are_all_reachable_from_a_call_site(self):
		overrides = list_sort.migrate_legacy_sort_settings(dict(self.LEGACY))['overrides']
		call_keys = set(c[0] for c in _sort_source_calls(SIMKL_API) + _sort_source_calls(MDBLIST_API))
		migrated_keys = set(s.rsplit(':', 1)[0] for s in overrides
			if s.startswith('simkl:') or s.startswith('mdblist.'))
		self.assertEqual({'simkl', 'mdblist.watchlist', 'mdblist.collection'}, migrated_keys)
		self.assertEqual(migrated_keys, call_keys)


if __name__ == '__main__':
	unittest.main()
