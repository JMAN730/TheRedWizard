import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'modules' / 'settings.py'


def _load_settings_module(store):
	def get_setting(setting_id, fallback=None):
		return store.get(setting_id.replace('redlight.', '', 1), fallback)

	def set_setting(setting_id, value):
		store[setting_id] = value

	settings_cache = types.ModuleType('caches.settings_cache')
	settings_cache.get_setting = get_setting
	settings_cache.set_setting = set_setting
	settings_cache.default_setting_values = lambda setting_id: {'setting_default': ''}
	settings_cache._EXTRAS_LIST_DEFAULT = ''

	caches = types.ModuleType('caches')
	caches.__path__ = []

	kodi_utils = types.ModuleType('modules.kodi_utils')
	kodi_utils.translate_path = lambda path: path
	kodi_utils.get_property = lambda key: ''
	kodi_utils.addon_profile = lambda: ''
	kodi_utils.make_directory = lambda path: None
	kodi_utils.logger = lambda *args, **kwargs: None

	modules = types.ModuleType('modules')
	modules.__path__ = []
	modules.kodi_utils = kodi_utils

	sys.modules['caches'] = caches
	sys.modules['caches.settings_cache'] = settings_cache
	sys.modules['modules'] = modules
	sys.modules['modules.kodi_utils'] = kodi_utils

	spec = importlib.util.spec_from_file_location('settings_under_test', SETTINGS_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class TraktWatchlistContextMenuTests(unittest.TestCase):
	def setUp(self):
		self._original_sys_modules = {}
		for key in ('caches', 'caches.settings_cache', 'modules', 'modules.kodi_utils'):
			if key in sys.modules:
				self._original_sys_modules[key] = sys.modules[key]
		self.store = {}
		self.settings = _load_settings_module(self.store)

	def tearDown(self):
		for key in ('caches', 'caches.settings_cache', 'modules', 'modules.kodi_utils'):
			if key in self._original_sys_modules:
				sys.modules[key] = self._original_sys_modules[key]
			else:
				sys.modules.pop(key, None)

	def test_default_enabled_and_order_include_trakt_watchlist(self):
		enabled = self.settings.cm_enabled()
		order = self.settings.cm_current_order()
		self.assertIn('trakt_watchlist', enabled)
		self.assertIn('trakt_watchlist', order)
		self.assertLess(order.index('trakt_watchlist'), order.index('mdblist_manager'))
		self.assertLess(order.index('in_trakt_list'), order.index('trakt_watchlist'))

	def test_migration_appends_to_customized_enabled_setting(self):
		self.store['context_menu.enabled'] = 'extras,options,trakt_manager,mark_watched'
		self.store['context_menu.order'] = 'extras,options,trakt_manager,mark_watched'
		changed = self.settings.migrate_trakt_watchlist_context_menu_for_upgrade(True)
		self.assertTrue(changed)
		enabled = self.store['context_menu.enabled'].split(',')
		self.assertIn('trakt_watchlist', enabled)
		order = self.store['context_menu.order'].split(',')
		self.assertIn('trakt_watchlist', order)
		self.assertLess(order.index('trakt_watchlist'), order.index('trakt_manager'))

	def test_migration_runs_once(self):
		self.store['context_menu.enabled'] = 'extras,trakt_manager'
		self.assertTrue(self.settings.migrate_trakt_watchlist_context_menu_for_upgrade(True))
		self.store['context_menu.enabled'] = 'extras,trakt_manager'
		self.assertFalse(self.settings.migrate_trakt_watchlist_context_menu_for_upgrade(True))

	def test_migration_skips_fresh_install(self):
		self.assertFalse(self.settings.migrate_trakt_watchlist_context_menu_for_upgrade(False))
		self.assertNotIn('context_menu.enabled', self.store)

	def test_normalize_keeps_watchlist_before_manager_group(self):
		order = self.settings._normalize_cm_list_order(
			['extras', 'trakt_watchlist', 'mdblist_manager', 'simkl_manager', 'trakt_manager', 'tmdb_manager'])
		self.assertEqual(['extras', 'trakt_watchlist', 'mdblist_manager', 'simkl_manager', 'trakt_manager', 'tmdb_manager'], order)


if __name__ == '__main__':
	unittest.main()
