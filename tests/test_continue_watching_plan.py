"""plan_continue_watching() is the single seam behind the merged Continue Watching list.

It takes the three raw watched-database row sets (in-progress movies, in-progress episodes,
next episodes), the hidden-progress show ids and the optional next-episodes limit, and returns
the render plan: the movie (order, tmdb_id) pairs, the tagged episode dicts, and the majority
content type. Everything else in the feature is thin glue over existing builders, so these
tests pin the whole merge/dedup/sort behaviour.

The module is imported directly by path, like the list_sort tests: its top level must stay free
of Kodi imports (the render glue does its imports lazily inside the function).
"""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'indexers' / 'continue_watching.py'


def _load_module():
	spec = importlib.util.spec_from_file_location('continue_watching_under_test', MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


continue_watching = _load_module()
plan_continue_watching = continue_watching.plan_continue_watching


def _movie(tmdb_id, last_played):
	return {'media_id': tmdb_id, 'title': 'Movie %s' % tmdb_id, 'last_played': last_played}


def _progress_ep(tmdb_id, season, episode, date):
	return {'media_ids': {'tmdb': tmdb_id}, 'season': season, 'episode': episode,
			'resume_point': 42.0, 'date': date, 'title': 'Show %s' % tmdb_id}


def _next_ep(tmdb_id, season, episode, last_played):
	return {'media_ids': {'tmdb': tmdb_id}, 'season': season, 'episode': episode,
			'title': 'Show %s' % tmdb_id, 'last_played': last_played}


class DedupTests(unittest.TestCase):
	def test_show_with_in_progress_episode_loses_its_next_episode_row(self):
		plan = plan_continue_watching(
			[], [_progress_ep(100, 2, 5, '2026-07-20 21:00:00')],
			[_next_ep(100, 2, 5, '2026-07-20 21:00:00'), _next_ep(200, 1, 1, '2026-07-19 20:00:00')],
			[], None)
		shows = [i['media_ids']['tmdb'] for i in plan['episodes']]
		self.assertEqual([100, 200], shows)
		self.assertEqual(1, shows.count(100))

	def test_in_progress_row_wins_over_next_row(self):
		plan = plan_continue_watching(
			[], [_progress_ep(100, 2, 5, '2026-07-20 21:00:00')],
			[_next_ep(100, 2, 5, '2026-07-20 21:00:00')],
			[], None)
		row = plan['episodes'][0]
		self.assertFalse(row.get('cw_next'))
		self.assertEqual(42.0, row['resume_point'])

	def test_duplicate_progress_rows_keep_only_the_most_recent(self):
		plan = plan_continue_watching(
			[], [_progress_ep(100, 2, 5, '2026-07-20 21:00:00'), _progress_ep(100, 1, 3, '2026-07-18 21:00:00')],
			[], [], None)
		self.assertEqual(1, len(plan['episodes']))
		self.assertEqual(5, plan['episodes'][0]['episode'])

	def test_duplicate_next_rows_keep_only_the_most_recent(self):
		plan = plan_continue_watching(
			[], [],
			[_next_ep(200, 1, 1, '2026-07-19 20:00:00'), _next_ep(200, 1, 2, '2026-07-20 20:00:00')],
			[], None)
		self.assertEqual(1, len(plan['episodes']))
		self.assertEqual(2, plan['episodes'][0]['episode'])

	def test_next_rows_are_tagged_cw_next(self):
		plan = plan_continue_watching([], [], [_next_ep(200, 1, 1, '2026-07-19 20:00:00')], [], None)
		self.assertTrue(plan['episodes'][0]['cw_next'])


class SortTests(unittest.TestCase):
	def test_unified_order_is_last_watched_descending(self):
		plan = plan_continue_watching(
			[_movie(500, '2026-07-20 12:00:00')],
			[_progress_ep(100, 2, 5, '2026-07-20 18:00:00')],
			[_next_ep(200, 1, 1, '2026-07-20 06:00:00')],
			[], None)
		movie_orders = dict((tmdb_id, order) for order, tmdb_id in plan['movies'])
		ep_orders = dict((i['media_ids']['tmdb'], i['custom_order']) for i in plan['episodes'])
		self.assertEqual(0, ep_orders[100])
		self.assertEqual(1, movie_orders[500])
		self.assertEqual(2, ep_orders[200])

	def test_missing_timestamp_sinks_to_the_end(self):
		plan = plan_continue_watching(
			[_movie(500, '2026-07-20 12:00:00')],
			[], [_next_ep(200, 1, 1, None)], [], None)
		ep_orders = dict((i['media_ids']['tmdb'], i['custom_order']) for i in plan['episodes'])
		movie_orders = dict((tmdb_id, order) for order, tmdb_id in plan['movies'])
		self.assertEqual(0, movie_orders[500])
		self.assertEqual(1, ep_orders[200])


class HiddenAndLimitTests(unittest.TestCase):
	def test_hidden_shows_are_dropped_from_both_episode_sources(self):
		plan = plan_continue_watching(
			[], [_progress_ep(100, 2, 5, '2026-07-20 21:00:00')],
			[_next_ep(300, 1, 1, '2026-07-19 20:00:00')],
			[100, 300], None)
		self.assertEqual([], plan['episodes'])

	def test_hidden_ids_compare_across_int_and_str(self):
		plan = plan_continue_watching(
			[], [_progress_ep(100, 2, 5, '2026-07-20 21:00:00')], [],
			['100'], None)
		self.assertEqual([], plan['episodes'])

	def test_hidden_ids_do_not_touch_movies(self):
		plan = plan_continue_watching([_movie(100, '2026-07-20 12:00:00')], [], [], [100], None)
		self.assertEqual(1, len(plan['movies']))

	def test_next_limit_truncates_next_rows_only(self):
		next_rows = [_next_ep(200 + n, 1, 1, '2026-07-1%s 20:00:00' % n) for n in range(5)]
		plan = plan_continue_watching(
			[], [_progress_ep(100, 2, 5, '2026-07-20 21:00:00')], next_rows, [], 2)
		self.assertEqual(3, len(plan['episodes']))


class ContentTypeTests(unittest.TestCase):
	def test_majority_episodes(self):
		plan = plan_continue_watching(
			[_movie(500, '2026-07-20 12:00:00')],
			[_progress_ep(100, 2, 5, '2026-07-20 18:00:00')],
			[_next_ep(200, 1, 1, '2026-07-20 06:00:00')],
			[], None)
		self.assertEqual('episodes', plan['content'])

	def test_majority_movies(self):
		plan = plan_continue_watching(
			[_movie(500, '2026-07-20 12:00:00'), _movie(501, '2026-07-19 12:00:00')],
			[_progress_ep(100, 2, 5, '2026-07-20 18:00:00')], [], [], None)
		self.assertEqual('movies', plan['content'])

	def test_empty_sources_give_empty_plan(self):
		plan = plan_continue_watching([], [], [], [], None)
		self.assertEqual([], plan['movies'])
		self.assertEqual([], plan['episodes'])


if __name__ == '__main__':
	unittest.main()
