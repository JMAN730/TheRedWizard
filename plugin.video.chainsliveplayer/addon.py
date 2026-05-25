# -*- coding: utf-8 -*-
import json
import os
import re
import sys
import urllib.request
from urllib.parse import parse_qsl, quote_plus, unquote_plus, urlparse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

ADDON = xbmcaddon.Addon()
CHAINSLIVE_ID = 'plugin.video.chainslive'
ADDON_HANDLE = int(sys.argv[1])
ADDON_URL = sys.argv[0]

DEFAULT_MANIFEST_URL = 'https://thechains24.com/ABSOLUTION/chains1o5.txt'
DEFAULT_ICON_URL = 'https://thechains24.com/2/LIVE/live.png'
DEFAULT_FANART_URL = 'https://thechains24.com/2/LIVE/livefanart.png'

USER_AGENT = (
	'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
	'(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

_DIR_BLOCK = re.compile(r'<dir>(.+?)</dir>', re.DOTALL | re.IGNORECASE)
_EXTINF = re.compile(r'#EXTINF:[^\r\n]*,([^\r\n]+)\r?\n([^\r\n#]+)', re.MULTILINE)
_TVG_LOGO = re.compile(r'tvg-logo="([^"]+)"', re.IGNORECASE)
_COLOR_TAG = re.compile(r'\[[^\]]+\]')


def _params():
	if len(sys.argv) < 3 or not sys.argv[2]:
		return {}
	qs = sys.argv[2][1:] if sys.argv[2].startswith('?') else sys.argv[2]
	return dict(parse_qsl(qs, keep_blank_values=True))


def _chainslive_installed():
	try:
		xbmcaddon.Addon(CHAINSLIVE_ID)
		return True
	except Exception:
		return False


def _manifest_url():
	custom = ADDON.getSetting('manifest_url').strip()
	return custom or DEFAULT_MANIFEST_URL


def _cache_path():
	return os.path.join(ADDON.getAddonInfo('profile'), 'menu_cache.json')


def _clean_title(title):
	return _COLOR_TAG.sub('', title).strip()


def _fetch_text(url):
	req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
	with urllib.request.urlopen(req, timeout=30) as response:
		data = response.read()
	try:
		return data.decode('utf-8')
	except UnicodeDecodeError:
		return data.decode('latin-1', errors='replace')


def _tag_text(block, tag):
	match = re.search(
		r'<{tag}>(.+?)</{tag}>'.format(tag=re.escape(tag)),
		block,
		re.DOTALL | re.IGNORECASE,
	)
	return match.group(1).strip() if match else ''


def _parse_jen_dirs(content):
	entries = []
	for block in _DIR_BLOCK.findall(content):
		link = _tag_text(block, 'link')
		title = _tag_text(block, 'title') or _tag_text(block, 'name')
		if not link or not title:
			continue
		entries.append({
			'title': _clean_title(title),
			'link': link,
			'thumbnail': _tag_text(block, 'thumbnail') or DEFAULT_ICON_URL,
			'fanart': _tag_text(block, 'fanart') or DEFAULT_FANART_URL,
		})
	return entries


def _m3u_url_from_link(link):
	if link.startswith('http'):
		return link
	if link.startswith('plugin://'):
		qs = dict(parse_qsl(urlparse(link).query, keep_blank_values=True))
		url = unquote_plus(qs.get('url', ''))
		if url.startswith('http'):
			return url
	return None


def _chainslive_m3u_url(m3u_url):
	return 'plugin://%s/?mode=1&url=%s' % (CHAINSLIVE_ID, quote_plus(m3u_url))


def _load_entries(manifest_url):
	cache_file = _cache_path()
	if os.path.exists(cache_file):
		try:
			with open(cache_file, 'r', encoding='utf-8') as handle:
				cached = json.load(handle)
			if cached.get('url') == manifest_url and cached.get('entries'):
				return cached['entries']
		except Exception:
			pass

	content = _fetch_text(manifest_url)
	entries = _parse_jen_dirs(content)
	try:
		os.makedirs(os.path.dirname(cache_file), exist_ok=True)
		with open(cache_file, 'w', encoding='utf-8') as handle:
			json.dump({'url': manifest_url, 'entries': entries}, handle)
	except Exception:
		pass
	return entries


def _parse_m3u(content):
	channels = []
	for name, stream_url in _EXTINF.findall(content):
		name = _clean_title(name.strip())
		stream_url = stream_url.strip()
		if not name or not stream_url:
			continue
		channels.append({'title': name, 'url': stream_url})
	return channels


def _listitem(label, icon, fanart, playable=False):
	item = xbmcgui.ListItem(label=label)
	item.setArt({'icon': icon or DEFAULT_ICON_URL, 'thumb': icon or DEFAULT_ICON_URL, 'fanart': fanart or DEFAULT_FANART_URL})
	item.setInfo('video', {'title': label, 'plot': label})
	if playable:
		item.setProperty('IsPlayable', 'true')
	return item


def _open_in_chainslive(m3u_url):
	xbmc.executebuiltin('Container.Update(%s)' % _chainslive_m3u_url(m3u_url))


def _show_category_menu():
	manifest_url = _manifest_url()
	try:
		entries = _load_entries(manifest_url)
	except Exception as err:
		xbmcgui.Dialog().ok('Chains Live Player', 'Could not download the Chains Live menu.\n\n%s' % err)
		xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=False)
		return

	if not entries:
		xbmcgui.Dialog().ok('Chains Live Player', 'No categories found in the manifest.\n\n%s' % manifest_url)
		xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=False)
		return

	for idx, entry in enumerate(entries):
		item_url = '%s?action=list&idx=%d' % (ADDON_URL, idx)
		xbmcplugin.addDirectoryItem(
			ADDON_HANDLE,
			item_url,
			_listitem(entry['title'], entry['thumbnail'], entry['fanart']),
			isFolder=True,
		)

	xbmcplugin.setPluginCategory(ADDON_HANDLE, ADDON.getAddonInfo('name'))
	xbmcplugin.setContent(ADDON_HANDLE, 'videos')
	xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=True)


