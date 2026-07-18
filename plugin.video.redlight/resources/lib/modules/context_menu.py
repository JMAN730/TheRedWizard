# -*- coding: utf-8 -*-

CONTEXT_MENU_ITEMS = (
	('Extras', 'extras'),
	('Options', 'options'),
	('Play Options', 'playback_options'),
	('External Scraper Settings', 'external_scraper_settings'),
	('Browse Movie Set', 'browse_movie_set'),
	('Browse TV Seasons', 'browse_seasons'),
	('Browse Season Episodes', 'browse_episodes'),
	('Browse Recommended', 'recommended'),
	('Browse Related', 'related'),
	('Browse More Like This', 'more_like_this'),
	('Browse Similar', 'similar'),
	('In Trakt Lists', 'in_trakt_list'),
	('MDBList Manager', 'mdblist_manager'),
	('Simkl Lists Manager', 'simkl_manager'),
	('Trakt Lists Manager', 'trakt_manager'),
	('TMDb Lists Manager', 'tmdb_manager'),
	('Personal Lists Manager', 'personal_manager'),
	('Favorites Manager', 'favorites_manager'),
	('Add to Trakt Watchlist', 'trakt_watchlist'),
	('Mark Watched/Unwatched', 'mark_watched'),
	('Unmark Previous Watched Episode', 'unmark_previous_episode'),
	('Exit List', 'exit'),
	('Refresh Widgets', 'refresh'),
	('Reload Widgets', 'reload'),
)

DEFAULT_CONTEXT_MENU_ITEMS = tuple(value for _, value in CONTEXT_MENU_ITEMS)


def context_menu_items():
	return [{'name': name, 'value': value} for name, value in CONTEXT_MENU_ITEMS]
