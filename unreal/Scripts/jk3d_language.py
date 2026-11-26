"""JK3DStudio VR: switch the guide's language (texts + voices) before a show.

Usage in the Unreal Python console:
    import jk3d_language as L; L.set_language("en")   # or "ru"
Texts live in jk3d_guide_texts.json next to this file (checked by Fact Guard).
Voices: /Game/JK3D/Guide/Audio/VO_<ROOM>_<RU|EN>.
"""
import json, os, re
import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = "/Game/JK3D/Guide/Audio/VO_{room}_{lang}"


def _phrases(text):
    # one subtitle per sentence: the guide splits lines on "|"
    return "|".join(s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip())


def set_language(lang="en"):
    lang = lang.lower()
    texts = json.load(open(os.path.join(HERE, "jk3d_guide_texts.json"), encoding="utf-8"))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    done = []
    for a in actors:
        label = a.get_actor_label()
        if label.startswith("JK3D_Zone_"):
            room = label[len("JK3D_Zone_"):]
            if room in texts:
                a.set_editor_property("Lines", _phrases(texts[room][lang]))
                a.set_editor_property("Voice", unreal.load_asset(AUDIO.format(room=room, lang=lang.upper())))
                done.append(room)
        elif label == "JK3D_Guide":
            a.set_editor_property("GreetingText", _phrases(texts["GREETING"][lang]))
            a.set_editor_property("GreetingVoice", unreal.load_asset(AUDIO.format(room="GREETING", lang=lang.upper())))
            done.append("GREETING")
    unreal.EditorLevelLibrary.save_current_level()
    unreal.log("[JK3D] guide language set to %s for: %s" % (lang, ", ".join(done)))
    return done
