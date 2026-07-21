# -*- coding: utf-8 -*-
"""Single sort model, engine and source adapters for every user-facing list.

Deliberately free of Kodi and addon imports so it can be unit-tested directly.
Settings and storage lookups are lazy imports inside functions.
"""
import re
from random import random as _random

MISSING_DATE = '2050-01-01'

DEFAULT_SPEC = {'field': 'title', 'direction': 'asc'}

VALID_FIELDS = ('title', 'date_added', 'release_date', 'rating', 'votes', 'runtime', 'rank', 'random', 'default')
VALID_DIRECTIONS = ('asc', 'desc')

# Fields whose ordering is not user-reversible.
DIRECTIONLESS_FIELDS = ('random', 'default')

FIELD_LABELS = {
	'title': 'Title', 'date_added': 'Date Added', 'release_date': 'Release Date', 'rating': 'Rating',
	'votes': 'Votes', 'runtime': 'Runtime', 'rank': 'Rank', 'random': 'Random', 'default': 'Provider Default'
}

DIRECTION_LABELS = {'asc': 'ascending', 'desc': 'descending'}

_ARTICLE_RE = re.compile(r'^(the|a|an)\s+')


def parse_spec(raw, fallback=None):
	"""'date_added:desc' -> {'field': 'date_added', 'direction': 'desc'}. Never raises."""
	if fallback is None: fallback = dict(DEFAULT_SPEC)
	if not raw: return dict(fallback)
	try:
		parts = str(raw).split(':')
		field = parts[0].strip()
		direction = parts[1].strip() if len(parts) > 1 else 'asc'
	except Exception:
		return dict(fallback)
	if field not in VALID_FIELDS: return dict(fallback)
	if direction not in VALID_DIRECTIONS: direction = 'asc'
	return {'field': field, 'direction': direction}


def format_spec(spec):
	return '%s:%s' % (spec.get('field', 'title'), spec.get('direction', 'asc'))


def spec_label(spec):
	field = spec.get('field', 'title')
	label = FIELD_LABELS.get(field, field)
	if field in DIRECTIONLESS_FIELDS: return label
	return '%s (%s)' % (label, DIRECTION_LABELS.get(spec.get('direction', 'asc'), 'ascending'))


def _safe_int(value, default):
	"""Best-effort int() coercion for sort keys. Falls back to default on missing or malformed values
	instead of raising, so one bad row from an external API can't silently unsort the whole list."""
	if not value: return default
	try:
		return int(value)
	except (TypeError, ValueError):
		return default


def strip_articles(title, ignore_articles):
	"""Lower-cased sort key for a title. Strips a leading 'the '/'a '/'an ' when enabled."""
	try:
		if title is None: return ''
		title = str(title).lower()
		if not ignore_articles: return title
		return _ARTICLE_RE.sub('', title)
	except Exception:
		return ''


def apply(data, spec, adapter, ignore_articles=False):
	"""Return data sorted by spec using adapter's field extractors. Never raises.

	Always returns a new list, never the caller's original object.
	"""
	if not data: return []
	field = spec.get('field', 'title')
	if field == 'default': return list(data)
	if field == 'random':
		try:
			return sorted(data, key=lambda k: _random())
		except Exception:
			return list(data)
	extractor = adapter.get('fields', {}).get(field)
	if extractor is None: return list(data)
	reverse = spec.get('direction', 'asc') == 'desc'
	if field == 'title':
		key = lambda i: strip_articles(extractor(i), ignore_articles)
	else:
		key = extractor
	try:
		return sorted(data, key=key, reverse=reverse)
	except Exception:
		return list(data)


def _node(item):
	"""Trakt list rows nest the payload under a key named by item['type']."""
	try: return item.get(item.get('type')) or {}
	except Exception: return {}


def _trakt_list_released(item):
	node = _node(item)
	if 'released' in node: return node.get('released') or MISSING_DATE
	if 'first_aired' in node: return node.get('first_aired') or MISSING_DATE
	return MISSING_DATE


