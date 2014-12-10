import requests
import json
from onitu.plug.exceptions import ServiceError

redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

authorization_base_url = "https://accounts.google.com/o/oauth2/auth"
token_url = "https://accounts.google.com/o/oauth2/token"
r_url = "https://www.googleapis.com/upload/drive/v2/files?uploadType=resumable"
file_url = "https://www.googleapis.com/upload/drive/v2/files"
file_url_basic = "https://www.googleapis.com/drive/v2/files"
scope = ["https://www.googleapis.com/auth/drive"]


def send(func, url, h, p, d, json=True):
    try:
        r = func(url, headers=h, params=p, data=d)
        if json is True:
            ret = r.json()
        else:
            ret = r.content
        if r.status_code != 200 and r.status_code != 204 \
                and r.status_code != 308 and r.status_code != 206:
            raise ServiceError(str(r.status_code) + " on " + url)
        return (r.headers, ret)
    except Exception as e:
        raise ServiceError(str(e))


def get_token(c_id, c_se, r_to):
    access_token_req = {
        "refresh_token": r_to,
        "client_id": c_id,
        "client_secret": c_se,
        "grant_type": "refresh_token",
    }
    url = "https://accounts.google.com/o/oauth2/token"
    return send(requests.post, url, {}, {}, access_token_req)


def get_information(access_token, name, parent_id):
        headers = {
            "Authorization": "Bearer " + access_token,
            "Content-Type": "application/json",
        }
        data = {"q": "title=\"" + name + "\" and \"" +
                parent_id + "\" in parents and trashed=false"}
        url = "https://www.googleapis.com/drive/v2/files"
        return send(requests.get, url, headers, data, {})


def get_information_by_id(access_token, file_id):
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/json",
    }
    url = "https://www.googleapis.com/drive/v2/files"
    return send(requests.get, url+"/"+file_id, headers, {}, {})


def add_folder(access_token, name, parent_id):
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/json",
    }

    data = """
    {
       "title": \""""+name+"""\",
       "parents": [{"id":\""""+parent_id+"""\"}],
       "mimeType": "application/vnd.google-apps.folder"
    }
    """
    url = "https://www.googleapis.com/drive/v2/files"
    return send(requests.post, url, headers, {}, data)


def delete_by_id(access_token, id_d):
    headers = {
        "Authorization": "Bearer " + access_token,
    }
    url = "https://www.googleapis.com/drive/v2/files"
    return send(requests.delete, url + "/" + id_d, headers, {}, {}, False)


def start_upload(access_token, name, parent_id, self_id):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + access_token,
    }
    data = {
        "title": name
    }
    if parent_id is not None:
        data["parents"] = [{
            "kind": "drive#fileLink",
            "id": parent_id
        }]
    url = "https://www.googleapis.com/upload/drive/v2/files"
    if self_id is not None:
        url += "/" + self_id
    url += "?uploadType=resumable"
    if self_id is not None:
        return send(requests.put, url, headers, {}, json.dumps(data), False)
    return send(requests.post, url, headers, {}, json.dumps(data), False)


def send_metadata(access_token, name, parent_id, self_id, size, params={}):
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/json",
        "Content-Length": size
    }
    data = {
        "title": name
    }
    if parent_id is not None:
        data["parents"] = [{
            "kind": "drive#fileLink",
            "id": parent_id
        }]
    url = "https://www.googleapis.com/drive/v2/files"
    if self_id is not None:
        url += "/" + self_id
        return send(requests.put, url, headers, params, json.dumps(data))
    return send(requests.post, url, headers, params, json.dumps(data))


def upload_chunk(access_token, location, offset, chunk, totalsize):
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Length": str(len(chunk)),
        "Content-Range": "bytes " + str(offset) + "-"
        + str(offset + len(chunk) - 1)
        + "/" + str(totalsize),
    }
    return send(requests.put, location, headers, {}, chunk, False)


def get_chunk(access_token, downloadUrl, offset, size):
    headers = {
        "Authorization": "Bearer " + access_token,
        "Range": "bytes=" + str(offset) + "-"
        + str(offset + size - 1)
    }
    return send(requests.get, downloadUrl, headers, {}, {}, False)


def get_files_by_path(access_token, parent_id):
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/json",
    }
    data = {"q": "\""+parent_id+"\" in parents and trashed=false"}
    url = "https://www.googleapis.com/drive/v2/files"
    return send(requests.get, url, headers, data, {})


def get_change(access_token, maxResult, lasterChangeId):
    headers = {
        "Authorization": "Bearer " + access_token,
    }
    params = {
        "maxResults": maxResult,
        "startChangeId": lasterChangeId,
    }
    url = "https://www.googleapis.com/drive/v2/changes"
    return send(requests.get, url, headers, params, {})


def get_parent(access_token, file_id):
    headers = {
        "Authorization": "Bearer " + access_token,
    }
    url = "https://www.googleapis.com/drive/v2/files"
    return send(requests.get, url + "/" + file_id + "/parents",
                headers, {}, {})
