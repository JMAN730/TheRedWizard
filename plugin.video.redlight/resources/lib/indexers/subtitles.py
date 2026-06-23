# -*- coding: utf-8 -*-
import os
import re
import xbmc
import requests
from modules import kodi_utils as ku, settings as st

timeout = 20.0
_ALERT_SUB_MAX_REMAINING = 600
_SUB_EXTS = ('.srt', '.ass', '.ssa', '.sub', '.vtt')
_ACTIVE_SUB_PROP = 'redlight.active_subtitle_path'

def _get(url, stream=False, retry=False, quiet=False):
	response = requests.get(url, stream=stream, timeout=timeout)
	if retry and response.status_code in (403, 429):
		if not quiet:
			ku.notification('SubMaker rate limited. Retrying in 10 secs...', 3500)
		ku.sleep(10000)
		return _get(url, stream=stream, quiet=quiet)
	return response

def _alert_sub_filename(imdb_id, season, episode):
	filename_lang = st.submaker_language().replace(' ', '_')
	if season: sub_filename = 'RedLightSubs_%s_%s_%s' % (imdb_id, season, episode)
	else: sub_filename = 'RedLightSubs_%s' % imdb_id
	return sub_filename + '_%s.srt' % filename_lang

def _looks_like_subtitle_path(value):
	if not value or value.strip() in ('(External)',): return False
	lower = value.lower().strip()
	if any(lower.endswith(ext) for ext in _SUB_EXTS): return True
	if lower.startswith('special://'): return True
	if '://' in lower: return any(ext in lower for ext in _SUB_EXTS)
	if os.path.sep in value or value.startswith('/') or (len(value) > 2 and value[1] == ':'):
		return any(lower.endswith(ext) for ext in _SUB_EXTS)
	return False

def _dedupe_paths(paths):
	seen, results = set(), []
	for path in paths:
		if not path: continue
		try: key = os.path.normcase(os.path.normpath(ku.translate_path(path) if path.startswith('special://') else path))
		except: key = path
		if key in seen: continue
		seen.add(key)
		results.append(path)
	return results

def _player_properties(properties):
	players = ku.get_jsonrpc({'jsonrpc': '2.0', 'id': 1, 'method': 'Player.GetActivePlayers', 'params': {}})
	if not players: return None
	player_id = players[0]['playerid']
	return ku.get_jsonrpc({'jsonrpc': '2.0', 'id': 1, 'method': 'Player.GetProperties',
		'params': {'playerid': player_id, 'properties': properties}})

def _subs_enabled(player=None):
	try:
		if player is None: player = xbmc.Player()
		if player.getSubtitles(): return True
	except: pass
	try:
		props = _player_properties(['subtitleenabled'])
		return bool(props and props.get('subtitleenabled'))
	except: pass
	return False

def _active_subtitle_paths_from_player():
	props = _player_properties(['subtitleenabled', 'currentsubtitle', 'subtitles'])
	if not props or not props.get('subtitleenabled'): return []
	paths, current = [], props.get('currentsubtitle') or {}
	current_index = current.get('index')
	for item in props.get('subtitles') or []:
		if current_index is not None and item.get('index') != current_index: continue
		for key in ('filename', 'path', 'name'):
			val = (item.get(key) or '').strip()
			if _looks_like_subtitle_path(val): paths.append(val)
	for key in ('filename', 'path', 'name'):
		val = (current.get(key) or '').strip()
		if _looks_like_subtitle_path(val): paths.append(val)
	return _dedupe_paths(paths)

def _addon_temp_subtitle_dirs():
	return (
		'special://temp/',
		'special://profile/addon_data/service.subtitles.a4ksubtitles/temp/',
	)

def _recent_subtitles_in_dir(directory, since_ts=None):
	try:
		native = ku.translate_path(directory.rstrip('/') + '/')
		if not os.path.isdir(native): return []
		found = []
		for name in os.listdir(native):
			lower = name.lower()
			if lower == 'sub.zip' or lower.endswith('.translated'): continue
			if not lower.endswith(_SUB_EXTS): continue
			full = os.path.join(native, name)
			if since_ts and os.path.getmtime(full) < (since_ts - 5): continue
			found.append((os.path.getmtime(full), full))
		found.sort(reverse=True)
		return [path for _, path in found]
	except: return []

