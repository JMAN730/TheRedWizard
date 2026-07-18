import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'modules' / 'settings.py'


def _load_settings_module(initial):
	values = dict(initial)

	def normalize_key(setting_id):
		return setting_id if setting_id.startswith('redlight.') else 'redlight.%s' % setting_id

	settings_cache = types.ModuleType('caches.settings_cache')
	settings_cache._EXTRAS_LIST_DEFAULT = ()
	settings_cache.default_setting_values = lambda setting_id: {'setting_default': ''}
	settings_cache.get_setting = lambda setting_id, fallback='': values.get(normalize_key(setting_id), fallback)
	settings_cache.set_setting = lambda setting_id, value: values.__setitem__(normalize_key(setting_id), value)

	caches = types.ModuleType('caches')
	caches.__path__ = []
	caches.settings_cache = settings_cache
	kodi_utils = types.ModuleType('modules.kodi_utils')
	kodi_utils.addon_profile = lambda: ''
	kodi_utils.get_property = lambda key: ''
	kodi_utils.logger = lambda *args, **kwargs: None
	kodi_utils.make_directory = lambda path: None
	kodi_utils.translate_path = lambda path: path
	modules = types.ModuleType('modules')
	modules.__path__ = [str(SETTINGS_PATH.parent)]
	modules.kodi_utils = kodi_utils

	sys.modules['caches'] = caches
	sys.modules['caches.settings_cache'] = settings_cache
	sys.modules['modules'] = modules
	sys.modules['modules.kodi_utils'] = kodi_utils

	spec = importlib.util.spec_from_file_location('settings_under_test', SETTINGS_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module, values


class TraktWatchlistContextMenuMigrationTests(unittest.TestCase):
	def setUp(self):
		self._module_keys = ('caches', 'caches.settings_cache', 'modules', 'modules.context_menu', 'modules.kodi_utils')
		self._original_sys_modules = {
			key: sys.modules[key] for key in self._module_keys if key in sys.modules
		}

	def tearDown(self):
		for key in self._module_keys:
			if key in self._original_sys_modules:
				sys.modules[key] = self._original_sys_modules[key]
			else:
				sys.modules.pop(key, None)

	def test_upgrade_adds_watchlist_action_without_reordering_existing_items(self):
		module, values = _load_settings_module({
			'redlight.context_menu.enabled': 'extras,trakt_manager,mark_watched,exit',
			'redlight.context_menu.order': 'mark_watched,extras,trakt_manager,exit',
		})

		changed = module.migrate_trakt_watchlist_context_menu_for_upgrade(True)

		self.assertTrue(changed)
		self.assertEqual(
			'extras,trakt_manager,trakt_watchlist,mark_watched,exit',
			values['redlight.context_menu.enabled'],
		)
		self.assertEqual(
			'trakt_watchlist,mark_watched,extras,trakt_manager,exit',
			values['redlight.context_menu.order'],
		)

	def test_runtime_context_menu_defaults_include_watchlist_action(self):
		module, _ = _load_settings_module({})

		for items in (module.cm_enabled(), module.cm_current_order()):
			self.assertIn('trakt_watchlist', items)
			self.assertEqual(items.index('trakt_watchlist') + 1, items.index('mark_watched'))

	def test_completed_migration_does_not_duplicate_watchlist_action(self):
		module, values = _load_settings_module({
			'redlight.trakt_watchlist.cm_menu_migrated': 'true',
			'redlight.context_menu.enabled': 'extras,trakt_watchlist,mark_watched',
			'redlight.context_menu.order': 'extras,trakt_watchlist,mark_watched',
		})

		changed = module.migrate_trakt_watchlist_context_menu_for_upgrade(True)

		self.assertFalse(changed)
		self.assertEqual('extras,trakt_watchlist,mark_watched', values['redlight.context_menu.enabled'])
		self.assertEqual('extras,trakt_watchlist,mark_watched', values['redlight.context_menu.order'])


if __name__ == '__main__':
	unittest.main()
