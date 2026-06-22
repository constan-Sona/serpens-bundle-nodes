import bpy
import os
import ast
import json
from ...base_node import SN_ScriptingBaseNode
from .._bundle_common import (
    socket_idname_for_value,
    struct_from_data,
    resync_all_separate_bundles,
)


# Parsed JSON cached per node so we don't read the file on every redraw.
# Keyed by (tree_name, node_name); cleared on reload, never persisted.
_JSON_DATA = {}


class SN_JsonReadNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_JsonReadNode"
    bl_label = "JSON Read"
    bl_width_default = 240
    node_color = (0.584, 0.443, 0.486)  # #95717C

    def on_create(self, context):
        # The single path source. Type/pick a file in the socket's own field, or wire a
        # static string (e.g. a String node / Path Info) — the structure is read from it
        # at edit time and the sockets rebuild automatically when the path or the file's
        # content changes. A dynamic (runtime-only) wired path keeps the last structure.
        p = self._add_input("SN_StringSocket", "Path")
        try:
            p.subtype = "FILE_PATH"
        except Exception:
            pass

    # --- data access -------------------------------------------------------

    def _key(self):
        return (self.node_tree.name, self.name)

    def _struct_path(self):
        """The path used at EDIT time to build the sockets.
        Returns the path string, "" when empty, or None when the Path socket is linked
        to something that can't be resolved statically (keep the last structure then)."""
        p = self.inputs.get("Path")
        if p is None:
            return ""
        if p.is_linked:
            from_out = p.from_socket()
            if from_out is None:
                return None
            try:
                # static sources (String node, Path Info default...) repr as a python
                # string literal (possibly r'...'), which literal_eval understands
                val = ast.literal_eval(from_out.python_value)
                if isinstance(val, str):
                    return bpy.path.abspath(val) if val else ""
            except Exception:
                pass
            return None  # dynamic expression: structure unknown at edit time
        if p.default_value:
            return bpy.path.abspath(p.default_value)
        return ""

    def _struct_sig(self):
        """Signature of the edit-time file (path + mtime) used for auto-refresh.
        None = unknown/dynamic (do not rebuild)."""
        path = self._struct_path()
        if path is None:
            return None
        if not path:
            return ""
        try:
            return f"{path}|{os.path.getmtime(path)}"
        except Exception:
            return f"{path}|missing"

    def _read_file(self):
        path = self._struct_path()
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _data(self):
        # Lazily (re)read when the in-memory cache is cold (e.g. right after reopening
        # the scene: the cache is empty but the Path socket value is restored from the
        # .blend, so reading on demand recovers the data).
        key = self._key()
        val = _JSON_DATA.get(key)
        if val is None:
            val = self._read_file()
            _JSON_DATA[key] = val
        return val

    def _top_struct(self, data):
        """Top-level struct. Object -> its keys; otherwise a single 'Value' socket."""
        if isinstance(data, dict):
            return struct_from_data(data)
        if data is None:
            return []
        return [("Value", socket_idname_for_value(data), None, None, False)]

    def struct_for_output(self, out):
        """Object struct for a nested-OBJECT output (used by Separate Bundle).
        Returns None for array outputs (those are consumed by Loop For Bundle)."""
        data = self._data()
        if not isinstance(data, dict):
            return None
        sub = data.get(out.name)
        return struct_from_data(sub) if isinstance(sub, dict) else None

    def element_struct_for_output(self, out):
        """Element struct for an ARRAY output (used by Loop For Bundle)."""
        data = self._data()
        if not isinstance(data, dict):
            return None
        sub = data.get(out.name)
        if isinstance(sub, (list, tuple)) and len(sub) and isinstance(sub[0], dict):
            return struct_from_data(sub[0])
        return None

    # --- structure building ------------------------------------------------

    def reload(self):
        """Re-read the file, rebuild the output sockets, resync downstream Separates."""
        sig = self._struct_sig()
        if sig is None:
            return  # dynamic path: keep the current structure
        _JSON_DATA[self._key()] = None
        data = self._read_file()
        _JSON_DATA[self._key()] = data
        self["_struct_sig_built"] = sig
        self._rebuild(self._top_struct(data))
        resync_all_separate_bundles()

    def _deferred_reload(self):
        self["_reload_pending"] = False
        try:
            self.reload()
        except Exception:
            pass
        return None  # one-shot

    def _schedule_reload(self):
        # topology-safe: reload changes sockets, so do it on the next tick
        if not self.get("_reload_pending", False):
            self["_reload_pending"] = True
            bpy.app.timers.register(self._deferred_reload, first_interval=0.0)

    def _rebuild(self, struct):
        old_links = {out.name: out.to_sockets() for out in self.outputs if out.is_linked}
        self.disable_evaluation = True
        try:
            for i in range(len(self.outputs) - 1, -1, -1):
                self.outputs.remove(self.outputs[i])
            for name, idn, _children, _src, _arr in struct:
                new = self._add_output(idn, name)
                new.set_name_silent(name)
            for out in self.outputs:
                if out.name in old_links:
                    for to_socket in old_links[out.name]:
                        try:
                            self.node_tree.links.new(out, to_socket)
                        except Exception:
                            pass
        finally:
            self.disable_evaluation = False
        self._evaluate(bpy.context)

    # --- code generation ---------------------------------------------------

    @property
    def _loader(self):
        return f"sn_json_{self.static_uid}"

    def evaluate(self, context):
        # auto-rebuild when the path OR the file content (mtime) changed; a dynamic
        # wired path (sig None) keeps the structure. Done on a timer (topology-safe).
        sig = self._struct_sig()
        if sig is not None and sig != self.get("_struct_sig_built", None):
            self._schedule_reload()
        else:
            # safety net: rebuild if the outputs drifted from the data (e.g. socket
            # types changed across addon versions)
            desired = [(n, idn) for n, idn, _c, _s, _a in self._top_struct(self._data())]
            current = [(o.name, o.bl_idname) for o in self.outputs]
            if sig is not None and desired != current:
                self["_struct_sig_built"] = None
                self._schedule_reload()

        # runtime path: the Path socket (its own field or whatever is wired into it)
        path_inp = self.inputs.get("Path")
        if path_inp is not None and (path_inp.is_linked or path_inp.default_value):
            path_repr = path_inp.python_value
        else:
            path_repr = "''"

        # mtime-aware memoized loader: cheap on repeated UI calls, but re-reads
        # automatically when the file changes on disk (e.g. after a JSON Write)
        self.code_imperative = f"""
            _{self._loader}_cache = {{}}
            def {self._loader}(path):
                import os, json
                try:
                    sn_m = os.path.getmtime(path)
                except Exception:
                    return {{}}
                sn_c = _{self._loader}_cache.get(path)
                if sn_c is None or sn_c[0] != sn_m:
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            _{self._loader}_cache[path] = (sn_m, json.load(f))
                    except Exception:
                        _{self._loader}_cache[path] = (sn_m, {{}})
                return _{self._loader}_cache[path][1]
            """

        data = self._data()
        is_obj = isinstance(data, dict)
        arr_names = {n for n, _i, _c, _s, a in self._top_struct(data) if a}
        for out in self.outputs:
            if not is_obj and out.name == "Value":
                out.python_value = f'{self._loader}({path_repr})'
            elif out.name in arr_names:
                # array-of-objects -> Bundle holding the whole list (iterate w/ Loop For Bundle)
                out.python_value = f'{self._loader}({path_repr}).get("{out.name}", [])'
            else:
                out.python_value = f'{self._loader}({path_repr}).get("{out.name}", None)'

    def draw_node(self, context, layout):
        sp = self._struct_path()
        if sp is None:
            layout.label(text="Dynamic path (keeps last structure)", icon="INFO")
        elif sp and self._data() is None:
            row = layout.row()
            row.alert = True
            row.label(text="File not found or invalid JSON", icon="ERROR")
        elif not len(self.outputs):
            layout.label(text="Set a .json file in the Path socket", icon="INFO")

    def on_free(self):
        _JSON_DATA.pop(self._key(), None)
