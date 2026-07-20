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
