"""The Continue Watching mode must be wired into the static registries the addon reads.

navigator_cache.py and settings_cache.py both import the Kodi runtime, so the menu literals and
the directory-listing mode set are pulled out of their ASTs instead of importing the modules —
the same approach as test_base_cache_databases.py.
"""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'plugin.video.redlight' / 'resources' / 'lib'


def _class_list_literal(path, class_name, attr_name):
	tree = ast.parse(path.read_text(encoding='utf-8'))
	for node in ast.walk(tree):
		if isinstance(node, ast.ClassDef) and node.name == class_name:
			for stmt in node.body:
				if isinstance(stmt, ast.Assign) and any(getattr(t, 'id', None) == attr_name for t in stmt.targets):
					return ast.literal_eval(stmt.value)
	raise AssertionError('%s.%s not found in %s' % (class_name, attr_name, path))


def _module_assign_literal(path, name):
	tree = ast.parse(path.read_text(encoding='utf-8'))
	for node in ast.walk(tree):
		if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == name for t in node.targets):
			return ast.literal_eval(node.value)
	raise AssertionError('%s not found in %s' % (name, path))


class DefaultMenuTests(unittest.TestCase):
	def _entry(self, menu):
		return next((i for i in menu if i.get('mode') == 'build_continue_watching'), None)

	def test_movie_menu_has_continue_watching(self):
		menu = _class_list_literal(LIB / 'caches' / 'navigator_cache.py', 'NavigatorCache', 'movie_list')
		entry = self._entry(menu)
		self.assertIsNotNone(entry)
		self.assertEqual('Continue Watching', entry['name'])

	def test_tvshow_menu_has_continue_watching(self):
		menu = _class_list_literal(LIB / 'caches' / 'navigator_cache.py', 'NavigatorCache', 'tvshow_list')
		entry = self._entry(menu)
		self.assertIsNotNone(entry)
		self.assertEqual('Continue Watching', entry['name'])


class ListingModeTests(unittest.TestCase):
	def test_mode_is_a_directory_listing_mode(self):
		tree = ast.parse((LIB / 'caches' / 'settings_cache.py').read_text(encoding='utf-8'))
		for node in ast.walk(tree):
			if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == '_DIRECTORY_LISTING_MODES' for t in node.targets):
				modes = ast.literal_eval(node.value.args[0])
				self.assertIn('build_continue_watching', modes)
				return
		raise AssertionError('_DIRECTORY_LISTING_MODES not found')


if __name__ == '__main__':
	unittest.main()
