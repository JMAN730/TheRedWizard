import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'modules' / 'router.py'


class TraktWatchlistRouterTests(unittest.TestCase):
	def setUp(self):
		self.module_keys = (
			'xbmc', 'modules', 'modules.kodi_utils', 'modules.trakt_actions',
			'caches', 'caches.settings_cache', 'apis', 'apis.trakt_api',
		)
		self.original_modules = {
			key: sys.modules[key] for key in self.module_keys if key in sys.modules
		}

	def tearDown(self):
		for key in self.module_keys:
			if key in self.original_modules:
				sys.modules[key] = self.original_modules[key]
			else:
				sys.modules.pop(key, None)

	def test_direct_watchlist_route_dispatches_validated_action(self):
		received = []
		expected_result = object()

		xbmc = types.ModuleType('xbmc')
		xbmc.getInfoLabel = lambda label: ''
		kodi_utils = types.ModuleType('modules.kodi_utils')
		kodi_utils.external = lambda: False
		kodi_utils.get_property = lambda key: ''
		kodi_utils.logger = lambda *args, **kwargs: None
		trakt_actions = types.ModuleType('modules.trakt_actions')
		trakt_actions.add_to_watchlist_item = lambda params: received.append(params) or expected_result
		modules = types.ModuleType('modules')
		modules.__path__ = []
		modules.kodi_utils = kodi_utils
		modules.trakt_actions = trakt_actions

		settings_cache = types.ModuleType('caches.settings_cache')
		settings_cache.ensure_settings_properties_loaded = lambda: None
		settings_cache.is_directory_listing_mode = lambda mode: False
		settings_cache.should_block_bootstrap_on_entry = lambda mode: False
		settings_cache.sync_kodi_profile_context = lambda: None
		caches = types.ModuleType('caches')
		caches.__path__ = []
		caches.settings_cache = settings_cache
		trakt_api = types.ModuleType('apis.trakt_api')
		apis = types.ModuleType('apis')
		apis.__path__ = []
		apis.trakt_api = trakt_api

		sys.modules.update({
			'xbmc': xbmc,
			'modules': modules,
			'modules.kodi_utils': kodi_utils,
			'modules.trakt_actions': trakt_actions,
			'caches': caches,
			'caches.settings_cache': settings_cache,
			'apis': apis,
			'apis.trakt_api': trakt_api,
		})

		spec = importlib.util.spec_from_file_location('router_under_test', ROUTER_PATH)
		router = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(router)
		request = types.SimpleNamespace(argv=[
			'plugin://plugin.video.redlight',
			'1',
			'?mode=trakt.add_to_watchlist_item&media_type=movie&tmdb_id=550',
		])

		result = router.routing(request)

		self.assertIs(expected_result, result)
		self.assertEqual([{
			'mode': 'trakt.add_to_watchlist_item',
			'media_type': 'movie',
			'tmdb_id': '550',
		}], received)


if __name__ == '__main__':
	unittest.main()
