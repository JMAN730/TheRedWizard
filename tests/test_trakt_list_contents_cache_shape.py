"""get_trakt_list_contents' cache row has one shape, whoever asks for it.

The disk cache key is built from list_type/user/slug/list_id only - it does not encode the `method`
the fetch was made with. get_trakt() returns a bare list for method=None and a
{'sort_by','sort_how','data'} dict for method='sort_by_headers', so two callers asking for the same
list with different methods write and read incompatible rows under one key. That is what happened
when the list builder still carried sort_by/sort_how in its folder URL while trakt_image_maker,
which has no URL to carry them in, called with the default: the builder's row was a dict, the
custom-sort branch skipped the unwrapping, and the enumerate() below iterated the dict's three keys
and did i['type'] on a string. Swallowed by the enclosing try - the list simply rendered empty.

The function is compiled straight out of apis/trakt_api.py against stub globals rather than
imported: the module pulls in the whole Kodi runtime, but this one function only touches
trakt_cache, get_trakt, list_sort and settings.
"""
import ast
import sys
import unittest

from test_trakt_sync_list_sort import ROOT, list_sort, _install_stubs, OVERRIDES, SETTINGS

_STUBBED_MODULES = ('caches', 'caches.list_sort_cache', 'caches.settings_cache', 'modules', 'modules.settings')

TRAKT_API = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'apis' / 'trakt_api.py'
TRAKT_LISTS = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'indexers' / 'trakt_lists.py'

# Ranks are deliberately out of payload order, so "sorted by rank" and "handed back untouched" are
# different sequences and a fallback that quietly stopped working would be visible here.
ROWS = [
	{'type': 'movie', 'rank': 2, 'movie': {'ids': {'trakt': 2}, 'title': 'Banana', 'released': '2001-01-01'}},
	{'type': 'movie', 'rank': 3, 'movie': {'ids': {'trakt': 3}, 'title': 'Alpha', 'released': '1999-01-01'}},
	{'type': 'movie', 'rank': 1, 'movie': {'ids': {'trakt': 1}, 'title': 'Cherry', 'released': '2010-01-01'}},
]

PAYLOAD_ORDER = ['Banana', 'Alpha', 'Cherry']
RANK_ASC = ['Cherry', 'Banana', 'Alpha']


def _tree(path):
	with open(str(path), 'r', encoding='utf-8') as f:
		return ast.parse(f.read())


def _function(path, name):
	found = [n for n in ast.walk(_tree(path)) if isinstance(n, ast.FunctionDef) and n.name == name]
	if len(found) != 1: raise AssertionError('expected exactly one def %s in %s' % (name, path.name))
	return found[0]


class _Harness:
	"""get_trakt_list_contents compiled against stubs, plus the cache params it asked for."""

	def __init__(self, cache_row):
		self.cache_row = cache_row
		self.requested = []
		node = _function(TRAKT_API, 'get_trakt_list_contents')
		module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))

		class _TraktCache:
			@staticmethod
			def cache_trakt_object(function, string, params):
				self.requested.append({'string': string, 'params': params})
				return self.cache_row

		class _Settings:
			@staticmethod
			def ignore_articles(): return False

		namespace = {'trakt_cache': _TraktCache, 'get_trakt': lambda *a, **k: None,
			'list_sort': list_sort, 'settings': _Settings}
		exec(compile(module, '<get_trakt_list_contents>', 'exec'), namespace)
		self.call = namespace['get_trakt_list_contents']

	def titles(self, *args, **kwargs):
		return [i['title'] for i in self.call(*args, **kwargs)]

	@property
	def method(self):
		return self.requested[-1]['params']['method']


def _dict_row(sort_by='rank', sort_how='asc'):
	return {'sort_by': sort_by, 'sort_how': sort_how, 'data': [dict(i) for i in ROWS]}


