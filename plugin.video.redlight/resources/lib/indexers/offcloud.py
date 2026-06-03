# -*- coding: utf-8 -*-
# Thanks to kodifitzwell for allowing me to borrow his code
import sys
from apis.offcloud_api import Offcloud
from modules import kodi_utils
from modules.source_utils import supported_video_extensions
from modules.utils import clean_file_name, normalize
# logger = kodi_utils.logger

def oc_cloud():
	def _builder():
		for count, item in enumerate(folders, 1):
			try:
				cm = []
				cm_append = cm.append
				is_folder = item['isDirectory']
				request_id, folder_name, server = item['requestId'], item['fileName'], item['server']
				delete_params = {'mode': 'offcloud.delete', 'folder_id': request_id}
				if is_folder:
					display = '%02d | [B]FOLDER[/B] | [I]%s [/I]' % (count, clean_file_name(normalize(folder_name)).upper())
					url_params = {'mode': 'offcloud.browse_oc_cloud', 'folder_id': request_id}
					cm_append(('[B]Delete Folder[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(delete_params)))
				else:
					display = '%02d | [B]File[/B] | [I]%s [/I]' % (count, clean_file_name(normalize(folder_name)).upper())
					link = Offcloud.requote_uri(Offcloud.build_url(server, request_id, folder_name))
					url_params = {'mode': 'offcloud.resolve_oc', 'url': link, 'play': 'true'}
					down_file_params = {'mode': 'downloader', 'action': 'cloud.offcloud_direct', 'name': folder_name, 'url': link, 'image': icon}
					cm_append(('[B]Delete File[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(delete_params)))
					cm.append(('[B]Download File[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(down_file_params)))
				url = kodi_utils.build_url(url_params)
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': fanart, 'banner': icon})
				yield (url, listitem, is_folder)
			except Exception:
				pass
	icon, fanart = kodi_utils.get_icon('offcloud'), kodi_utils.get_addon_fanart()
	cloud_folders = Offcloud.user_cloud()
	folders = [i for i in (cloud_folders or []) if i.get('status') == 'downloaded']
	handle = int(sys.argv[1])
	kodi_utils.add_items(handle, list(_builder()))
	kodi_utils.set_content(handle, 'files')
	kodi_utils.end_directory(handle)
	kodi_utils.set_view_mode('view.premium')

def browse_oc_cloud(folder_id):
	def _builder():
		for count, item in enumerate(video_files, 1):
			try:
				cm = []
				name = item.split('/')[-1]
				name = clean_file_name(name).upper()
				link = Offcloud.requote_uri(item)
				display = '%02d | [B]FILE[/B] | [I]%s [/I]' % (count, name)
				url_params = {'mode': 'offcloud.resolve_oc', 'url': link, 'play': 'true'}
				url = kodi_utils.build_url(url_params)
				down_file_params = {'mode': 'downloader', 'action': 'cloud.offcloud_direct', 'name': name, 'url': link, 'image': icon}
				cm.append(('[B]Download File[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(down_file_params)))
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': fanart, 'banner': icon})
				listitem.getVideoInfoTag(True).setPlot(' ')
				yield (url, listitem, False)
			except Exception:
				pass
	icon, fanart = kodi_utils.get_icon('offcloud'), kodi_utils.get_addon_fanart()
	torrent_files = Offcloud.user_cloud_info(folder_id)
	video_files = [i for i in (torrent_files or []) if i.lower().endswith(tuple(supported_video_extensions()))]
	handle = int(sys.argv[1])
	kodi_utils.add_items(handle, list(_builder()))
	kodi_utils.set_content(handle, 'files')
	kodi_utils.end_directory(handle)
	kodi_utils.set_view_mode('view.premium')

def oc_delete(folder_id):
	if not kodi_utils.confirm_dialog(): return
	result = Offcloud.delete_torrent(folder_id)
	if not result or 'success' not in result: return kodi_utils.notification('Error')
	Offcloud.clear_cache()
	kodi_utils.execute_builtin('Container.Refresh')

def resolve_oc(params):
	url = params['url']
	if params.get('play', 'false') != 'true': return url
	from modules.player import RedLightPlayer
	RedLightPlayer().run(url, 'video')

def oc_account_info():
	try:
		kodi_utils.show_busy_dialog()
		account_info = Offcloud.account_info()
		body = []
		append = body.append
		append('[B]Email[/B]: %s' % account_info.get('email', ''))
		append('[B]User ID[/B]: %s' % account_info.get('user_id') or account_info.get('userId', ''))
		is_premium = account_info.get('is_premium') if 'is_premium' in account_info else account_info.get('isPremium', '')
		append('[B]Premium[/B]: %s' % is_premium)
		expires = account_info.get('expiration_date') or account_info.get('expirationDate', '')
		append('[B]Expires[/B]: %s' % expires)
		if 'can_download' in account_info:
			append('[B]Can Download[/B]: %s' % account_info.get('can_download'))
		append('[B]Cloud Limit[/B]: {:,}'.format((account_info.get('limits') or {}).get('cloud', 0)))
		kodi_utils.hide_busy_dialog()
		return kodi_utils.show_text('OFFCLOUD', '\n\n'.join(body), font_size='large')
	except Exception:
		kodi_utils.hide_busy_dialog()
