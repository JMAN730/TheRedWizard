import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAKT_ACTIONS_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'modules' / 'trakt_actions.py'


def _load_trakt_actions_module(trakt_active=True):
	notifications = []
	requests = []
	result = object()

	kodi_utils = types.ModuleType('modules.kodi_utils')
	kodi_utils.notification = lambda message, duration=0: notifications.append((message, duration))
	settings = types.ModuleType('modules.settings')
	settings.trakt_user_active = lambda: trakt_active
	modules = types.ModuleType('modules')
	modules.__path__ = []
	modules.kodi_utils = kodi_utils
	modules.settings = settings

	trakt_api = types.ModuleType('apis.trakt_api')
	trakt_api.add_to_watchlist = lambda payload: requests.append(payload) or result
	apis = types.ModuleType('apis')
	apis.__path__ = []
	apis.trakt_api = trakt_api

	sys.modules['modules'] = modules
	sys.modules['modules.kodi_utils'] = kodi_utils
	sys.modules['modules.settings'] = settings
	sys.modules['apis'] = apis
	sys.modules['apis.trakt_api'] = trakt_api

	spec = importlib.util.spec_from_file_location('trakt_actions_under_test', TRAKT_ACTIONS_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module, notifications, requests, result


class TraktWatchlistContextMenuTests(unittest.TestCase):
	def setUp(self):
		self._original_sys_modules = {
			key: sys.modules[key]
			for key in ('modules', 'modules.kodi_utils', 'modules.settings', 'apis', 'apis.trakt_api')
			if key in sys.modules
		}

	def tearDown(self):
		for key in ('modules', 'modules.kodi_utils', 'modules.settings', 'apis', 'apis.trakt_api'):
			if key in self._original_sys_modules:
				sys.modules[key] = self._original_sys_modules[key]
			else:
				sys.modules.pop(key, None)

	def test_movie_context_action_opens_direct_watchlist_route(self):
		module, _, _, _ = _load_trakt_actions_module()
		built_params = []

		def build_url(params):
			built_params.append(params)
			return 'plugin://plugin.video.redlight/direct-watchlist'

		item = module.watchlist_context_menu_item(build_url, {
			'tmdb_id': 550,
			'imdb_id': 'tt0137523',
			'tvdb_id': 'None',
			'media_type': 'movie',
		})

		self.assertEqual(
			['trakt_watchlist', ('[B]Add to Watchlist[/B]',
								 'RunPlugin(plugin://plugin.video.redlight/direct-watchlist)')],
			item,
		)
		self.assertEqual([{
			'mode': 'trakt.add_to_watchlist_item',
			'tmdb_id': 550,
			'imdb_id': 'tt0137523',
			'tvdb_id': 'None',
			'media_type': 'movie',
		}], built_params)

	def test_active_user_can_add_movie_directly_to_watchlist(self):
		module, notifications, requests, api_result = _load_trakt_actions_module()

		result = module.add_to_watchlist_item({
			'tmdb_id': '550',
			'imdb_id': 'tt0137523',
			'tvdb_id': 'None',
			'media_type': 'movie',
		})

		self.assertIs(api_result, result)
		self.assertEqual([{'movies': [{'ids': {'tmdb': 550}}]}], requests)
		self.assertEqual([], notifications)

	def test_active_user_can_add_tv_show_using_available_external_id(self):
		module, notifications, requests, api_result = _load_trakt_actions_module()

		result = module.add_to_watchlist_item({
			'tmdb_id': 'None',
			'imdb_id': 'tt0944947',
			'tvdb_id': '121361',
			'media_type': 'tvshow',
		})

		self.assertIs(api_result, result)
		self.assertEqual([{'shows': [{'ids': {'imdb': 'tt0944947'}}]}], requests)
		self.assertEqual([], notifications)

	def test_inactive_user_is_rejected_before_trakt_request(self):
		module, notifications, requests, _ = _load_trakt_actions_module(trakt_active=False)

		result = module.add_to_watchlist_item({
			'tmdb_id': '550',
			'media_type': 'movie',
		})

		self.assertIsNone(result)
		self.assertEqual([], requests)
		self.assertEqual([('No Active Trakt Account', 3500)], notifications)

	def test_invalid_route_parameters_are_rejected_before_trakt_request(self):
		module, notifications, requests, _ = _load_trakt_actions_module()

		result = module.add_to_watchlist_item({
			'tmdb_id': '../../invalid',
			'imdb_id': 'not-an-imdb-id',
			'tvdb_id': '-1',
			'media_type': 'tvshow',
		})

		self.assertIsNone(result)
		self.assertEqual([], requests)
		self.assertEqual([('Invalid media information', 3500)], notifications)

	def test_oversized_numeric_identifier_is_rejected_before_trakt_request(self):
		module, notifications, requests, _ = _load_trakt_actions_module()

		result = module.add_to_watchlist_item({
			'tmdb_id': '9' * 100,
			'media_type': 'movie',
		})

		self.assertIsNone(result)
		self.assertEqual([], requests)
		self.assertEqual([('Invalid media information', 3500)], notifications)


if __name__ == '__main__':
	unittest.main()
