import importlib.util
import sys
import types
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UTILS_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'modules' / 'utils.py'
SETTINGS_CACHE_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'caches' / 'settings_cache.py'

STUB_MODULE_KEYS = ('modules', 'modules.kodi_utils', 'modules.settings', 'caches', 'caches.base_cache')


def _install_stub_modules():
	properties = {}
	kodi_utils = types.ModuleType('modules.kodi_utils')
	kodi_utils.addon_fanart = lambda: ''
	kodi_utils.addon_info = lambda key: 'test-version' if key == 'version' else ''
	kodi_utils.clear_property = lambda key: properties.pop(key, None)
	kodi_utils.get_property = lambda key: properties.get(key, '')
	kodi_utils.is_android = lambda: False
	kodi_utils.logger = lambda *args, **kwargs: None
	kodi_utils.notification = lambda *args, **kwargs: None
	kodi_utils.path_exists = lambda path: False
	kodi_utils.schedule_widget_refresh = lambda **kwargs: None
	kodi_utils.set_property = lambda key, value: properties.__setitem__(key, value)
	kodi_utils.sleep = lambda *args, **kwargs: None
	kodi_utils.translate_path = lambda path: path

	modules = types.ModuleType('modules')
	modules.__path__ = []
	modules.kodi_utils = kodi_utils
	settings = types.ModuleType('modules.settings')
	settings.max_threads = lambda: 1
	settings.migrate_cm_manager_order_for_upgrade = lambda: False
	settings.migrate_external_scraper_context_menu_for_upgrade = lambda had_existing: False
	settings.migrate_external_scraper_run_mode_for_upgrade = lambda had_existing: False
	settings.migrate_external_scraper_slots_for_upgrade = lambda had_existing: False
	settings.migrate_mdblist_context_menu_for_upgrade = lambda had_existing: False
	settings.migrate_simkl_context_menu_for_upgrade = lambda had_existing: False
	settings.migrate_trakt_watchlist_context_menu_for_upgrade = lambda had_existing: False

	caches = types.ModuleType('caches')
	caches.__path__ = []
	base_cache = types.ModuleType('caches.base_cache')
	base_cache.connect_database = lambda name: None

	sys.modules['modules'] = modules
	sys.modules['modules.kodi_utils'] = kodi_utils
	sys.modules['modules.settings'] = settings
	sys.modules['caches'] = caches
	sys.modules['caches.base_cache'] = base_cache
	return properties


def _load_module(name, path):
	spec = importlib.util.spec_from_file_location(name, path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class FakeSettingsCache:
	def __init__(self, initial=None):
		self.data = dict(initial or {})
		self.rows = {}

	def clean_database(self):
		return True

	def clear_db_cache(self):
		pass

	def get_all(self):
		return dict(self.data)

	def remove_setting(self, setting_id):
		self.data.pop(setting_id, None)

	def set_many(self, settings_list, load_properties=True):
		for row in settings_list:
			self.rows[row[0]] = row
			self.data[row[0]] = row[3]

	def set_memory_cache(self, setting_id, value):
		pass

	def write_db(self, setting_id, setting_value, setting_info=None):
		self.data[setting_id] = setting_value


class StubModulesTestCase(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls._original_sys_modules = {}
		for key in STUB_MODULE_KEYS:
			if key in sys.modules:
				cls._original_sys_modules[key] = sys.modules[key]
		cls.properties = _install_stub_modules()

	@classmethod
	def tearDownClass(cls):
		for key in STUB_MODULE_KEYS:
			if key in cls._original_sys_modules:
				sys.modules[key] = cls._original_sys_modules[key]
			else:
				sys.modules.pop(key, None)


class MakeDayDateFormatTests(StubModulesTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.utils = _load_module('utils_under_test', UTILS_PATH)

	def setUp(self):
		self.today = date(2026, 7, 19)

	def test_words_mode_uses_relative_labels(self):
		make_day = self.utils.make_day
		self.assertEqual('YESTERDAY', make_day(self.today, date(2026, 7, 18)))
		self.assertEqual('TODAY', make_day(self.today, date(2026, 7, 19)))
		self.assertEqual('TOMORROW', make_day(self.today, date(2026, 7, 20)))
		self.assertEqual('TUESDAY', make_day(self.today, date(2026, 7, 21)))

	def test_date_mode_ignores_relative_labels(self):
		make_day = self.utils.make_day
		self.assertEqual('07/19/2026', make_day(self.today, date(2026, 7, 19), '%m/%d/%Y', use_words=False))
		self.assertEqual('20/07/2026', make_day(self.today, date(2026, 7, 20), '%d/%m/%Y', use_words=False))
		self.assertEqual('2026-07-21', make_day(self.today, date(2026, 7, 21), '%Y-%m-%d', use_words=False))

	def test_date_mode_formats_far_future_dates(self):
		self.assertEqual('08/01/2026', self.utils.make_day(self.today, date(2026, 8, 1), '%m/%d/%Y', use_words=False))


class CalendarDateLabelsSettingTests(StubModulesTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.module = _load_module('settings_cache_under_test_date_labels', SETTINGS_CACHE_PATH)

	def setUp(self):
		self.properties.clear()

	def _sync(self, initial):
		cache = FakeSettingsCache(initial)
		self.module.settings_cache = cache
		result = self.module.sync_settings({'silent': 'true', 'load_properties': 'false', 'force': 'true'})
		self.assertEqual('synced', result)
		return cache

	def test_default_setting_metadata(self):
		defaults = {s['setting_id']: s for s in self.module.default_settings()}
		setting = defaults.get('trakt.calendar_date_labels')
		self.assertIsNotNone(setting, 'trakt.calendar_date_labels missing from default settings')
		self.assertEqual('action', setting['setting_type'])
		self.assertEqual('0', setting['setting_default'])
		self.assertEqual({
			'0': 'Words / YYYY-MM-DD', '7': 'Words / MM-DD-YYYY', '8': 'Words / DD-MM-YYYY',
			'3': 'YYYY-MM-DD', '1': 'MM-DD-YYYY', '2': 'DD-MM-YYYY',
			'6': 'Day + YYYY-MM-DD', '4': 'Day + MM-DD-YYYY', '5': 'Day + DD-MM-YYYY'},
			setting['settings_options'])

	def test_fresh_install_defaults_to_words(self):
		cache = self._sync({})

		self.assertEqual('0', cache.data['trakt.calendar_date_labels'])
		self.assertEqual('Words / YYYY-MM-DD', cache.data['trakt.calendar_date_labels_name'])

	def test_upgrade_inserts_setting_without_touching_existing_preferences(self):
		cache = self._sync({
			'trakt.calendar_sort_order': '1',
			'trakt.calendar_future_days': '14',
		})

		self.assertEqual('0', cache.data['trakt.calendar_date_labels'])
		self.assertEqual('1', cache.data['trakt.calendar_sort_order'])
		self.assertEqual('14', cache.data['trakt.calendar_future_days'])

	def test_existing_date_labels_choice_is_not_overwritten(self):
		cache = self._sync({'trakt.calendar_date_labels': '2'})

		self.assertEqual('2', cache.data['trakt.calendar_date_labels'])


if __name__ == '__main__':
	unittest.main()
