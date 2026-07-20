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
	"""Return data sorted by spec using adapter's field extractors. Never raises."""
	if not data: return data
	field = spec.get('field', 'title')
	if field == 'default': return data
	if field == 'random': return sorted(data, key=lambda k: _random())
	extractor = adapter.get('fields', {}).get(field)
	if extractor is None: return data
	reverse = spec.get('direction', 'asc') == 'desc'
	if field == 'title':
		key = lambda i: strip_articles(extractor(i), ignore_articles)
	else:
		key = extractor
	try:
		return sorted(data, key=key, reverse=reverse)
	except Exception:
		return data
