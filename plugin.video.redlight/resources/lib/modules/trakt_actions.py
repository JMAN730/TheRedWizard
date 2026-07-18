# -*- coding: utf-8 -*-

from modules import kodi_utils, settings


def watchlist_context_menu_item(build_url, params):
	action_params = dict(params)
	action_params['mode'] = 'trakt.add_to_watchlist_item'
	return ['trakt_watchlist', ('[B]Add to Watchlist[/B]', 'RunPlugin(%s)' % build_url(action_params))]


def _positive_integer(value):
	value = str(value).strip()
	if not value.isdigit() or len(value) > 20:
		raise ValueError
	numeric_value = int(value)
	if numeric_value <= 0:
		raise ValueError
	return numeric_value


def _imdb_identifier(value):
	value = str(value).strip()
	if len(value) > 20 or not value.startswith('tt') or not value[2:].isdigit():
		raise ValueError
	return value


def build_list_item_payload(params):
	media_type = params.get('media_type')
	if media_type == 'movie':
		return {'movies': [{'ids': {'tmdb': _positive_integer(params['tmdb_id'])}}]}
	if media_type != 'tvshow':
		raise ValueError
	identifiers = (
		('tmdb_id', 'tmdb', _positive_integer),
		('imdb_id', 'imdb', _imdb_identifier),
		('tvdb_id', 'tvdb', _positive_integer),
	)
	for param_key, trakt_key, validator in identifiers:
		try:
			media_id = validator(params.get(param_key))
		except (TypeError, ValueError):
			continue
		return {'shows': [{'ids': {trakt_key: media_id}}]}
	raise ValueError


def add_to_watchlist_item(params):
	if not settings.trakt_user_active():
		return kodi_utils.notification('No Active Trakt Account', 3500)
	try:
		payload = build_list_item_payload(params)
	except (KeyError, TypeError, ValueError):
		return kodi_utils.notification('Invalid media information', 3500)
	from apis import trakt_api
	return trakt_api.add_to_watchlist(payload)
