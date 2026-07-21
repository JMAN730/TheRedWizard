import ast
import sys
import unittest

from test_trakt_sync_list_sort import ROOT, list_sort, _install_stubs, OVERRIDES, SETTINGS


_STUBBED_MODULES = ('caches', 'caches.list_sort_cache', 'caches.settings_cache', 'modules', 'modules.settings')

TRAKT_API = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'apis' / 'trakt_api.py'
TMDB_LISTS = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'indexers' / 'tmdb_lists.py'

# Every fixture below is laid out so that the input order is not equal to any of the orders the tests
# assert. A two-row fixture cannot do that - one of the two possible orders always coincides with the
# input - so an implementation that ignored the spec and returned the rows untouched would pass.
# Ranks, ratings and date_added are likewise out of title order, so title:asc and the spec under test
# never produce the same sequence.
TRAKT_LIST_ROWS = [
	{'type': 'movie', 'rank': 2, 'listed_at': '2024-01-01', 'movie': {'title': 'Banana', 'released': '2001-01-01', 'rating': 5.0, 'votes': 10, 'runtime': 100}},
	{'type': 'show', 'rank': 3, 'listed_at': '2024-02-01', 'show': {'title': 'Alpha', 'first_aired': '1999-01-01', 'rating': 9.0, 'votes': 20, 'runtime': 40}},
	{'type': 'movie', 'rank': 1, 'listed_at': '2024-03-01', 'movie': {'title': 'Cherry', 'released': '2010-01-01', 'rating': 7.0, 'votes': 30, 'runtime': 120}},
]

TRAKT_PAYLOAD_ORDER = ['Banana', 'Alpha', 'Cherry']
TRAKT_TITLE_ASC = ['Alpha', 'Banana', 'Cherry']
TRAKT_RANK_ASC = ['Cherry', 'Banana', 'Alpha']

# Damson carries a date_added shorter than the others on purpose: '90' sorts last numerically but
# first descending as a string, so an extractor that dropped the int() coercion is caught here.
PERSONAL_ROWS = [
	{'title': 'Banana', 'date_added': '200', 'release_date': '2001-01-01'},
	{'title': 'Alpha', 'date_added': '100', 'release_date': '1999-01-01'},
	{'title': 'Cherry', 'date_added': '150', 'release_date': '2010-01-01'},
	{'title': 'Damson', 'date_added': '90', 'release_date': '2005-01-01'},
]

# Damson has no release date, so release_date sorts pin the MISSING_DATE sentinel: without it the
# comparison of None against a string raises and apply() hands back the payload order unsorted.
TMDB_ROWS = [
	{'title': 'Banana', 'release_date': '2001-01-01', 'original_order': 0},
	{'title': 'Cherry', 'release_date': '2010-01-01', 'original_order': 1},
	{'title': 'Alpha', 'release_date': '1999-01-01', 'original_order': 2},
	{'title': 'Damson', 'release_date': None, 'original_order': 3},
]

TMDB_PROVIDER_ORDER = ['Banana', 'Cherry', 'Alpha', 'Damson']
TMDB_TITLE_ASC = ['Alpha', 'Banana', 'Cherry', 'Damson']
TMDB_RELEASE_DESC = ['Damson', 'Cherry', 'Banana', 'Alpha']


class _StubbedTestCase(unittest.TestCase):
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


