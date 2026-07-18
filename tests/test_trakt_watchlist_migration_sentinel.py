import sys
import unittest

from test_settings_cache_calendar_migration import FakeSettingsCache, _load_settings_cache_module


class TraktWatchlistMigrationSentinelTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls._original_sys_modules = {}
		for key in ('modules', 'modules.kodi_utils', 'modules.settings', 'caches', 'caches.base_cache'):
			if key in sys.modules:
				cls._original_sys_modules[key] = sys.modules[key]
		cls.module = _load_settings_cache_module()

	@classmethod
	def tearDownClass(cls):
		for key in ('modules', 'modules.kodi_utils', 'modules.settings', 'caches', 'caches.base_cache'):
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

	def test_sentinel_survives_sync_on_existing_profile(self):
		# If the sentinel is missing from default_settings(), sync_settings()
		# removes it as obsolete and the watchlist migration reruns on every
		# startup, re-enabling the entry after a user disables it.
		cache = FakeSettingsCache({'trakt_watchlist.cm_menu_migrated': 'true'})
		self._sync(cache)
		self.assertEqual('true', cache.data.get('trakt_watchlist.cm_menu_migrated'))


if __name__ == '__main__':
	unittest.main()
