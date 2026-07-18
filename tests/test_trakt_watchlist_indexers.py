import importlib.util
import sys
import types
import unittest
from pathlib import Path
from urllib.parse import urlencode


ROOT = Path(__file__).resolve().parents[1]
LIB_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib'


class FakeVideoInfoTag:
	def __getattr__(self, name):
		return lambda *args, **kwargs: None


class FakeListItem:
	def __init__(self):
		self.context_menu = []

	def addContextMenuItems(self, items):
		self.context_menu = items

	def getVideoInfoTag(self, create=False):
		return FakeVideoInfoTag()

	def setArt(self, art):
		pass

	def setLabel(self, label):
		pass

	def setProperties(self, properties):
		pass


def _load_module(name, path):
	spec = importlib.util.spec_from_file_location(name, path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def _movie_meta():
	return {
		'tmdb_id': 550,
		'imdb_id': 'tt0137523',
		'title': 'Fight Club',
		'year': 1999,
		'premiered': '1999-10-15',
		'duration': 8340,
		'extra_info': {},
		'poster': 'movie-poster',
		'fanart': 'movie-fanart',
		'genre': [],
		'country': [],
		'short_cast': [],
	}


def _tvshow_meta():
	return {
		'tmdb_id': 1399,
		'imdb_id': 'tt0944947',
		'tvdb_id': 121361,
		'title': 'Game of Thrones',
		'year': 2011,
		'premiered': '2011-04-17',
		'total_seasons': 8,
		'total_aired_eps': 73,
		'poster': 'show-poster',
		'fanart': 'show-fanart',
		'genre': [],
		'country': [],
		'short_cast': [],
	}


class TraktWatchlistIndexerTests(unittest.TestCase):
	def setUp(self):
		self.module_keys = (
			'modules', 'modules.kodi_utils', 'modules.metadata', 'modules.settings',
			'modules.trakt_actions', 'modules.utils', 'modules.watched_status',
		)
		self.original_modules = {
			key: sys.modules[key] for key in self.module_keys if key in sys.modules
		}
		self._install_dependencies()

	def tearDown(self):
		for key in self.module_keys:
			if key in self.original_modules:
				sys.modules[key] = self.original_modules[key]
			else:
				sys.modules.pop(key, None)

	def _install_dependencies(self):
		kodi_utils = types.ModuleType('modules.kodi_utils')
		kodi_utils.external = lambda: False
		settings = types.ModuleType('modules.settings')
		settings.append_external_scraper_settings_cm = lambda append, build_url: None
		settings.mdblist_user_active = lambda: False
		settings.playback_key = lambda: 'media'
		settings.simkl_user_active = lambda: False
		settings.tmdb_api_key = lambda: ''
		settings.trakt_user_active = lambda: True
		metadata = types.ModuleType('modules.metadata')
		metadata.movie_meta = lambda *args: _movie_meta()
		metadata.movieset_meta = lambda *args: {}
		metadata.tvshow_meta = lambda *args: _tvshow_meta()
		watched_status = types.ModuleType('modules.watched_status')
		watched_status.get_progress_status_movie = lambda bookmarks, tmdb_id: 0
		watched_status.get_watched_status_movie = lambda watched_info, tmdb_id: 0
		watched_status.get_watched_status_tvshow = lambda watched_info, total: (0, 0, total)
		watched_status.get_resume_seconds = lambda progress, duration: 0
		utils = types.ModuleType('modules.utils')
		utils.TaskPool = object
		utils.get_current_timestamp = lambda: 1
		utils.get_datetime = lambda: 2
		utils.jsondate_to_datetime = lambda *args: 1
		utils.manual_function_import = lambda *args: None
		utils.paginate_list = lambda *args: args[0]

		modules = types.ModuleType('modules')
		modules.__path__ = [str(LIB_PATH / 'modules')]
		modules.kodi_utils = kodi_utils
		modules.settings = settings
		modules.watched_status = watched_status
		sys.modules.update({
			'modules': modules,
			'modules.kodi_utils': kodi_utils,
			'modules.metadata': metadata,
			'modules.settings': settings,
			'modules.utils': utils,
			'modules.watched_status': watched_status,
		})
		trakt_actions = _load_module('modules.trakt_actions', LIB_PATH / 'modules' / 'trakt_actions.py')
		modules.trakt_actions = trakt_actions
		sys.modules['modules.trakt_actions'] = trakt_actions

	def _configure_indexer(self, indexer):
		indexer.ai_model_active = False
		indexer.build_url = lambda params: 'plugin://plugin.video.redlight/?%s' % urlencode(params)
		indexer.current_date = 2
		indexer.current_time = 1
		indexer.custom_cm_menu = False
		indexer.fanart_empty = ''
		indexer.kodi_actor = lambda **kwargs: kwargs
		indexer.make_listitem = FakeListItem
		indexer.mpaa_region = 'US'
		indexer.poster_empty = ''
		indexer.rpdb_api_key = None
		indexer.rpdb_format = ''
		indexer.tmdb_api_key = ''
		indexer.window_command = 'Container.Update(%s)'
		indexer.widget_hide_watched = False

	def _watchlist_action(self, indexer):
		listitem = indexer.items[0][0][1]
		actions = [action for label, action in listitem.context_menu if label == '[B]Add to Watchlist[/B]']
		self.assertEqual(1, len(actions))
		return actions[0]

	def test_movie_builder_attaches_direct_watchlist_action(self):
		movies = _load_module('movies_under_test', LIB_PATH / 'indexers' / 'movies.py')
		indexer = movies.Movies({})
		self._configure_indexer(indexer)
		indexer.bookmarks = {}
		indexer.open_extras = False
		indexer.open_movieset = False
		indexer.watched_info = {}

		indexer.build_movie_content(0, 550)

		action = self._watchlist_action(indexer)
		self.assertIn('mode=trakt.add_to_watchlist_item', action)
		self.assertIn('media_type=movie', action)
		self.assertIn('tmdb_id=550', action)

	def test_tvshow_builder_attaches_direct_watchlist_action(self):
		tvshows = _load_module('tvshows_under_test', LIB_PATH / 'indexers' / 'tvshows.py')
		indexer = tvshows.TVShows({})
		self._configure_indexer(indexer)
		indexer.all_episodes = 0
		indexer.is_folder = True
		indexer.open_extras = False
		indexer.watched_info = {}

		indexer.build_tvshow_content(0, 1399)

		action = self._watchlist_action(indexer)
		self.assertIn('mode=trakt.add_to_watchlist_item', action)
		self.assertIn('media_type=tvshow', action)
		self.assertIn('tmdb_id=1399', action)
		self.assertIn('tvdb_id=121361', action)


if __name__ == '__main__':
	unittest.main()