class MixedListResolutionTests(_StubbedTestCase):
	def _titles(self, rows):
		return [i[i['type']]['title'] for i in rows]

	def test_no_override_uses_default_spec(self):
		# rating:asc would order Banana, Cherry, Alpha. A mixed list must ignore the mediatype
		# default and land on DEFAULT_SPEC (title:asc) instead.
		SETTINGS['redlight.sort.default.movies'] = 'rating:asc'
		SETTINGS['redlight.sort.default.shows'] = 'rating:asc'
		result = list_sort.sort_source(list(TRAKT_LIST_ROWS), 'trakt.list:99', None, 'trakt_list')
		self.assertEqual(TRAKT_TITLE_ASC, self._titles(result))

	def test_override_drives_trakt_list(self):
		OVERRIDES['trakt.list:99'] = 'rank:desc'
		result = list_sort.sort_source(list(TRAKT_LIST_ROWS), 'trakt.list:99', None, 'trakt_list')
		self.assertEqual([3, 2, 1], [i['rank'] for i in result])

	def test_override_is_scoped_to_its_own_list(self):
		OVERRIDES['trakt.list:99'] = 'rank:desc'
		result = list_sort.sort_source(list(TRAKT_LIST_ROWS), 'trakt.list:100', None, 'trakt_list')
		self.assertEqual(TRAKT_TITLE_ASC, self._titles(result))

	def test_trakt_list_without_override_keeps_the_payload_sort(self):
		# The Trakt API declares the list's own ordering, and the folder URL carries it. A user who
		# never opened "Set Custom Sort" has no override row and nothing to migrate, so the payload
		# sort - not DEFAULT_SPEC - is the ordering that must survive the upgrade.
		fallback = list_sort.trakt_list_fallback('rank', 'asc')
		self.assertEqual('rank:asc', fallback)
		result = list_sort.sort_source(list(TRAKT_LIST_ROWS), 'trakt.list:99', None, 'trakt_list', fallback=fallback)
		self.assertEqual([1, 2, 3], [i['rank'] for i in result])
		self.assertEqual(TRAKT_RANK_ASC, self._titles(result))

	def test_trakt_payload_sort_direction_is_honoured(self):
		result = list_sort.sort_source(list(TRAKT_LIST_ROWS), 'trakt.list:99', None, 'trakt_list',
			fallback=list_sort.trakt_list_fallback('rank', 'desc'))
		self.assertEqual([3, 2, 1], [i['rank'] for i in result])

	def test_stored_override_beats_the_payload_sort(self):
		OVERRIDES['trakt.list:99'] = 'title:asc'
		result = list_sort.sort_source(list(TRAKT_LIST_ROWS), 'trakt.list:99', None, 'trakt_list',
			fallback=list_sort.trakt_list_fallback('rank', 'asc'))
		self.assertEqual(TRAKT_TITLE_ASC, self._titles(result))

	def test_unmappable_payload_sort_leaves_the_order_untouched(self):
		# 'my_rating', 'watched' and 'collected' have no canonical field. The old code left such a
		# payload alone rather than retitling it, so they must resolve to the provider order.
		for sort_by in ('my_rating', 'watched', 'collected'):
			fallback = list_sort.trakt_list_fallback(sort_by, 'desc')
			self.assertEqual('default:asc', fallback, sort_by)
			result = list_sort.sort_source(list(TRAKT_LIST_ROWS), 'trakt.list:99', None, 'trakt_list', fallback=fallback)
			self.assertEqual(TRAKT_PAYLOAD_ORDER, self._titles(result), sort_by)

	def test_personal_list_override(self):
		OVERRIDES['personal:Faves|jo'] = 'date_added:desc'
		result = list_sort.sort_source(list(PERSONAL_ROWS), 'personal:Faves|jo', None, 'personal')
		self.assertEqual(['Banana', 'Cherry', 'Alpha', 'Damson'], [i['title'] for i in result])

	def test_personal_list_without_override_sorts_by_title(self):
		result = list_sort.sort_source(list(PERSONAL_ROWS), 'personal:Faves|jo', None, 'personal')
		self.assertEqual(['Alpha', 'Banana', 'Cherry', 'Damson'], [i['title'] for i in result])

	def test_tmdb_default_field_keeps_provider_order(self):
		OVERRIDES['tmdb:watchlist'] = 'default:asc'
		result = list_sort.sort_source(list(TMDB_ROWS), 'tmdb:watchlist', None, 'tmdb')
		self.assertEqual(TMDB_PROVIDER_ORDER, [i['title'] for i in result])

	def test_tmdb_release_date_override(self):
		OVERRIDES['tmdb:8675309'] = 'release_date:desc'
		result = list_sort.sort_source(list(TMDB_ROWS), 'tmdb:8675309', None, 'tmdb')
		self.assertEqual(TMDB_RELEASE_DESC, [i['title'] for i in result])

	def test_tmdb_list_without_override_keeps_provider_order(self):
		# A TMDb user list nobody ever sorted has no store row and no override row. Its ordering is
		# TMDb's own, and DEFAULT_SPEC would silently retitle it on upgrade.
		result = list_sort.sort_source(list(TMDB_ROWS), 'tmdb:8675309', None, 'tmdb', fallback='default:asc')
		self.assertEqual(TMDB_PROVIDER_ORDER, [i['title'] for i in result])

	def test_tmdb_stored_override_beats_the_provider_order_fallback(self):
		OVERRIDES['tmdb:8675309'] = 'title:asc'
		result = list_sort.sort_source(list(TMDB_ROWS), 'tmdb:8675309', None, 'tmdb', fallback='default:asc')
		self.assertEqual(TMDB_TITLE_ASC, [i['title'] for i in result])


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

	def test_tmdb_non_string_sort_order_still_translates(self):
		# get_sort_orders() hands back whatever the row holds; an int must not fall through the table.
		result = list_sort.migrate_legacy_stores(trakt_rows={}, personal_rows={}, tmdb_rows={8675309: 2})
		self.assertEqual('release_date:desc', result['tmdb:8675309'])

	def test_tmdb_explicit_provider_default_choice_is_preserved(self):
		# sort_order_tmdb_list() stores the literal string 'None' for "Default From TMDb (None)".
		# Dropping the row would turn that explicit choice into title:asc, unrecoverably.
		result = list_sort.migrate_legacy_stores(trakt_rows={}, personal_rows={}, tmdb_rows={8675309: 'None'})
		self.assertEqual('default:asc', result['tmdb:8675309'])

	def test_tmdb_null_and_blank_sort_orders_keep_provider_order(self):
		result = list_sort.migrate_legacy_stores(trakt_rows={}, personal_rows={}, tmdb_rows={1: None, 2: ''})
		self.assertEqual({'tmdb:1': 'default:asc', 'tmdb:2': 'default:asc'}, result)

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

	def test_settings_migration_cannot_reach_the_new_blank_codes(self):
		# LEGACY_TMDB_CODES now answers 'None' and '', which _legacy_code() must never look up:
		# it coerces a missing or blank setting to the '4' fallback first. Pinned because the two
		# tables share LEGACY_TMDB_CODES and only the store path may see those keys.
		for stored in (None, '', 'None'):
			overrides = list_sort.migrate_legacy_sort_settings({'tmdbsort.watchlist': stored})['overrides']
			self.assertEqual('default:asc', overrides['tmdb:watchlist'])
		self.assertEqual('4', list_sort._legacy_code({'tmdbsort.watchlist': None}, 'tmdbsort.watchlist'))
		self.assertEqual('4', list_sort._legacy_code({'tmdbsort.watchlist': ''}, 'tmdbsort.watchlist'))
		self.assertEqual('4', list_sort._legacy_code({}, 'tmdbsort.watchlist'))


