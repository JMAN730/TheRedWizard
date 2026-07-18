"""Provider-neutral watchlist toggle. Dispatches to Trakt watchlist, Simkl Plan to Watch,
or MDBList watchlist depending on the resolved provider."""


def toggle_watchlist(params):
	provider = params.get('provider')
	if not provider:
		from modules import settings
		provider = settings.active_watchlist_provider()
	if not provider:
		from modules import kodi_utils
		return kodi_utils.notification('No Active List Provider', 3500)
	if provider == 'trakt':
		from apis import trakt_api
		return trakt_api.toggle_watchlist(params)
	action = params.get('action', 'add')
	tmdb_id, media_type = params['tmdb_id'], params['media_type']
	imdb_id, tvdb_id = params.get('imdb_id'), params.get('tvdb_id')
	if provider == 'simkl':
		from apis import simkl_api
		if action == 'add': return simkl_api.simkl_add_to_list('plantowatch', tmdb_id, media_type, imdb_id, tvdb_id)
		return simkl_api.simkl_remove_from_list('plantowatch', tmdb_id, media_type, imdb_id, tvdb_id)
	if provider == 'mdblist':
		from apis import mdblist_api
		if action == 'add': return mdblist_api.mdblist_add_to_watchlist(tmdb_id, media_type, imdb_id)
		return mdblist_api.mdblist_remove_from_watchlist(tmdb_id, media_type, imdb_id)

def watchlist_tmdb_ids(provider, media_type):
	try:
		if provider == 'trakt':
			from apis.trakt_api import trakt_watchlist_tmdb_ids
			return trakt_watchlist_tmdb_ids(media_type)
		if provider == 'simkl':
			from apis.simkl_api import simkl_plantowatch_tmdb_ids
			return simkl_plantowatch_tmdb_ids(media_type)
		if provider == 'mdblist':
			from apis.mdblist_api import mdblist_watchlist_tmdb_ids
			return mdblist_watchlist_tmdb_ids(media_type)
	except: pass
	return set()
