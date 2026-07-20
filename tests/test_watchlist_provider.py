import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'plugin.video.redlight' / 'resources' / 'lib'
SETTINGS_PATH = LIB / 'modules' / 'settings.py'
WATCHLIST_PATH = LIB / 'modules' / 'watchlist.py'
CUSTOM_KEYS_PATH = LIB / 'modules' / 'custom_keys.py'

_STUB_KEYS = (
	'caches', 'caches.settings_cache', 'modules', 'modules.kodi_utils', 'modules.settings',
	'modules.watchlist', 'apis', 'apis.trakt_api', 'apis.simkl_api', 'apis.mdblist_api',
	'indexers', 'indexers.dialogs',
)


def _snapshot_modules():
	return {key: sys.modules[key] for key in _STUB_KEYS if key in sys.modules}


def _restore_modules(snapshot):
	for key in _STUB_KEYS:
		if key in snapshot:
			sys.modules[key] = snapshot[key]
		else:
			sys.modules.pop(key, None)


def _load_settings_module(store, db_values):
	def get_setting(setting_id, fallback=None):
		return store.get(setting_id.replace('redlight.', '', 1), fallback)

	def set_setting(setting_id, value):
		store[setting_id] = value

	settings_cache = types.ModuleType('caches.settings_cache')
	settings_cache.get_setting = get_setting
	settings_cache.set_setting = set_setting
	settings_cache.default_setting_values = lambda setting_id: {'setting_default': ''}
	settings_cache._EXTRAS_LIST_DEFAULT = ''
	settings_cache.settings_cache = types.SimpleNamespace(read_db_value=lambda key: db_values.get(key, 'empty_setting'))

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


def _active_db_values(*providers):
	values = {}
	if 'trakt' in providers:
		values['trakt.user'] = 'someuser'
	if 'simkl' in providers:
		values['simkl.user'] = 'someuser'
		values['simkl.token'] = 'sometoken'
	if 'mdblist' in providers:
		values['mdblist.user'] = 'someuser'
		values['mdblist.token'] = 'sometoken'
	return values


class ActiveWatchlistProviderTests(unittest.TestCase):
	def setUp(self):
		self._snapshot = _snapshot_modules()
		self.store = {}

	def tearDown(self):
		_restore_modules(self._snapshot)

	def _settings(self, *active_providers):
		return _load_settings_module(self.store, _active_db_values(*active_providers))

	def test_auto_prefers_trakt_when_all_active(self):
		settings = self._settings('trakt', 'simkl', 'mdblist')
		self.assertEqual('trakt', settings.active_watchlist_provider())

	def test_auto_returns_simkl_when_only_simkl_active(self):
		settings = self._settings('simkl')
		self.assertEqual('simkl', settings.active_watchlist_provider())

	def test_auto_returns_mdblist_when_only_mdblist_active(self):
		settings = self._settings('mdblist')
		self.assertEqual('mdblist', settings.active_watchlist_provider())

	def test_returns_none_when_no_provider_active(self):
		settings = self._settings()
		self.assertIsNone(settings.active_watchlist_provider())

	def test_explicit_provider_respected_when_active(self):
		self.store['watchlist.provider'] = 'simkl'
		settings = self._settings('trakt', 'simkl')
		self.assertEqual('simkl', settings.active_watchlist_provider())

	def test_explicit_provider_falls_back_when_inactive(self):
		self.store['watchlist.provider'] = 'simkl'
		settings = self._settings('trakt')
		self.assertEqual('trakt', settings.active_watchlist_provider())


class _RecordingModule(types.ModuleType):
	def __init__(self, name):
		super().__init__(name)
		self.calls = []

	def _record(self, func_name, result=True):
		def _func(*args, **kwargs):
			self.calls.append((func_name, args, kwargs))
			return result
		setattr(self, func_name, _func)
		return _func