TRAKT_SYNC = {
	'capabilities': ('title', 'date_added', 'release_date', 'random'),
	'fields': {
		'title': lambda i: i.get('title'),
		'date_added': lambda i: i.get('collected_at') or '',
		'release_date': lambda i: i.get('released') or MISSING_DATE,
	}
}

TRAKT_LIST = {
	'capabilities': ('title', 'date_added', 'release_date', 'rating', 'votes', 'runtime', 'rank', 'random', 'default'),
	'fields': {
		'title': lambda i: _node(i).get('title'),
		'date_added': lambda i: i.get('listed_at') or '',
		'release_date': _trakt_list_released,
		'rating': lambda i: _node(i).get('rating') or 0,
		'votes': lambda i: _node(i).get('votes') or 0,
		'runtime': lambda i: _node(i).get('runtime') or 0,
		'rank': lambda i: i.get('rank') or 0,
	}
}

SIMKL = {
	'capabilities': ('title', 'date_added', 'release_date', 'random', 'default'),
	'fields': {
		'title': lambda i: i.get('title'),
		'date_added': lambda i: i.get('collected_at') or '',
		'release_date': lambda i: i.get('released') or MISSING_DATE,
	}
}

MDBLIST_WATCHLIST = {
	'capabilities': ('title', 'date_added', 'release_date', 'random'),
	'fields': {
		'title': lambda i: i.get('title'),
		'date_added': lambda i: i.get('watchlist_at') or '',
		'release_date': lambda i: i.get('release_date') or MISSING_DATE,
	}
}

# NOTE: this adapter's release_date extractor returns an integer year, not a date string like every
# other adapter's. That is deliberate - the old MDBList collection code sorted on 'year', which is the
# only date-ish field the payload carries - but it means the spec string 'release_date:desc' denotes
# different data here than elsewhere. Keys from two adapters are never comparable; do not assume a
# future shared sort UI can merge or compare them.
MDBLIST_COLLECTION = {
	'capabilities': ('title', 'date_added', 'release_date', 'random'),
	'fields': {
		'title': lambda i: i.get('title'),
		'date_added': lambda i: i.get('collected_at') or '',
		'release_date': lambda i: _safe_int(i.get('year'), 9999),
	}
}

PERSONAL = {
	'capabilities': ('title', 'date_added', 'release_date', 'random', 'default'),
	'fields': {
		'title': lambda i: i.get('title'),
		'date_added': lambda i: _safe_int(i.get('date_added'), 0),
		'release_date': lambda i: i.get('release_date') or MISSING_DATE,
	}
}

TMDB = {
	'capabilities': ('title', 'release_date', 'random', 'default'),
	'fields': {
		'title': lambda i: i.get('title'),
		'release_date': lambda i: i.get('release_date') or MISSING_DATE,
	}
}

ADAPTERS = {
	'trakt_sync': TRAKT_SYNC, 'trakt_list': TRAKT_LIST, 'simkl': SIMKL,
	'mdblist_watchlist': MDBLIST_WATCHLIST, 'mdblist_collection': MDBLIST_COLLECTION,
	'personal': PERSONAL, 'tmdb': TMDB
}


def field_choices(adapter_name):
	adapter = ADAPTERS.get(adapter_name)
	if not adapter: return ()
	return adapter['capabilities']


DEFAULT_SETTING_IDS = {'movies': 'redlight.sort.default.movies', 'shows': 'redlight.sort.default.shows'}


def resolve(list_key, media_type=None):
	"""Per-list override, else the mediatype default, else DEFAULT_SPEC."""
	from caches.list_sort_cache import scope_key, normalize_media_type, get_override
	scope = scope_key(list_key, media_type)
	raw = get_override(scope)
	if raw:
		spec = parse_spec(raw, fallback=None)
		if format_spec(spec) == raw: return spec
	normalized = normalize_media_type(media_type)
	if not normalized: return dict(DEFAULT_SPEC)
	from caches.settings_cache import get_setting
	return parse_spec(get_setting(DEFAULT_SETTING_IDS[normalized], ''))