def _sort_source_calls(path):
	"""Every list_sort.sort_source(...) call in a module, as dicts of unparsed argument source.

	Parsed from source with ast rather than imported, because both modules pull in the Kodi runtime.
	Mirrors tests/test_simkl_mdblist_sort.py.
	"""
	with open(str(path), 'r', encoding='utf-8') as f:
		tree = ast.parse(f.read())
	calls = []
	for node in ast.walk(tree):
		if not isinstance(node, ast.Call): continue
		func = node.func
		if not isinstance(func, ast.Attribute) or func.attr != 'sort_source': continue
		if not isinstance(func.value, ast.Name) or func.value.id != 'list_sort': continue
		keywords = dict((k.arg, ast.unparse(k.value)) for k in node.keywords if k.arg)
		args = [ast.unparse(a) for a in node.args]
		calls.append({'tree': tree, 'args': args, 'list_key': args[1], 'adapter': args[3] if len(args) > 3 else None,
			'fallback': keywords.get('fallback')})
	return calls


def _assigned_source(tree, name):
	"""The source of the expression a module-level-visible name was last assigned, else name itself."""
	found = name
	for node in ast.walk(tree):
		if isinstance(node, ast.Assign) and any(ast.unparse(t) == name for t in node.targets):
			found = ast.unparse(node.value)
	return found


class CallSiteFallbackTests(_StubbedTestCase):
	"""Pin that the two mixed-list call sites actually pass the provider-order fallback.

	The engine-level tests above prove the fallback works; nothing else would notice a call site
	that stopped passing one, and the result is every un-customised Trakt user list and TMDb list
	silently reordering to title:asc on upgrade, with no legacy row left to recover from.
	"""

	def _single_call(self, path, adapter):
		calls = [c for c in _sort_source_calls(path) if c['adapter'] == adapter]
		self.assertEqual(1, len(calls), 'expected exactly one %s sort_source call in %s' % (adapter, path.name))
		return calls[0]

	def test_trakt_user_list_call_site_passes_the_payload_sort_as_fallback(self):
		call = self._single_call(TRAKT_API, "'trakt_list'")
		self.assertEqual("'trakt.list:%s' % list_id", call['list_key'])
		self.assertIsNotNone(call['fallback'], 'the Trakt user list call site must pass a fallback')
		self.assertEqual('list_sort.trakt_list_fallback(sort_by, sort_how)',
			_assigned_source(call['tree'], call['fallback']))

	def test_tmdb_call_site_fallback_literal_preserves_provider_order(self):
		call = self._single_call(TMDB_LISTS, "'tmdb'")
		self.assertEqual("'tmdb:%s' % list_id", call['list_key'])
		self.assertIsNotNone(call['fallback'], 'the TMDb list call site must pass a fallback')
		result = list_sort.sort_source(list(TMDB_ROWS), 'tmdb:8675309', None, 'tmdb',
			fallback=ast.literal_eval(call['fallback']))
		self.assertEqual(TMDB_PROVIDER_ORDER, [i['title'] for i in result])

	def test_trakt_call_site_fallback_expression_preserves_the_payload_sort(self):
		call = self._single_call(TRAKT_API, "'trakt_list'")
		self.assertIsNotNone(call['fallback'], 'the Trakt user list call site must pass a fallback')
		source = _assigned_source(call['tree'], call['fallback'])
		fallback = eval(source, {'list_sort': list_sort, 'sort_by': 'rank', 'sort_how': 'asc'})
		result = list_sort.sort_source(list(TRAKT_LIST_ROWS), 'trakt.list:99', None, 'trakt_list', fallback=fallback)
		self.assertEqual([1, 2, 3], [i['rank'] for i in result])


if __name__ == '__main__':
	unittest.main()
