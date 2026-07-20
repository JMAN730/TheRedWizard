import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIST_SORT_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'modules' / 'list_sort.py'


def _install_stubs():
	caches = types.ModuleType('caches')
	caches.__path__ = []
	list_sort_cache = types.ModuleType('caches.list_sort_cache')
	list_sort_cache.scope_key = lambda list_key, media_type=None: list_key
	list_sort_cache.normalize_media_type = lambda m: ''
	list_sort_cache.get_override = lambda scope: ''
	list_sort_cache.set_override = lambda scope, spec: True
	settings_cache = types.ModuleType('caches.settings_cache')
	settings_cache.get_setting = lambda setting_id, fallback='': fallback
	sys.modules['caches'] = caches
	sys.modules['caches.list_sort_cache'] = list_sort_cache
	sys.modules['caches.settings_cache'] = settings_cache


def _load_list_sort_module():
	_install_stubs()
	spec = importlib.util.spec_from_file_location('list_sort_migration_under_test', LIST_SORT_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


list_sort = _load_list_sort_module()


class LegacyCodeTranslationTests(unittest.TestCase):
	def test_all_sync_codes(self):
		expected = {'0': 'title:asc', '1': 'date_added:desc', '2': 'release_date:desc', '3': 'date_added:asc', '4': 'release_date:asc'}
		for code, spec_string in expected.items():
			self.assertEqual(spec_string, list_sort.LEGACY_SYNC_CODES[code], 'code %s' % code)

	def test_all_tmdb_codes(self):
		expected = {'0': 'title:asc', '1': 'release_date:asc', '2': 'release_date:desc', '3': 'random:asc', '4': 'default:asc'}
		for code, spec_string in expected.items():
			self.assertEqual(spec_string, list_sort.LEGACY_TMDB_CODES[code], 'code %s' % code)


class MigrationTests(unittest.TestCase):
	def test_watchlist_seeds_both_defaults(self):
		result = list_sort.migrate_legacy_sort_settings({'sort.watchlist': '1'})
		self.assertEqual('date_added:desc', result['defaults']['sort.default.movies'])
		self.assertEqual('date_added:desc', result['defaults']['sort.default.shows'])

	def test_no_old_settings_produces_nothing(self):
		result = list_sort.migrate_legacy_sort_settings({})
		self.assertEqual({}, result['defaults'])
		self.assertEqual({}, result['overrides'])

	def test_matching_collection_produces_no_override(self):
		result = list_sort.migrate_legacy_sort_settings({'sort.watchlist': '2', 'sort.collection': '2'})
		self.assertEqual({}, result['overrides'])

	def test_differing_collection_overrides_trakt_and_mdblist(self):
		result = list_sort.migrate_legacy_sort_settings({'sort.watchlist': '0', 'sort.collection': '1'})
		self.assertEqual('date_added:desc', result['overrides']['trakt.collection:movies'])
		self.assertEqual('date_added:desc', result['overrides']['trakt.collection:shows'])
		self.assertEqual('date_added:desc', result['overrides']['mdblist.collection:movies'])
		self.assertEqual('date_added:desc', result['overrides']['mdblist.collection:shows'])

	def test_differing_simkl_overrides_both_media_types(self):
		result = list_sort.migrate_legacy_sort_settings({'sort.watchlist': '0', 'sort.simkl': '4'})
		self.assertEqual('release_date:asc', result['overrides']['simkl:movies'])
		self.assertEqual('release_date:asc', result['overrides']['simkl:shows'])

	def test_mdblist_watchlist_never_gets_an_override(self):
		result = list_sort.migrate_legacy_sort_settings({'sort.watchlist': '3'})
		self.assertNotIn('mdblist.watchlist:movies', result['overrides'])

	def test_tmdb_settings_always_become_overrides(self):
		result = list_sort.migrate_legacy_sort_settings({'tmdbsort.watchlist': '4', 'tmdbsort.favorites': '2'})
		self.assertEqual('default:asc', result['overrides']['tmdb:watchlist'])
		self.assertEqual('release_date:desc', result['overrides']['tmdb:favorites'])

	def test_unknown_code_is_ignored(self):
		result = list_sort.migrate_legacy_sort_settings({'sort.watchlist': '99'})
		self.assertEqual({}, result['defaults'])


class LegacyStoreTranslationTests(unittest.TestCase):
	def test_trakt_custom_sort_keys_remap(self):
		cases = {
			('added', 'desc'): 'date_added:desc',
			('popularity', 'asc'): 'votes:asc',
			('percentage', 'desc'): 'rating:desc',
			('released', 'asc'): 'release_date:asc',
			('rank', 'asc'): 'rank:asc',
			('runtime', 'desc'): 'runtime:desc',
			('title', 'desc'): 'title:desc',
			('random', 'asc'): 'random:asc',
			('default', 'asc'): 'default:asc',
		}
		for (sort_by, sort_how), expected in cases.items():
			self.assertEqual(expected, list_sort.translate_trakt_custom_sort(sort_by, sort_how), sort_by)

	def test_unknown_trakt_key_returns_empty(self):
		self.assertEqual('', list_sort.translate_trakt_custom_sort('nonsense', 'asc'))

	def test_personal_codes(self):
		expected = {'0': 'title:asc', '1': 'date_added:asc', '2': 'date_added:desc', '3': 'release_date:asc',
			'4': 'release_date:desc', '5': 'random:asc', 'None': 'default:asc'}
		for code, spec_string in expected.items():
			self.assertEqual(spec_string, list_sort.LEGACY_PERSONAL_CODES[code], 'code %s' % code)


class RunMigrationTests(unittest.TestCase):
	# run_sort_migration() does a lazy `from caches.list_sort_cache import set_override`
	# inside the function body, so it resolves whatever is in sys.modules at call time —
	# not what was there when this file's module-level list_sort was built. Other test
	# files in this suite install their own competing 'caches.list_sort_cache' stub at
	# import time (e.g. test_list_sort_resolve.py's stub has no set_override), and
	# collection order can leave that stub in sys.modules by the time these tests run.
	# Reinstall our own stubs here so these tests are independent of collection order.
	def setUp(self):
		self._original_sys_modules = {}
		for key in ('caches', 'caches.list_sort_cache', 'caches.settings_cache'):
			if key in sys.modules:
				self._original_sys_modules[key] = sys.modules[key]
		_install_stubs()

	def tearDown(self):
		for key in ('caches', 'caches.list_sort_cache', 'caches.settings_cache'):
			if key in self._original_sys_modules:
				sys.modules[key] = self._original_sys_modules[key]
			else:
				sys.modules.pop(key, None)

	def test_writes_defaults_and_overrides(self):
		written_settings, written_overrides = {}, {}
		list_sort_cache = sys.modules['caches.list_sort_cache']
		list_sort_cache.set_override = lambda scope, spec: written_overrides.__setitem__(scope, spec) or True
		changed = list_sort.run_sort_migration({'sort.watchlist': '1', 'sort.collection': '2'},
			lambda setting_id, value: written_settings.__setitem__(setting_id, value))
		self.assertTrue(changed)
		self.assertEqual('date_added:desc', written_settings['sort.default.movies'])
		self.assertEqual('Date Added (descending)', written_settings['sort.default.movies_name'])
		self.assertEqual('release_date:desc', written_overrides['trakt.collection:movies'])

	def test_no_legacy_settings_reports_no_change(self):
		changed = list_sort.run_sort_migration({}, lambda setting_id, value: None)
		self.assertFalse(changed)


class SentinelTests(unittest.TestCase):
	def setUp(self):
		self._original_sys_modules = {}
		for key in ('modules', 'modules.kodi_utils', 'modules.settings', 'caches', 'caches.base_cache', 'caches.settings_cache'):
			if key in sys.modules:
				self._original_sys_modules[key] = sys.modules[key]

	def tearDown(self):
		for key in ('modules', 'modules.kodi_utils', 'modules.settings', 'caches', 'caches.base_cache', 'caches.settings_cache'):
			if key in self._original_sys_modules:
				sys.modules[key] = self._original_sys_modules[key]
			else:
				sys.modules.pop(key, None)

	def test_sentinel_declared_in_default_settings(self):
		from test_settings_cache_calendar_migration import _load_settings_cache_module
		module = _load_settings_cache_module()
		ids = [s['setting_id'] for s in module.default_settings()]
		self.assertIn('migration.unified_list_sort', ids)

	def test_new_sort_defaults_declared(self):
		from test_settings_cache_calendar_migration import _load_settings_cache_module
		module = _load_settings_cache_module()
		ids = [s['setting_id'] for s in module.default_settings()]
		for setting_id in ('sort.default.movies', 'sort.default.movies_name', 'sort.default.shows', 'sort.default.shows_name'):
			self.assertIn(setting_id, ids)

	def test_old_sort_ids_removed(self):
		from test_settings_cache_calendar_migration import _load_settings_cache_module
		module = _load_settings_cache_module()
		ids = [s['setting_id'] for s in module.default_settings()]
		for setting_id in ('sort.watchlist', 'sort.collection', 'sort.simkl', 'tmdbsort.watchlist', 'tmdbsort.favorites'):
			self.assertNotIn(setting_id, ids)

	def test_progress_and_watched_sorts_survive(self):
		from test_settings_cache_calendar_migration import _load_settings_cache_module
		module = _load_settings_cache_module()
		ids = [s['setting_id'] for s in module.default_settings()]
		self.assertIn('sort.progress', ids)
		self.assertIn('sort.watched', ids)


if __name__ == '__main__':
	unittest.main()