LEGACY_SYNC_CODES = {'0': 'title:asc', '1': 'date_added:desc', '2': 'release_date:desc', '3': 'date_added:asc', '4': 'release_date:asc'}

LEGACY_TMDB_CODES = {'0': 'title:asc', '1': 'release_date:asc', '2': 'release_date:desc', '3': 'random:asc', '4': 'default:asc'}

# MDBList only ever honoured three of the five legacy codes (apis/mdblist_api.py:574-577, :585-588):
# 2 -> release date / year descending, 1 -> watchlist_at / collected_at descending, and everything
# else - including 0, 3 and 4 - falls through to title. Translating it through LEGACY_SYNC_CODES
# would silently change the ordering of every MDBList list belonging to a user on code 3 or 4.
LEGACY_MDBLIST_CODES = {'0': 'title:asc', '1': 'date_added:desc', '2': 'release_date:desc', '3': 'title:asc', '4': 'title:asc'}

LEGACY_PERSONAL_CODES = {'0': 'title:asc', '1': 'date_added:asc', '2': 'date_added:desc', '3': 'release_date:asc',
	'4': 'release_date:desc', '5': 'random:asc', 'None': 'default:asc', '': 'title:asc'}

# Trakt user-list sort_by values -> canonical fields.
LEGACY_TRAKT_FIELDS = {'added': 'date_added', 'released': 'release_date', 'popularity': 'votes', 'percentage': 'rating',
	'title': 'title', 'runtime': 'runtime', 'rank': 'rank', 'votes': 'votes', 'random': 'random', 'default': 'default'}


def translate_trakt_custom_sort(sort_by, sort_how):
	"""Legacy Trakt per-list sort_by/sort_how -> 'field:direction'. '' when unmappable."""
	field = LEGACY_TRAKT_FIELDS.get(sort_by)
	if not field: return ''
	direction = 'desc' if sort_how == 'desc' else 'asc'
	return '%s:%s' % (field, direction)


class SortMigrationError(Exception):
	"""A translated sort preference could not be persisted."""


# An absent row is not "no preference" - it is the fallback the old getter hardcoded, and the list was
# ordered by it. lists_sort_order used int(get_setting('redlight.sort.%s', '0')) -> code 0 (title), and
# tmdblists_sort_order used get_setting('redlight.tmdbsort.%s', '4') -> code 4 (provider order). Reading
# a missing row as '' would map to nothing, write nothing, and let the scope inherit the new global
# default (seeded from sort.watchlist) - silently reordering the list.
LEGACY_SETTING_FALLBACKS = {'sort.watchlist': '0', 'sort.collection': '0', 'sort.simkl': '0',
	'tmdbsort.watchlist': '4', 'tmdbsort.favorites': '4'}


def _legacy_code(old_settings, setting_id):
	"""The stored legacy code, or the fallback the old getter used when the row is absent or blank."""
	fallback = LEGACY_SETTING_FALLBACKS[setting_id]
	value = old_settings.get(setting_id, fallback)
	if value is None or value == '': return fallback
	return str(value)