def _sidecar_subtitle_paths(playing_filename=None, playing_url=None):
	paths = []
	for raw in (playing_url, playing_filename):
		if not raw: continue
		base_url = raw.split('|')[0].split('?')[0]
		if base_url.startswith(('http://', 'https://', 'plugin://')): continue
		translated = ku.translate_path(base_url) if base_url.startswith('special://') else base_url
		if not os.path.isfile(translated): continue
		folder, stem = os.path.dirname(translated), os.path.splitext(os.path.basename(translated))[0]
		try:
			for name in os.listdir(folder):
				lower = name.lower()
				if not lower.endswith(_SUB_EXTS): continue
				if lower.startswith(stem.lower()) or stem.lower() in lower:
					paths.append(os.path.join(folder, name))
		except: pass
	return _dedupe_paths(paths)

def _collect_subtitle_candidates(player, playing_filename, imdb_id, season, episode, playback_started_at=None):
	paths, seen = [], set()
	def add(path):
		if not path: return
		try: key = os.path.normcase(os.path.normpath(ku.translate_path(path) if path.startswith('special://') else path))
		except: key = path
		if key in seen: return
		seen.add(key)
		paths.append(path)
	active_prop = ku.get_property(_ACTIVE_SUB_PROP)
	if active_prop: add(active_prop)
	for path in _active_subtitle_paths_from_player(): add(path)
	if imdb_id: add('%s%s' % ('special://temp/', _alert_sub_filename(imdb_id, season, episode)))
	if playback_started_at:
		for directory in _addon_temp_subtitle_dirs():
			for path in _recent_subtitles_in_dir(directory, playback_started_at):
				add(path)
	try: playing_url = player.getPlayingFile() if player else None
	except: playing_url = None
	for path in _sidecar_subtitle_paths(playing_filename, playing_url): add(path)
	return paths

def _time_part_to_seconds(part):
	part = part.replace(',', '.')
	chunks = part.split(':')
	if len(chunks) == 3:
		h, m, s = chunks
		return int(h) * 3600 + int(m) * 60 + float(s)
	if len(chunks) == 2:
		m, s = chunks
		return int(m) * 60 + float(s)
	return float(part)

