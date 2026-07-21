import sys
import unittest

from test_trakt_sync_list_sort import list_sort, _install_stubs, OVERRIDES, SETTINGS


_STUBBED_MODULES = ('caches', 'caches.list_sort_cache', 'caches.settings_cache', 'modules', 'modules.settings')

# Every fixture below is three rows deliberately laid out so that the input order is not equal to any
# of the orders the tests assert. A two-row fixture cannot do that - one of the two possible orders
# always coincides with the input - so an implementation that ignored the spec and returned the rows
# untouched would pass. Ratings and date_added are likewise out of title order, so title:asc and the
# spec under test never produce the same sequence.
TRAKT_LIST_ROWS = [
	{'type': 'movie', 'rank': 2, 'listed_at': '2024-01-01', 'movie': {'title': 'Banana', 'released': '2001-01-01', 'rating': 5.0, 'votes': 10, 'runtime': 100}},
	{'type': 'show', 'rank': 1, 'listed_at': '2024-02-01', 'show': {'title': 'Alpha', 'first_aired': '1999-01-01', 'rating': 9.0, 'votes': 20, 'runtime': 40}},
	{'type': 'movie', 'rank': 3, 'listed_at': '2024-03-01', 'movie': {'title': 'Cherry', 'released': '2010-01-01', 'rating': 7.0, 'votes': 30, 'runtime': 120}},
]

PERSONAL_ROWS = [
	{'title': 'Banana', 'date_added': '200', 'release_date': '2001-01-01'},
	{'title': 'Alpha', 'date_added': '100', 'release_date': '1999-01-01'},
	{'title': 'Cherry', 'date_added': '150', 'release_date': '2010-01-01'},
]

TMDB_ROWS = [
	{'title': 'Banana', 'release_date': '2001-01-01', 'original_order': 0},
	{'title': 'Cherry', 'release_date': '2010-01-01', 'original_order': 1},
	{'title': 'Alpha', 'release_date': '1999-01-01', 'original_order': 2},
]


class MixedListResolutionTests(unittest.TestCase):
	def setUp(self):
		# Other test modules install their own fake 'caches'/'modules' stubs into sys.modules at
		# import time, and resolve()/sort_source() re-read sys.modules lazily on every call, so
		# collection order could otherwise decide which stubs these tests see. Same idiom as
		# tests/test_list_sort_resolve.py and tests/test_trakt_sync_list_sort.py.
		self._original_sys_modules = {}
		for key in _STUBBED_MODULES:
			if key in sys.modules:
				self._original_sys_modules[key] = sys.modules[key]
		_install_stubs()
		OVERRIDES.clear()
		SETTINGS.clear()

	def tearDown(self):
		for key in _STUBBED_MODULES:
			if key in self._original_sys_modules:
				sys.modules[key] = self._original_sys_modules[key]
			else:
				sys.modules.pop(key, None)
		OVERRIDES.clear()
		SETTINGS.clear()

	def _titles(self, rows):
		return [i[i['type']]['title'] for i in rows]

	def test_no_override_uses_default_spec(self):
		# rating:asc would order Banana, Cherry, Alpha. A mixed list must ignore the mediatype
		# default and land on DEFAULT_SPEC (title:asc) instead.
		SETTINGS['redlight.sort.default.movies'] = 'rating:asc'
		SETTINGS['redlight.sort.default.shows'] = 'rating:asc'
		result = list_sort.sort_source(list(TRAKT_LIST_ROWS), 'trakt.list:99', None, 'trakt_list')
		self.assertEqual(['Alpha', 'Banana', 'Cherry'], self._titles(result))

	def test_override_drives_trakt_list(self):
		OVERRIDES['trakt.list:99'] = 'rank:desc'
		result = list_sort.sort_source(list(TRAKT_LIST_ROWS), 'trakt.list:99', None, 'trakt_list')
		self.assertEqual([3, 2, 1], [i['rank'] for i in result])

	def test_override_is_scoped_to_its_own_list(self):
		OVERRIDES['trakt.list:99'] = 'rank:desc'
		result = list_sort.sort_source(list(TRAKT_LIST_ROWS), 'trakt.list:100', None, 'trakt_list')
		self.assertEqual(['Alpha', 'Banana', 'Cherry'], self._titles(result))

	def test_personal_list_override(self):
		OVERRIDES['personal:Faves|jo'] = 'date_added:desc'
		result = list_sort.sort_source(list(PERSONAL_ROWS), 'personal:Faves|jo', None, 'personal')
		self.assertEqual(['Banana', 'Cherry', 'Alpha'], [i['title'] for i in result])

	def test_personal_list_without_override_sorts_by_title(self):
		result = list_sort.sort_source(list(PERSONAL_ROWS), 'personal:Faves|jo', None, 'personal')
		self.assertEqual(['Alpha', 'Banana', 'Cherry'], [i['title'] for i in result])

	def test_tmdb_default_field_keeps_provider_order(self):
		OVERRIDES['tmdb:watchlist'] = 'default:asc'
		result = list_sort.sort_source(list(TMDB_ROWS), 'tmdb:watchlist', None, 'tmdb')
		self.assertEqual(['Banana', 'Cherry', 'Alpha'], [i['title'] for i in result])

	def test_tmdb_release_date_override(self):
		OVERRIDES['tmdb:8675309'] = 'release_date:desc'
		result = list_sort.sort_source(list(TMDB_ROWS), 'tmdb:8675309', None, 'tmdb')
		self.assertEqual(['Cherry', 'Banana', 'Alpha'], [i['title'] for i in result])


