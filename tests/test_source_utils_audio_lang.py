import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_UTILS_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'modules' / 'source_utils.py'


def _load_source_utils_module():
	caches = types.ModuleType('caches')
	caches.__path__ = []

	settings_cache = types.ModuleType('caches.settings_cache')
	settings_cache.get_setting = lambda setting_id, fallback=None: fallback

	modules = types.ModuleType('modules')
	modules.__path__ = []

	metadata = types.ModuleType('modules.metadata')
	metadata.episodes_meta = lambda *args, **kwargs: []

	settings = types.ModuleType('modules.settings')
	settings.date_offset = lambda: 0

	kodi_utils = types.ModuleType('modules.kodi_utils')
	kodi_utils.supported_media = lambda: ''
	kodi_utils.get_property = lambda key: ''
	kodi_utils.set_property = lambda key, value: None
	kodi_utils.notification = lambda *args, **kwargs: None

	utils = types.ModuleType('modules.utils')
	utils.adjust_premiered_date = lambda *args, **kwargs: (None, None)
	utils.get_datetime = lambda: None
	utils.jsondate_to_datetime = lambda *args, **kwargs: None
	utils.subtract_dates = lambda *args, **kwargs: 0
	utils.chunks = lambda lst, n: []

	requests_stub = sys.modules.get('requests') or types.ModuleType('requests')

	sys.modules['caches'] = caches
	sys.modules['caches.settings_cache'] = settings_cache
	sys.modules['modules'] = modules
	sys.modules['modules.metadata'] = metadata
	sys.modules['modules.settings'] = settings
	sys.modules['modules.kodi_utils'] = kodi_utils
	sys.modules['modules.utils'] = utils
	sys.modules['requests'] = requests_stub

	spec = importlib.util.spec_from_file_location('source_utils_under_test', SOURCE_UTILS_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


source_utils = _load_source_utils_module()

# Alphabetical by display name, matching audio_lang_choices().
EXPECTED_LANGS = (
	('ENGLISH AUDIO', 'ENG'), ('FRENCH AUDIO', 'FRE'), ('GERMAN AUDIO', 'GER'), ('HINDI AUDIO', 'HIN'),
	('ITALIAN AUDIO', 'ITA'), ('JAPANESE AUDIO', 'JPN'), ('KOREAN AUDIO', 'KOR'), ('PORTUGUESE AUDIO', 'POR'),
	('RUSSIAN AUDIO', 'RUS'), ('SPANISH AUDIO', 'SPA'))


def _info_tags(release_title):
	title = source_utils.release_info_format(release_title)
	info = source_utils.get_info(title)
	return info.split(' | ') if info else []


class TestAudioLangDetection(unittest.TestCase):

	def test_eng_tagged(self):
		self.assertIn('ENG', _info_tags('Some.Movie.2023.1080p.ENG.WEB-DL.x264'))

	def test_english_word_tagged(self):
		self.assertIn('ENG', _info_tags('Some.Movie.2023.English.1080p.BluRay'))

	def test_eng_subs_not_tagged(self):
		self.assertNotIn('ENG', _info_tags('Some.Movie.2023.1080p.WEB.Eng.Subs.x264'))

	def test_subs_eng_not_tagged(self):
		self.assertNotIn('ENG', _info_tags('Some.Movie.2023.1080p.WEB.Subs.Eng.x264'))

	def test_engsub_not_tagged(self):
		self.assertNotIn('ENG', _info_tags('Some.Movie.2023.1080p.WEB.EngSub.x264'))

	def test_swesub_not_swedish_false_positive(self):
		tags = _info_tags('Some.Movie.2023.1080p.SweSub.x264')
		self.assertNotIn('ENG', tags)
		self.assertIn('SUBS', tags)

	def test_subita_not_italian(self):
		self.assertNotIn('ITA', _info_tags('Some.Movie.2023.1080p.SubITA.x264'))

	def test_dual_audio_pair_tags_both_and_multi(self):
		tags = _info_tags('Some.Movie.2023.1080p.ITA.ENG.BluRay.x264')
		self.assertIn('ITA', tags)
		self.assertIn('ENG', tags)
		self.assertIn('MULTI-LANG', tags)

	def test_each_language_positive_pattern(self):
		samples = {
			'ENG': 'Movie.2023.1080p.ENG.WEB', 'SPA': 'Movie.2023.1080p.Spanish.WEB', 'FRE': 'Movie.2023.1080p.TRUEFRENCH.WEB',
			'GER': 'Movie.2023.1080p.German.WEB', 'ITA': 'Movie.2023.1080p.iTA.WEB', 'POR': 'Movie.2023.1080p.Dublado.WEB',
			'HIN': 'Movie.2023.1080p.Hindi.WEB', 'JPN': 'Movie.2023.1080p.JPN.WEB', 'KOR': 'Movie.2023.1080p.Korean.WEB',
			'RUS': 'Movie.2023.1080p.RUS.WEB'}
		for tag, title in samples.items():
			with self.subTest(tag=tag):
				self.assertIn(tag, _info_tags(title))

	def test_plain_title_no_language_tags(self):
		tags = _info_tags('Some.Movie.2023.1080p.BluRay.x264-GROUP')
		for _, tag in EXPECTED_LANGS:
			self.assertNotIn(tag, tags)


class TestSourceFilters(unittest.TestCase):

	def test_source_filters_contains_all_language_entries(self):
		filters = source_utils.source_filters()
		for name, tag in EXPECTED_LANGS:
			self.assertIn((name, tag), filters)

	def test_audio_lang_choices_shape(self):
		choices = source_utils.audio_lang_choices()
		self.assertEqual(tuple((name, tag) for name, tag, _ in choices), EXPECTED_LANGS)
		for _, _, patterns in choices:
			self.assertTrue(patterns)
			for pattern in patterns:
				self.assertTrue(pattern.startswith('.') and pattern.endswith('.'))


if __name__ == '__main__':
	unittest.main()