def _subtitle_last_end_seconds(content):
	times = re.findall(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', content)
	if not times:
		times = [(h, m, s, '000') for h, m, s in re.findall(r'(\d{2}):(\d{2}):(\d{2})', content)]
	end_seconds = 0.0
	for h, m, s, ms in times:
		end_seconds = max(end_seconds, int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0)
	if end_seconds > 0: return end_seconds
	ass_times = re.findall(r'Dialogue:\s*\d+,(\d+:\d+:\d+[\.,]\d+),(\d+:\d+:\d+[\.,]\d+)', content, re.I)
	for _, end in ass_times:
		end_seconds = max(end_seconds, _time_part_to_seconds(end))
	return end_seconds if end_seconds > 0 else None

def _seconds_remaining_before_end(sub_path, total_time):
	try:
		with ku.open_file(sub_path) as file: content = file.read()
		end_seconds = _subtitle_last_end_seconds(content)
		if end_seconds is None: return None
		remaining = float(total_time) - end_seconds
		if remaining < 0 or remaining > _ALERT_SUB_MAX_REMAINING: return None
		return int(remaining)
	except: return None

def _fetch_alert_subtitle(imdb_id, season, episode):
	manifest = st.submaker_manifest()
	if not manifest or 'manifest' not in manifest: return None
	search_filename = _alert_sub_filename(imdb_id, season, episode)
	final_path = '%s%s' % ('special://temp/', search_filename)
	if season: params = 'subtitles/series/%s:%s:%s' % (imdb_id, season, episode)
	else: params = 'subtitles/movie/%s' % imdb_id
	try: response = _get(manifest.replace('manifest', params), retry=True, quiet=True)
	except requests.RequestException: return None
	if not response.ok: return None
	subs = response.json().get('subtitles', [])
	if not subs: return None
	language = st.submaker_language()
	choices = (i for i in subs if i.get('lang') == language)
	try: chosen_sub = next(choices, None) or next(iter(subs))
	except: return None
	response = _get(chosen_sub.get('url'), stream=True, retry=True, quiet=True)
	if not response.ok: return None
	try: content = response.text
	except: content = response.content
	try:
		with ku.open_file(final_path, 'w') as file: file.write(content)
		ku.set_property(_ACTIVE_SUB_PROP, final_path)
	except: return None
	return final_path

def subtitle_seconds_remaining_before_end(total_time, imdb_id, season=None, episode=None, fetch=False, player=None,
		playing_filename=None, playback_started_at=None):
	if not total_time: return None
	for sub_path in _collect_subtitle_candidates(player, playing_filename, imdb_id, season, episode, playback_started_at):
		remaining = _seconds_remaining_before_end(sub_path, total_time)
		if remaining is not None: return remaining
	if not fetch or not imdb_id or not st.submaker_enabled(): return None
	fetched = _fetch_alert_subtitle(imdb_id, season, episode)
	if not fetched: return None
	return _seconds_remaining_before_end(fetched, total_time)

def remember_active_subtitle_path(path):
	if path: ku.set_property(_ACTIVE_SUB_PROP, path)

def clear_active_subtitle_path():
	ku.clear_property(_ACTIVE_SUB_PROP)

class Subtitles(xbmc.Player):
	def subtitles_download(self, url):
		response = _get(url, stream=True, retry=True)
		return response if response.ok else response.reason

	def subtitles_search(self):
		if self.season: params = 'subtitles/series/%s:%s:%s' % (self.imdb_id, self.season, self.episode)
		else: params = 'subtitles/movie/%s' % self.imdb_id
		try: response = _get(self.manifest.replace('manifest', params), retry=True)
		except requests.RequestException as e: return str(e)
		return response.json().get('subtitles', []) if response.ok else response.reason

	def _video_file_subs(self):
		try: available_sub_language = self.getSubtitles()
		except: available_sub_language = ''
		if not available_sub_language: return False
		if st.auto_enable_subs(): self.showSubtitles(True)
		ku.notification('Local subtitles found', icon=self.poster, settle_ms=150)
		return True

	def _downloaded_subs(self):
		files = ku.list_dirs(self.subtitle_path)[1]
		final_match = next((i for i in files if i == self.search_filename), None)
		if not final_match: return False
		subtitle = '%s%s' % (self.subtitle_path, final_match)
		ku.notification('Downloaded subtitles found', icon=self.poster, settle_ms=150)
		return subtitle

	def _searched_subs(self):
		subs = self.subtitles_search()
		if isinstance(subs, str):
			return ku.notification('SubMaker error: %s' % subs, settle_ms=150)
		if not subs:
			return ku.notification('No subtitles found', icon=self.poster, settle_ms=150)
		choices = (i for i in subs if i.get('lang') == self.language)
		try: chosen_sub = next(choices, None) or next(iter(subs))
		except: return ku.notification('No subtitles found', icon=self.poster, settle_ms=150)
		response = self.subtitles_download(chosen_sub.get('url'))
		if isinstance(response, str):
			return ku.notification('SubMaker error: %s' % response, settle_ms=150)
		final_path = '%s%s' % (self.subtitle_path, self.search_filename)
		try: content = response.text
		except: content = response.content
		with ku.open_file(final_path, 'w') as file: file.write(content)
		ku.sleep(1000)
		return final_path

	def run(self, imdb_id, season, episode, poster):
		self.manifest = st.submaker_manifest()
		if not self.manifest or 'manifest' not in self.manifest: return
		self.imdb_id, self.season, self.episode, self.poster = imdb_id, season, episode, poster
		self.language = st.submaker_language()
		filename_lang = self.language.replace(' ', '_')
		self.subtitle_path = 'special://temp/'
		if season: self.sub_filename = 'RedLightSubs_%s_%s_%s' % (self.imdb_id, self.season, self.episode)
		else: self.sub_filename = 'RedLightSubs_%s' % self.imdb_id
		self.search_filename = self.sub_filename + '_%s.srt' % filename_lang
		ku.sleep(2500)
		if st.submaker_prefer_local():
			subtitle = self._video_file_subs()
			if subtitle: return
		subtitle = self._downloaded_subs()
		if subtitle:
			remember_active_subtitle_path(subtitle)
			return self.setSubtitles(subtitle)
		subtitle = self._searched_subs()
		if subtitle:
			remember_active_subtitle_path(subtitle)
			return self.setSubtitles(subtitle)