class LegacyStoreMigrationTests(unittest.TestCase):
	def test_trakt_rows_translate(self):
		result = list_sort.migrate_legacy_stores(
			trakt_rows={'12345': {'sort_by': 'added', 'sort_how': 'desc'}}, personal_rows={}, tmdb_rows={})
		self.assertEqual('date_added:desc', result['trakt.list:12345'])

	def test_trakt_sort_how_is_honoured(self):
		result = list_sort.migrate_legacy_stores(
			trakt_rows={'12345': {'sort_by': 'added', 'sort_how': 'asc'}}, personal_rows={}, tmdb_rows={})
		self.assertEqual('date_added:asc', result['trakt.list:12345'])

	def test_personal_rows_translate(self):
		result = list_sort.migrate_legacy_stores(
			trakt_rows={}, personal_rows={('Faves', 'jo'): '2'}, tmdb_rows={})
		self.assertEqual('date_added:desc', result['personal:Faves|jo'])

	def test_personal_code_one_is_ascending(self):
		result = list_sort.migrate_legacy_stores(
			trakt_rows={}, personal_rows={('Faves', 'jo'): '1'}, tmdb_rows={})
		self.assertEqual('date_added:asc', result['personal:Faves|jo'])

	def test_tmdb_rows_translate(self):
		result = list_sort.migrate_legacy_stores(trakt_rows={}, personal_rows={}, tmdb_rows={8675309: '2'})
		self.assertEqual('release_date:desc', result['tmdb:8675309'])

	def test_tmdb_code_one_is_ascending(self):
		result = list_sort.migrate_legacy_stores(trakt_rows={}, personal_rows={}, tmdb_rows={8675309: '1'})
		self.assertEqual('release_date:asc', result['tmdb:8675309'])

	def test_unmappable_rows_are_skipped(self):
		result = list_sort.migrate_legacy_stores(
			trakt_rows={'1': {'sort_by': 'nonsense', 'sort_how': 'asc'}}, personal_rows={('X', 'y'): '99'}, tmdb_rows={1: '99'})
		self.assertEqual({}, result)

	def test_null_personal_sort_order_becomes_provider_default(self):
		result = list_sort.migrate_legacy_stores(trakt_rows={}, personal_rows={('Faves', 'jo'): None}, tmdb_rows={})
		self.assertEqual('default:asc', result['personal:Faves|jo'])

	def test_all_three_stores_migrate_together(self):
		result = list_sort.migrate_legacy_stores(
			trakt_rows={'12345': {'sort_by': 'title', 'sort_how': 'asc'}},
			personal_rows={('Faves', 'jo'): '5'}, tmdb_rows={8675309: '4'})
		self.assertEqual({'trakt.list:12345': 'title:asc', 'personal:Faves|jo': 'random:asc',
			'tmdb:8675309': 'default:asc'}, result)

	def test_empty_stores_translate_to_nothing(self):
		self.assertEqual({}, list_sort.migrate_legacy_stores(None, None, None))


if __name__ == '__main__':
	unittest.main()
