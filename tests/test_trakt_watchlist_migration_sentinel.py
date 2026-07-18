import sys
import unittest

from test_settings_cache_calendar_migration import FakeSettingsCache, _load_settings_cache_module
from test_trakt_watchlist_context_menu import _load_settings_module


class TraktWatchlistMigrationSentinelTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls._original_sys_modules = {}
		for key in ('modules', 'modules.kodi_utils', 'modules.settings', 'caches', 'caches.base_cache', 'caches.settings_cache'):
			if key in sys.modules:
				cls._original_sys_modules[key] = sys.modules[key]
		cls.module = _load_settings_cache_module()

	@classmethod
	def tearDownClass(cls):
		for key in ('modules', 'modules.kodi_utils', 'modules.settings', 'caches', 'caches.base_cache', 'caches.settings_cache'):
			if key in cls._original_sys_modules:
				sys.modules[key] = cls._original_sys_modules[key]
			else:
				sys.modules.pop(key, None)

	def setUp(self):
		self.module._test_properties.clear()

	def _sync(self, cache):
		self.module.settings_cache = cache
		result = self.module.sync_settings({'silent': 'true', 'load_properties': 'false', 'force': 'true'})
		self.assertEqual('synced', result)

	def test_sentinel_declared_in_default_settings(self):
		ids = [s['setting_id'] for s in self.module.default_settings()]
		self.assertIn('trakt_watchlist.cm_menu_migrated', ids)

	def test_sync_does_not_rerun_migration_on_existing_profile(self):
		# If the sentinel is missing from default_settings(), sync_settings()
		# removes it as obsolete before running migrations, so the real
		# migration reruns and re-adds trakt_watchlist after a user removed it.
		customized = 'extras,options,trakt_manager,mark_watched'
		cache = FakeSettingsCache({
			'trakt_watchlist.cm_menu_migrated': 'true',
			'context_menu.enabled': customized,
			'context_menu.order': customized,
		})
		settings_module = _load_settings_module(cache.data)
		sys.modules['modules.settings'].migrate_trakt_watchlist_context_menu_for_upgrade = \
			settings_module.migrate_trakt_watchlist_context_menu_for_upgrade
		try:
			self._sync(cache)
		finally:
			sys.modules['modules.settings'].migrate_trakt_watchlist_context_menu_for_upgrade = lambda had_existing: False
		self.assertEqual('true', cache.data.get('trakt_watchlist.cm_menu_migrated'))
		self.assertEqual(customized, cache.data.get('context_menu.enabled'))
		self.assertEqual(customized, cache.data.get('context_menu.order'))


if __name__ == '__main__':
	unittest.main()
