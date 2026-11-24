"""JK3DStudio VR — link between the Unreal editor and the AI Gateway.

Run inside Unreal Editor (Python):
    import jk3d_gateway as g
    g.CONFIG.update(url="http://127.0.0.1:8000", api_key="...", project_id="jk3d-001")
    g.ensure_project("Pilot apartment", floor=9)
    g.send_passport()        # rooms, approx. areas, light and door counts -> passport (status "check")
    # designer checks the passport and approves it (API /docs or later the plugin UI)
    g.download_audio()       # approved speech audio -> Content/JK3D/Guide/Audio

Only the Python standard library is used (Unreal's Python has no extra packages).
Areas come from the bounding box of ROOM_<NAME>_FLOOR and are exact only for rectangular
rooms, so every auto field is sent with status "check" for the designer to confirm.

NOTE: written without access to the editor; first run together with the author and fix if needed.
"""
import json
import os
import urllib.error
import urllib.request

import unreal

CONFIG = {"url": "http://127.0.0.1:8000", "api_key": "change-this-key", "project_id": "jk3d-001"}

ROOM_PREFIX, FLOOR_SUFFIX = "ROOM_", "_FLOOR"


# ---------- HTTP ----------
def _request(method, path, body=None, raw=False):
    req = urllib.request.Request(
        CONFIG["url"].rstrip("/") + path,
        method=method,
        data=None if body is None else json.dumps(body).encode("utf-8"),
        headers={"X-API-Key": CONFIG["api_key"], "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            return data if raw else (json.loads(data) if data else None)
    except urllib.error.HTTPError as e:
        unreal.log_error(f"[JK3D] {method} {path} -> {e.code}: {e.read().decode('utf-8', 'replace')}")
        raise


# ---------- Scene analysis ----------
def _actors():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()


def _rooms():
    """{ROOM: (min_x, min_y, max_x, max_y, area_m2)} from ROOM_<NAME>_FLOOR actors (Unreal units = cm)."""
    rooms = {}
    for a in _actors():
        label = a.get_actor_label()
        if label.upper().startswith(ROOM_PREFIX) and label.upper().endswith(FLOOR_SUFFIX):
            name = label[len(ROOM_PREFIX):-len(FLOOR_SUFFIX)].upper()
            origin, extent = a.get_actor_bounds(False)
            area = (2 * extent.x / 100.0) * (2 * extent.y / 100.0)
            rooms[name] = (origin.x - extent.x, origin.y - extent.y, origin.x + extent.x, origin.y + extent.y,
                           round(area, 1))
    return rooms


def _room_of(location, rooms):
    for name, (x0, y0, x1, y1, _) in rooms.items():
        if x0 <= location.x <= x1 and y0 <= location.y <= y1:
            return name
    return None


def collect_passport():
    rooms = _rooms()
    lights = {r: 0 for r in rooms}
    doors = {r: 0 for r in rooms}
    for a in _actors():
        room = _room_of(a.get_actor_location(), rooms)
        if room is None:
            continue
        if isinstance(a, unreal.Light):
            lights[room] += 1
        elif a.get_actor_label().upper().startswith("DOOR_"):
            doors[room] += 1

    fields = []
    for r, (*_, area) in rooms.items():
        low = r.lower()
        fields += [
            {"key": f"{low}.area_m2", "room": r, "label": {"ru": "Площадь", "en": "Area"},
             "value": str(area), "unit": "m2", "source": "auto", "status": "check", "required": True},
            {"key": f"{low}.lights", "room": r, "label": {"ru": "Светильников", "en": "Light fixtures"},
             "value": str(lights[r]), "source": "auto", "status": "check"},
            {"key": f"{low}.doors", "room": r, "label": {"ru": "Дверей", "en": "Doors"},
             "value": str(doors[r]), "source": "auto", "status": "check"},
        ]
    return fields


# ---------- Commands ----------
def ensure_project(name, floor=None, languages=("ru", "en")):
    try:
        _request("GET", f"/v1/projects/{CONFIG['project_id']}")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        _request("POST", "/v1/projects", {"id": CONFIG["project_id"], "name": name, "floor": floor,
                                          "languages": list(languages)})
    unreal.log(f"[JK3D] project {CONFIG['project_id']} ready")


def send_passport():
    fields = collect_passport()
    _request("PUT", f"/v1/projects/{CONFIG['project_id']}/passport", {"fields": fields})
    unreal.log(f"[JK3D] sent {len(fields)} passport fields; designer must check and approve them")
    return fields


def download_audio(target_dir="/Game/JK3D/Guide/Audio"):
    """Download approved audio and import it as Sound Wave assets (WAV imports directly)."""
    export = _request("GET", f"/v1/projects/{CONFIG['project_id']}/export")
    out = os.path.join(unreal.Paths.project_saved_dir(), "JK3D_Audio")
    os.makedirs(out, exist_ok=True)
    files = []
    for item in export["speech"]:
        for audio_id in item["audio_ids"]:
            data = _request("GET", f"/v1/audio/{audio_id}", raw=True)
            ext = ".wav" if data[:4] == b"RIFF" else ".mp3"
            path = os.path.join(out, f"VO_{item['room']}_{item['lang']}_{audio_id}{ext}")
            with open(path, "wb") as f:
                f.write(data)
            files.append(path)
    wavs = [p for p in files if p.endswith(".wav")]
    if wavs:
        tasks = []
        for p in wavs:
            t = unreal.AssetImportTask()
            t.filename, t.destination_path, t.automated, t.replace_existing, t.save = p, target_dir, True, True, True
            tasks.append(t)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    unreal.log(f"[JK3D] downloaded {len(files)} files to {out}; imported {len(wavs)} WAV")
    if len(wavs) < len(files):
        unreal.log_warning("[JK3D] MP3 files are not imported by Unreal: convert to WAV (e.g. ffmpeg) first")
    return files