def migrate_legacy_sort_settings(old_settings):
	"""Pure translation of the old settings dict into new defaults and overrides."""
	defaults, overrides = {}, {}
	watchlist_code = _legacy_code(old_settings, 'sort.watchlist')
	collection_code = _legacy_code(old_settings, 'sort.collection')
	watchlist_spec = LEGACY_SYNC_CODES.get(watchlist_code)
	if watchlist_spec:
		defaults['sort.default.movies'] = watchlist_spec
		defaults['sort.default.shows'] = watchlist_spec
	baseline = watchlist_spec or LEGACY_SYNC_CODES['0']
	collection_spec = LEGACY_SYNC_CODES.get(collection_code)
	if collection_spec and collection_spec != baseline:
		overrides['trakt.collection:movies'] = collection_spec
		overrides['trakt.collection:shows'] = collection_spec
	# MDBList reads the same two settings but implements a different, narrower mapping, so it is
	# always pinned explicitly. Inheriting the global default - which is seeded from sort.watchlist
	# through LEGACY_SYNC_CODES - would give it an ordering it never honoured.
	for legacy_code, list_key in ((watchlist_code, 'mdblist.watchlist'), (collection_code, 'mdblist.collection')):
		mdblist_spec = LEGACY_MDBLIST_CODES.get(legacy_code)
		if not mdblist_spec: continue
		overrides['%s:movies' % list_key] = mdblist_spec
		overrides['%s:shows' % list_key] = mdblist_spec
	simkl_spec = LEGACY_SYNC_CODES.get(_legacy_code(old_settings, 'sort.simkl'))
	if simkl_spec and simkl_spec != baseline:
		overrides['simkl:movies'] = simkl_spec
		overrides['simkl:shows'] = simkl_spec
	for old_id, scope in (('tmdbsort.watchlist', 'tmdb:watchlist'), ('tmdbsort.favorites', 'tmdb:favorites')):
		tmdb_spec = LEGACY_TMDB_CODES.get(_legacy_code(old_settings, old_id))
		if tmdb_spec: overrides[scope] = tmdb_spec
	return {'defaults': defaults, 'overrides': overrides}


def run_sort_migration(old_settings, write_setting):
	"""Apply the translation. write_setting(setting_id, value) persists a setting.

	Returns True when anything was written, False when there was nothing to migrate. Note that
	since every legacy setting is read through its documented fallback, an empty old_settings
	dict still translates to the fallback ordering, so False is now a defensive case only.

	Raises SortMigrationError when an override could not be persisted. set_override() swallows
	its own exceptions and reports False, so an unwritable store would otherwise look like a
	clean success and the caller would record the migration as done with the user's
	preferences already deleted. Every override is attempted before raising, so a single bad
	row does not discard the ones that can still be saved.
	"""
	result = migrate_legacy_sort_settings(old_settings)
	if not result['defaults'] and not result['overrides']: return False
	from caches.list_sort_cache import set_override
	for setting_id, spec_string in result['defaults'].items():
		write_setting(setting_id, spec_string)
		write_setting('%s_name' % setting_id, spec_label(parse_spec(spec_string)))
	failed = [scope for scope, spec_string in result['overrides'].items() if not set_override(scope, spec_string)]
	if failed:
		raise SortMigrationError('could not persist sort overrides: %s' % ', '.join(sorted(failed)))
	return True


def migrate_legacy_stores(trakt_rows, personal_rows, tmdb_rows):
	"""Translate the three legacy per-list stores into {scope: spec_string}.

	trakt_rows:    {list_id: {'sort_by':..., 'sort_how':...}}  (caches.trakt_cache.get_all_lists_custom_sort)
	personal_rows: {(name, author): sort_order}
	tmdb_rows:     {list_id: sort_order}
	Unmappable rows are skipped rather than guessed.
	"""
	result = {}
	for list_id, row in (trakt_rows or {}).items():
		spec_string = translate_trakt_custom_sort(row.get('sort_by'), row.get('sort_how'))
		if spec_string: result['trakt.list:%s' % list_id] = spec_string
	for (name, author), sort_order in (personal_rows or {}).items():
		spec_string = LEGACY_PERSONAL_CODES.get(str(sort_order))
		if spec_string: result['personal:%s|%s' % (name, author)] = spec_string
	for list_id, sort_order in (tmdb_rows or {}).items():
		spec_string = LEGACY_TMDB_CODES.get(str(sort_order))
		if spec_string: result['tmdb:%s' % list_id] = spec_string
	return result


def sort_source(data, list_key, media_type, adapter_name):
	"""Resolve the spec for this list and media type, then sort. Never raises."""
	if not data: return data
	adapter = ADAPTERS.get(adapter_name)
	if not adapter: return data
	try:
		spec = resolve(list_key, media_type)
	except Exception:
		spec = dict(DEFAULT_SPEC)
	try:
		from modules.settings import ignore_articles
		articles = ignore_articles()
	except Exception:
		articles = False
	return apply(data, spec, adapter, ignore_articles=articles)
