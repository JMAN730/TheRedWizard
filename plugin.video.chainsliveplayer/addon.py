# -*- coding: utf-8 -*-
import re
import sys
import urllib.request

import xbmcaddon
import xbmcgui
import xbmcplugin

ADDON = xbmcaddon.Addon()
CHAINSLIVE_ID = 'plugin.video.chainslive'

DEFAULT_MANIFEST_URL = 'https://thechains24.com/ABSOLUTION/chains1o5.txt'
DEFAULT_ICON_URL = 'https://thechains24.com/2/LIVE/live.png'
DEFAULT_FANART_URL = 'https://thechains24.com/2/LIVE/livefanart.png'

USER_AGENT = (
	'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
	'(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

_DIR_BLOCK = re.compile(r'<dir>(.+?)</dir>', re.DOTALL | re.IGNORECASE)


def _chainslive_installed():
	try:
		xbmcaddon.Addon(CHAINSLIVE_ID)
		return True
	except Exception:
		return False


def _manifest_url():
	custom = ADDON.getSetting('manifest_url').strip()
	return custom or DEFAULT_MANIFEST_URL


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
			'title': title,
			'link': link,
			'thumbnail': _tag_text(block, 'thumbnail') or DEFAULT_ICON_URL,
			'fanart': _tag_text(block, 'fanart') or DEFAULT_FANART_URL,
		})
	return entries


def _listitem(label, icon, fanart):
	item = xbmcgui.ListItem(label=label)
	item.setArt({'icon': icon, 'thumb': icon, 'fanart': fanart})
	item.setInfo('video', {'title': label, 'plot': label})
	return item


def main():
	handle = int(sys.argv[1])

	if not _chainslive_installed():
		xbmcgui.Dialog().ok(
			'Chains Live Player',
			'[COLOR goldenrod][B]Chains Live[/B][/COLOR] is not installed!\n\n'
			'Install [COLOR goldenrod]plugin.video.chainslive[/COLOR] from the Chains Repository, then try again',
		)
		xbmcplugin.endOfDirectory(handle, succeeded=False)
		return

	manifest_url = _manifest_url()
	try:
		content = _fetch_text(manifest_url)
	except Exception as err:
		xbmcgui.Dialog().ok(
			'Chains Live Player',
			'Could not download the Chains Live menu.\n\n%s' % err,
		)
		xbmcplugin.endOfDirectory(handle, succeeded=False)
		return

	entries = _parse_jen_dirs(content)
	if not entries:
		xbmcgui.Dialog().ok(
			'Chains Live Player',
			'No categories found in the manifest.\n\n%s' % manifest_url,
		)
		xbmcplugin.endOfDirectory(handle, succeeded=False)
		return

	for entry in entries:
		link = entry['link']
		is_folder = link.startswith('plugin://') or link.startswith('http')
		xbmcplugin.addDirectoryItem(
			handle,
			link,
			_listitem(entry['title'], entry['thumbnail'], entry['fanart']),
			isFolder=is_folder,
		)

	xbmcplugin.setPluginCategory(handle, ADDON.getAddonInfo('name'))
	xbmcplugin.setContent(handle, 'videos')
	xbmcplugin.endOfDirectory(handle, succeeded=True)


if __name__ == '__main__':
	main()