class CacheShapeTests(unittest.TestCase):
	# Several modules in this suite install their own 'caches'/'modules' stubs at import time, and
	# sort_source() re-reads sys.modules on every call, so collection order would otherwise decide
	# whose override store these tests see. Same idiom as tests/test_mixed_list_sort.py.
	def setUp(self):
		self._original_sys_modules = dict((k, sys.modules[k]) for k in _STUBBED_MODULES if k in sys.modules)
		_install_stubs()
		OVERRIDES.clear()
		SETTINGS.clear()

	def tearDown(self):
		for key in _STUBBED_MODULES:
			if key in self._original_sys_modules: sys.modules[key] = self._original_sys_modules[key]
			else: sys.modules.pop(key, None)
		OVERRIDES.clear()
		SETTINGS.clear()

	def test_every_caller_requests_the_same_method(self):
		"""The builder, the artwork maker and the random builders all share one cache key, so they
		must all write the same shape into it."""
		harness = _Harness(_dict_row())
		harness.call('my_lists', 'jo', 'faves', True, '42')                # the list builder
		builder_method = harness.method
		harness.call('my_lists', 'jo', 'faves', True, '42')                # trakt_image_maker
		self.assertEqual(builder_method, harness.method)
		harness.call('my_lists', 'jo', 'faves', True, '42', 'skip')        # the random builders
		self.assertEqual(builder_method, harness.method)
		self.assertEqual('sort_by_headers', builder_method)

	def test_all_three_callers_share_one_cache_key(self):
		# If they ever stop sharing it, the shape agreement above stops mattering - and so does this
		# whole file. Pinned so that change is a deliberate one.
		harness = _Harness(_dict_row())
		harness.call('my_lists', 'jo', 'faves', True, '42')
		harness.call('my_lists', 'jo', 'faves', True, '42', 'skip')
		self.assertEqual(1, len(set(i['string'] for i in harness.requested)))

	def test_a_dict_row_is_unwrapped_for_the_skip_caller_too(self):
		"""'skip' used to bypass the unwrapping entirely: the dict reached enumerate(), i['type'] ran
		against the string 'sort_by', and every row was swallowed by the try - an empty list."""
		harness = _Harness(_dict_row())
		self.assertEqual(PAYLOAD_ORDER, harness.titles('my_lists', 'jo', 'faves', True, '42', 'skip'))

	def test_a_dict_row_is_unwrapped_for_a_custom_sort_caller_too(self):
		# The signature still accepts a sort_by. No caller passes one any more, but one that did must
		# not resurrect the crash.
		harness = _Harness(_dict_row())
		self.assertEqual(3, len(harness.call('my_lists', 'jo', 'faves', True, '42', 'rank', 'asc')))

	def test_a_legacy_bare_list_row_still_reads(self):
		"""Rows written by the previous build are plain lists. They must survive the upgrade."""
		harness = _Harness([dict(i) for i in ROWS])
		self.assertEqual(PAYLOAD_ORDER, harness.titles('my_lists', 'jo', 'faves', True, '42'))

	def test_the_payload_headers_drive_the_fallback_ordering(self):
		"""Nothing carries sort_by/sort_how in from a URL any more, so the headers in the cached row
		are the only remaining record of the order Trakt declares for the list."""
		harness = _Harness(_dict_row('rank', 'asc'))
		self.assertEqual(RANK_ASC, harness.titles('my_lists', 'jo', 'faves', True, '42'))

	def test_the_builder_and_the_artwork_maker_produce_the_same_order(self):
		"""trakt_image_maker builds the poster from the first four items the user sees on screen."""
		harness = _Harness(_dict_row('rank', 'asc'))
		builder = harness.titles('my_lists', 'jo', 'faves', True, '42')
		artwork = harness.titles('my_lists', 'jo', 'faves', True, '42')
		self.assertEqual(builder, artwork)
		self.assertEqual(RANK_ASC, artwork)

	def test_headerless_rows_fall_back_to_the_provider_order(self):
		harness = _Harness({'sort_by': None, 'sort_how': None, 'data': [dict(i) for i in ROWS]})
		self.assertEqual(PAYLOAD_ORDER, harness.titles('my_lists', 'jo', 'faves', True, '42'))


def _positional_arg_count(node, called_name):
	counts = []
	for child in ast.walk(node):
		if not isinstance(child, ast.Call): continue
		func = child.func
		name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else None)
		if name != called_name: continue
		counts.append((len(child.args), sorted(k.arg for k in child.keywords if k.arg)))
	return counts


class CallSiteTests(unittest.TestCase):
	def test_no_caller_asks_for_a_client_side_sort(self):
		"""Five positional arguments: list_type, user, slug, with_auth, list_id. A sixth is a sort_by,
		which is exactly what split the two callers apart."""
		for name in ('build_trakt_list', 'trakt_image_maker'):
			calls = _positional_arg_count(_function(TRAKT_LISTS, name), 'get_trakt_list_contents')
			self.assertEqual([(5, [])], calls, name)

	def test_the_legacy_per_list_sort_store_is_no_longer_read(self):
		with open(str(TRAKT_LISTS), 'r', encoding='utf-8') as f:
			source = f.read()
		self.assertNotIn('get_all_lists_custom_sort', source)
		self.assertNotIn('all_custom_sorts', source)

	def test_no_trakt_list_folder_url_carries_a_sort(self):
		"""A sort_by in the folder URL is what build_trakt_list read back out and passed on. Every
		url_params dict that names a build_trakt_list-ish mode must be free of both keys."""
		checked = 0
		for node in ast.walk(_tree(TRAKT_LISTS)):
			if not isinstance(node, ast.Dict): continue
			keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
			if 'mode' not in keys: continue
			source = ast.unparse(node)
			if 'build_trakt_list' not in source: continue
			checked += 1
			self.assertNotIn("'sort_by'", source, source)
			self.assertNotIn("'sort_how'", source, source)
		self.assertTrue(checked >= 4, 'expected to find the list folder URL dicts, found %d' % checked)

	def test_the_set_custom_sort_menu_still_carries_trakts_declared_order(self):
		"""It is not a folder URL: those two values are the fallback the "Use Default" choice resolves
		to, and they now come from the Trakt list metadata rather than from the legacy store."""
		checked = 0
		for node in ast.walk(_tree(TRAKT_LISTS)):
			if not isinstance(node, ast.Dict): continue
			if 'set_list_custom_sort' not in ast.unparse(node): continue
			keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
			checked += 1
			self.assertIn('sort_by', keys)
			self.assertIn('sort_how', keys)
		self.assertEqual(2, checked, 'expected both Set Custom Sort context menu entries')


if __name__ == '__main__':
	unittest.main()