def _show_channel_list(entry):
	m3u_url = _m3u_url_from_link(entry['link'])
	if not m3u_url:
		xbmcgui.Dialog().ok('Chains Live Player', 'This category is not supported here.')
		xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=False)
		return

	try:
		content = _fetch_text(m3u_url)
		channels = _parse_m3u(content)
	except Exception as err:
		xbmc.log('Chains Live Player: m3u fetch failed (%s), using Chains Live' % err, xbmc.LOGWARNING)
		_open_in_chainslive(m3u_url)
		xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=False)
		return

	if not channels:
		xbmc.log('Chains Live Player: empty m3u, using Chains Live', xbmc.LOGWARNING)
		_open_in_chainslive(m3u_url)
		xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=False)
		return

	icon = entry['thumbnail']
	fanart = entry['fanart']
	label = entry['title']

	for channel in channels:
		stream = channel['url']
		if stream.startswith('http'):
			item_url = '%s?action=play&url=%s&title=%s' % (
				ADDON_URL,
				quote_plus(stream),
				quote_plus(channel['title']),
			)
			xbmcplugin.addDirectoryItem(
				ADDON_HANDLE,
				item_url,
				_listitem(channel['title'], icon, fanart, playable=True),
				isFolder=False,
			)
		else:
			xbmcplugin.addDirectoryItem(
				ADDON_HANDLE,
				stream,
				_listitem(channel['title'], icon, fanart),
				isFolder=True,
			)

	xbmcplugin.setPluginCategory(ADDON_HANDLE, label)
	xbmcplugin.setContent(ADDON_HANDLE, 'videos')
	xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=True)


def main():
	if not _chainslive_installed():
		xbmcgui.Dialog().ok(
			'Chains Live Player',
			'[COLOR goldenrod][B]Chains Live[/B][/COLOR] is not installed!\n\n'
			'Install [COLOR goldenrod]plugin.video.chainslive[/COLOR] from the Chains Repository, then try again',
		)
		xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=False)
		return

	params = _params()
	action = params.get('action', '').strip()

	if action == 'play':
		stream = unquote_plus(params.get('url', ''))
		title = unquote_plus(params.get('title', ''))
		item = xbmcgui.ListItem(path=stream)
		item.setInfo('video', {'title': title})
		xbmcplugin.setResolvedUrl(ADDON_HANDLE, True, item)
		return

	if action == 'list':
		try:
			idx = int(params.get('idx', '-1'))
		except ValueError:
			idx = -1
		entries = _load_entries(_manifest_url())
		if 0 <= idx < len(entries):
			_show_channel_list(entries[idx])
		else:
			xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=False)
		return

	_show_category_menu()


if __name__ == '__main__':
	main()