def _load_watchlist_module(provider=None):
	settings = types.ModuleType('modules.settings')
	settings.active_watchlist_provider = lambda: provider

	kodi_utils = _RecordingModule('modules.kodi_utils')
	kodi_utils._record('notification', result=None)
	kodi_utils._record('kodi_refresh', result=None)

	modules = types.ModuleType('modules')
	modules.__path__ = []
	modules.settings = settings
	modules.kodi_utils = kodi_utils

	apis = types.ModuleType('apis')
	apis.__path__ = []
	trakt_api = _RecordingModule('apis.trakt_api')
	trakt_api._record('toggle_watchlist')
	trakt_api._record('trakt_watchlist_tmdb_ids', result={'101'})
	simkl_api = _RecordingModule('apis.simkl_api')
	simkl_api._record('simkl_add_to_list')
	simkl_api._record('simkl_remove_from_list')
	simkl_api._record('simkl_plantowatch_tmdb_ids', result={'202'})
	mdblist_api = _RecordingModule('apis.mdblist_api')
	mdblist_api._record('mdblist_add_to_watchlist')
	mdblist_api._record('mdblist_remove_from_watchlist')
	mdblist_api._record('mdblist_watchlist_tmdb_ids', result={'303'})

	sys.modules['modules'] = modules
	sys.modules['modules.settings'] = settings
	sys.modules['modules.kodi_utils'] = kodi_utils
	sys.modules['apis'] = apis
	sys.modules['apis.trakt_api'] = trakt_api
	sys.modules['apis.simkl_api'] = simkl_api
	sys.modules['apis.mdblist_api'] = mdblist_api

	spec = importlib.util.spec_from_file_location('watchlist_under_test', WATCHLIST_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module, {'trakt': trakt_api, 'simkl': simkl_api, 'mdblist': mdblist_api, 'kodi_utils': kodi_utils}


class ToggleWatchlistDispatchTests(unittest.TestCase):
	def setUp(self):
		self._snapshot = _snapshot_modules()

	def tearDown(self):
		_restore_modules(self._snapshot)

	def test_trakt_provider_delegates_to_trakt_api(self):
		watchlist, stubs = _load_watchlist_module()
		params = {'provider': 'trakt', 'action': 'add', 'tmdb_id': '5', 'media_type': 'movie'}
		watchlist.toggle_watchlist(params)
		self.assertEqual(1, len(stubs['trakt'].calls))
		name, args, kwargs = stubs['trakt'].calls[0]
		self.assertEqual('toggle_watchlist', name)
		self.assertEqual((params,), args)
		self.assertEqual([], stubs['simkl'].calls)
		self.assertEqual([], stubs['mdblist'].calls)

	def test_simkl_add_movie_targets_plantowatch(self):
		watchlist, stubs = _load_watchlist_module()
		params = {'provider': 'simkl', 'action': 'add', 'tmdb_id': '5', 'imdb_id': 'tt5', 'tvdb_id': 'None', 'media_type': 'movie'}
		watchlist.toggle_watchlist(params)
		self.assertEqual(1, len(stubs['simkl'].calls))
		name, args, kwargs = stubs['simkl'].calls[0]
		self.assertEqual('simkl_add_to_list', name)
		self.assertEqual(('plantowatch', '5', 'movie', 'tt5', 'None'), args)
		self.assertEqual([], stubs['trakt'].calls)
		self.assertEqual([], stubs['mdblist'].calls)

	def test_simkl_remove_tvshow_targets_plantowatch(self):
		watchlist, stubs = _load_watchlist_module()
		params = {'provider': 'simkl', 'action': 'remove', 'tmdb_id': '7', 'imdb_id': 'tt7', 'tvdb_id': '77', 'media_type': 'tvshow'}
		watchlist.toggle_watchlist(params)
		self.assertEqual(1, len(stubs['simkl'].calls))
		name, args, kwargs = stubs['simkl'].calls[0]
		self.assertEqual('simkl_remove_from_list', name)
		self.assertEqual(('plantowatch', '7', 'tvshow', 'tt7', '77'), args)
		self.assertEqual([], stubs['trakt'].calls)
		self.assertEqual([], stubs['mdblist'].calls)

	def test_mdblist_add_movie(self):
		watchlist, stubs = _load_watchlist_module()
		params = {'provider': 'mdblist', 'action': 'add', 'tmdb_id': '9', 'imdb_id': 'tt9', 'media_type': 'movie'}
		watchlist.toggle_watchlist(params)
		self.assertEqual(1, len(stubs['mdblist'].calls))
		name, args, kwargs = stubs['mdblist'].calls[0]
		self.assertEqual('mdblist_add_to_watchlist', name)
		self.assertEqual(('9', 'movie', 'tt9'), args)
		self.assertEqual([], stubs['trakt'].calls)
		self.assertEqual([], stubs['simkl'].calls)

	def test_mdblist_remove_tvshow(self):
		watchlist, stubs = _load_watchlist_module()
		params = {'provider': 'mdblist', 'action': 'remove', 'tmdb_id': '9', 'imdb_id': 'tt9', 'media_type': 'tvshow'}
		watchlist.toggle_watchlist(params)
		self.assertEqual(1, len(stubs['mdblist'].calls))
		name, args, kwargs = stubs['mdblist'].calls[0]
		self.assertEqual('mdblist_remove_from_watchlist', name)
		self.assertEqual(('9', 'tvshow', 'tt9'), args)
		self.assertEqual([], stubs['trakt'].calls)
		self.assertEqual([], stubs['simkl'].calls)

	def test_missing_provider_resolves_from_settings(self):
		watchlist, stubs = _load_watchlist_module(provider='simkl')
		params = {'action': 'add', 'tmdb_id': '5', 'imdb_id': 'None', 'tvdb_id': 'None', 'media_type': 'movie'}
		watchlist.toggle_watchlist(params)
		self.assertEqual(1, len(stubs['simkl'].calls))
		self.assertEqual('simkl_add_to_list', stubs['simkl'].calls[0][0])
		self.assertEqual([], stubs['trakt'].calls)
		self.assertEqual([], stubs['mdblist'].calls)

	def test_no_active_provider_notifies_without_api_calls(self):
		watchlist, stubs = _load_watchlist_module(provider=None)
		watchlist.toggle_watchlist({'action': 'add', 'tmdb_id': '5', 'media_type': 'movie'})
		self.assertEqual([], stubs['trakt'].calls)
		self.assertEqual([], stubs['simkl'].calls)
		self.assertEqual([], stubs['mdblist'].calls)
		self.assertEqual('notification', stubs['kodi_utils'].calls[0][0])


def _load_custom_keys_module(watchlist_url):
	kodi_utils = _RecordingModule('modules.kodi_utils')
	kodi_utils.get_infolabel = lambda label: watchlist_url
	kodi_utils._record('activate_window', result=None)
	kodi_utils._record('container_update', result=None)
	kodi_utils._record('hide_busy_dialog', result=None)

	watchlist = _RecordingModule('modules.watchlist')
	watchlist._record('toggle_watchlist')

	trakt_api = _RecordingModule('apis.trakt_api')
	trakt_api._record('toggle_watchlist')

	modules = types.ModuleType('modules')
	modules.__path__ = []
	modules.kodi_utils = kodi_utils
	modules.watchlist = watchlist

	apis = types.ModuleType('apis')
	apis.__path__ = []

	indexers = types.ModuleType('indexers')
	indexers.__path__ = []
	dialogs = types.ModuleType('indexers.dialogs')
	indexers.dialogs = dialogs

	sys.modules['modules'] = modules
	sys.modules['modules.kodi_utils'] = kodi_utils
	sys.modules['modules.watchlist'] = watchlist
	sys.modules['apis'] = apis
	sys.modules['apis.trakt_api'] = trakt_api
	sys.modules['indexers'] = indexers
	sys.modules['indexers.dialogs'] = dialogs

	spec = importlib.util.spec_from_file_location('custom_keys_under_test', CUSTOM_KEYS_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module, {'watchlist': watchlist, 'trakt': trakt_api}


class CustomKeyWatchlistTests(unittest.TestCase):
	def setUp(self):
		self._snapshot = _snapshot_modules()

	def tearDown(self):
		_restore_modules(self._snapshot)

	def test_custom_key_routes_through_provider_dispatcher(self):
		url = ('plugin://plugin.video.redlight/?mode=watchlist.toggle_watchlist&provider=simkl&action=add'
			'&tmdb_id=5&imdb_id=tt5&tvdb_id=None&media_type=movie')
		custom_keys, stubs = _load_custom_keys_module(url)
		custom_keys.trakt_watchlist()
		self.assertEqual([], stubs['trakt'].calls)
		self.assertEqual(1, len(stubs['watchlist'].calls))
		name, args, kwargs = stubs['watchlist'].calls[0]
		self.assertEqual('toggle_watchlist', name)
		self.assertEqual('simkl', args[0]['provider'])
		self.assertEqual('5', args[0]['tmdb_id'])

	def test_custom_key_no_params_is_noop(self):
		custom_keys, stubs = _load_custom_keys_module('')
		custom_keys.trakt_watchlist()
		self.assertEqual([], stubs['watchlist'].calls)
		self.assertEqual([], stubs['trakt'].calls)


class WatchlistTmdbIdsTests(unittest.TestCase):
	def setUp(self):
		self._snapshot = _snapshot_modules()

	def tearDown(self):
		_restore_modules(self._snapshot)

	def test_trakt_ids(self):
		watchlist, stubs = _load_watchlist_module()
		self.assertEqual({'101'}, watchlist.watchlist_tmdb_ids('trakt', 'movie'))
		self.assertEqual(('trakt_watchlist_tmdb_ids', ('movie',), {}), stubs['trakt'].calls[0])

	def test_simkl_ids(self):
		watchlist, stubs = _load_watchlist_module()
		self.assertEqual({'202'}, watchlist.watchlist_tmdb_ids('simkl', 'tvshow'))
		self.assertEqual(('simkl_plantowatch_tmdb_ids', ('tvshow',), {}), stubs['simkl'].calls[0])

	def test_mdblist_ids(self):
		watchlist, stubs = _load_watchlist_module()
		self.assertEqual({'303'}, watchlist.watchlist_tmdb_ids('mdblist', 'movie'))
		self.assertEqual(('mdblist_watchlist_tmdb_ids', ('movie',), {}), stubs['mdblist'].calls[0])

	def test_unknown_provider_returns_empty_set(self):
		watchlist, stubs = _load_watchlist_module()
		self.assertEqual(set(), watchlist.watchlist_tmdb_ids(None, 'movie'))


if __name__ == '__main__':
	unittest.main()
