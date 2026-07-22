# -*- coding: utf-8 -*-
import sys

def plan_continue_watching(movie_rows, progress_episode_rows, next_episode_rows, hidden_ids, nextep_limit):
	"""Merge the three watched-database row sets into one render plan.

	Returns {'movies': [(custom_order, tmdb_id), ...], 'episodes': [row, ...], 'content': str}.
	Episode rows keep their source fields and gain 'custom_order'; rows sourced from next
	episodes are tagged 'cw_next' so _process resolves the actual next episode for them.
	"""
	hidden = set(str(i) for i in hidden_ids or [])
	def _show_id(row): return str(row.get('media_ids', {}).get('tmdb', ''))
	def _stamp(row): return row.get('last_played') or row.get('date') or ''
	if nextep_limit: next_episode_rows = next_episode_rows[:nextep_limit]
	progress_rows = [i for i in progress_episode_rows if _show_id(i) not in hidden]
	in_progress_shows = set(_show_id(i) for i in progress_rows)
	next_rows = [dict(i, cw_next=True) for i in next_episode_rows
				if _show_id(i) not in hidden and _show_id(i) not in in_progress_shows]
	merged = [('movie', i) for i in movie_rows] + [('episode', i) for i in progress_rows + next_rows]
	merged.sort(key=lambda k: _stamp(k[1]), reverse=True)
	movies, episodes = [], []
	for custom_order, (media_type, row) in enumerate(merged):
		if media_type == 'movie': movies.append((custom_order, row['media_id']))
		else: episodes.append(dict(row, custom_order=custom_order, last_played=_stamp(row)))
	content = 'movies' if len(movies) > len(episodes) else 'episodes'
	return {'movies': movies, 'episodes': episodes, 'content': content}

def build_continue_watching(params):
	from threading import Thread
	from modules import kodi_utils, settings
	from modules import watched_status as ws
	handle, is_external, content = int(sys.argv[1]), kodi_utils.external(), 'episodes'
	try:
		from indexers.movies import Movies
		from indexers.episodes import build_single_episode
		watched_indicators = settings.watched_indicators()
		try: movie_rows = ws.get_in_progress_movies(None, 1)
		except: movie_rows = []
		try: progress_episode_rows = ws.get_in_progress_episodes()
		except: progress_episode_rows = []
		try: next_episode_rows = ws.get_next_episodes(settings.nextep_method())
		except: next_episode_rows = []
		try: hidden_ids = ws.get_hidden_progress_items(watched_indicators)
		except: hidden_ids = []
		nextep_limit = settings.nextep_limit() if settings.nextep_limit_history() else None
		plan = plan_continue_watching(movie_rows, progress_episode_rows, next_episode_rows, hidden_ids, nextep_limit)
		content = plan['content']
		item_list = []
		item_list_extend = item_list.extend
		def _movies():
			if not plan['movies']: return
			try: item_list_extend(Movies({'list': plan['movies'], 'id_type': 'tmdb_id', 'custom_order': 'true',
										'action': 'in_progress_movies', 'category_name': 'Continue Watching'}).worker())
			except: pass
		def _episodes():
			if not plan['episodes']: return
			try: item_list_extend(build_single_episode('episode.continue_watching', plan['episodes']))
			except: pass
		threads = [Thread(target=_movies), Thread(target=_episodes)]
		[i.start() for i in threads]
		[i.join() for i in threads]
		item_list.sort(key=lambda k: k[1])
		kodi_utils.add_items(handle, [i[0] for i in item_list])
	except: pass
	kodi_utils.set_content(handle, content)
	kodi_utils.set_category(handle, 'Continue Watching')
	kodi_utils.end_directory(handle, cacheToDisc=False)
	if content == 'episodes': kodi_utils.set_view_mode('view.episodes_single', 'episodes', is_external, fallback_view_types=('view.episodes',))
	else: kodi_utils.set_view_mode('view.%s' % content, content, is_external)
