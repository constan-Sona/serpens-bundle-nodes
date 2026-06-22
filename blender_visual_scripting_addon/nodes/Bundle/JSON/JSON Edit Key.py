import bpy
from ...base_node import SN_ScriptingBaseNode
from .._bundle_common import matching_input_portals


def _skip_reroutes(sock):
    while sock is not None and sock.node.bl_idname == "NodeReroute":
        links = sock.node.inputs[0].links
        sock = links[0].from_socket if links else None
    return sock


def _key_segments_from(sock, depth=0):
    """Key path for an output socket of the bundle/JSON family as a list of segments,
    each ("lit", text) or ("expr", python_code_producing_a_str). None if unresolvable.
    Walks Separate chains, Bundle Portals and Index Bundle Array picks (static index,
    wired/dynamic index, and Name mode — resolved to an index at runtime)."""
    sock = _skip_reroutes(sock)
    if sock is None or depth > 32:
        return None
    node = sock.node
    idn = node.bl_idname
    if idn == "SN_JsonReadNode":
        return [("lit", sock.name)] if sock.name != "Value" else None
    if idn == "SN_SeparateBundleNode":
        base = node.inputs.get("Bundle")
        if base and base.links:
            parent = _key_segments_from(base.links[0].from_socket, depth + 1)
            if parent:
                return parent + [("lit", sock.name)]
        return None
    if idn == "SN_BundlePortalNode" and node.direction == "OUTPUT":
        for ip in matching_input_portals(node.var_name):
            if ip.inputs[0].links:
                p = _key_segments_from(ip.inputs[0].links[0].from_socket, depth + 1)
                if p:
                    return p
        return None
    if idn == "SN_IndexBundleArrayNode" and sock.name == "Item":
        base = node.inputs.get("Bundle")
        if not (base and base.links):
            return None
        parent = _key_segments_from(base.links[0].from_socket, depth + 1)
        if not parent:
            return None
        sel = node.inputs[1]
        if node.mode == "Index":
            if sel.is_linked:
                return parent + [("expr", f"str(int({sel.python_value}))")]
            return parent + [("lit", str(int(sel.default_value)))]
        # Name mode: find the element's index at RUNTIME (stays correct even if the
        # array order changes). 999999999 makes the editor abort safely on no-match.
        seq = base.python_value
        return parent + [("expr",
            f'str(next((sn_i for sn_i, sn_x in enumerate(({seq}) or []) '
            f'if isinstance(sn_x, dict) and str(sn_x.get("name")) == str({sel.python_value})), 999999999))')]
    return None


def _segments_to_expr(segments):
    """Python expression (a str) building the dotted key from segments."""
    parts = []
    for kind, val in segments:
        parts.append(repr(val) if kind == "lit" else f"({val})")
    return " + '.' + ".join(parts)


def _segments_to_label(segments):
    """Human readable preview of the key path for the node UI."""
    out = []
    for kind, val in segments:
        out.append(val if kind == "lit" else "<runtime>")
    return ".".join(out)


class SN_JsonEditKeyNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_JsonEditKeyNode"
    bl_label = "JSON Edit Key"
    bl_width_default = 240
    node_color = (0.584, 0.443, 0.486)  # #95717C (JSON family)

    # the changeable Value input can also become a Bundle (write a whole object/array)
    socket_names = {**SN_ScriptingBaseNode.socket_names,
                    "Bundle": "SN_BundleSocket",
                    "Bundle Array": "SN_BundleArraySocket"}

    def _deferred_fix_value_input(self):
        """Converts the Value input to the matching Bundle type when a bundle is
        plugged in (the raw Bundle->Data link is invalid for Serpens so
        on_link_insert never fires)."""
        self["_fix_pending"] = False
        try:
            inp = self.inputs.get("Value")
            if inp is None or not inp.links:
                return None
            fs = inp.links[0].from_socket
            if not fs or fs.bl_idname not in ("SN_BundleSocket", "SN_BundleArraySocket"):
                return None
            if inp.bl_idname != fs.bl_idname and getattr(inp, "changeable", False):
                self.convert_socket(inp, fs.bl_idname)
                self._evaluate(bpy.context)
        except Exception:
            pass
        return None  # one-shot

    def on_node_update(self):
        if not self.get("_fix_pending", False):
            self["_fix_pending"] = True
            bpy.app.timers.register(self._deferred_fix_value_input, first_interval=0.0)

    def on_create(self, context):
        self.add_execute_input()
        p = self._add_input("SN_StringSocket", "Path")
        try:
            p.subtype = "FILE_PATH"
        except Exception:
            pass
        self.add_string_input("Key")
        v = self.add_data_input("Value")
        v.changeable = True
        self.add_execute_output()

    @property
    def _editor(self):
        return f"sn_json_edit_{self.static_uid}"

    def _auto_key_segments(self):
        """When the Key input is wired to a bundle/JSON-family output, the key is taken
        from the SOCKET's path (e.g. render.engine), not from its value. Uses the raw
        link so even Bundle outputs (normally invalid on a String input) resolve."""
        key_inp = self.inputs.get("Key")
        if key_inp and key_inp.links:
            return _key_segments_from(key_inp.links[0].from_socket)
        return None

    def evaluate(self, context):
        self.code_imperative = f"""
            def {self._editor}(path, key, value):
                try:
                    import os, json
                    data = {{}}
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    except Exception:
                        data = {{}}
                    sn_parts = [p for p in str(key).split(".") if p != ""]
                    if not sn_parts:
                        print("JSON Edit Key: empty key")
                        return
                    sn_t = data
                    for sn_p in sn_parts[:-1]:
                        if isinstance(sn_t, list):
                            try:
                                sn_t = sn_t[int(sn_p)]
                            except Exception:
                                print("JSON Edit Key: invalid list index:", sn_p)
                                return
                        elif isinstance(sn_t, dict):
                            if sn_p not in sn_t or not isinstance(sn_t[sn_p], (dict, list)):
                                sn_t[sn_p] = {{}}
                            sn_t = sn_t[sn_p]
                        else:
                            print("JSON Edit Key: can't enter key:", sn_p)
                            return
                    sn_last = sn_parts[-1]
                    if isinstance(sn_t, list):
                        try:
                            sn_i = int(sn_last)
                            if -len(sn_t) <= sn_i < len(sn_t):
                                sn_t[sn_i] = value
                            else:
                                print("JSON Edit Key: index out of range:", sn_last)
                                return
                        except ValueError:
                            print("JSON Edit Key: list needs an index, got:", sn_last)
                            return
                    elif isinstance(sn_t, dict):
                        sn_t[sn_last] = value
                    else:
                        print("JSON Edit Key: can't set key on:", type(sn_t).__name__)
                        return
                    sn_dir = os.path.dirname(path)
                    if sn_dir:
                        os.makedirs(sn_dir, exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                except Exception as sn_e:
                    print("JSON Edit Key error:", sn_e)
            """
        segs = self._auto_key_segments()
        key_expr = _segments_to_expr(segs) if segs else self.inputs["Key"].python_value
        self.code = f"""
                    {self._editor}({self.inputs['Path'].python_value}, {key_expr}, {self.inputs['Value'].python_value})
                    {self.indent(self.outputs[0].python_value, 5)}
                    """

    def draw_node(self, context, layout):
        segs = self._auto_key_segments()
        if segs:
            layout.label(text=f"Key from link: {_segments_to_label(segs)}", icon="LINKED")
            return
        if self.inputs["Key"].is_linked:
            layout.label(text="Key from linked value", icon="LINKED")
            return
        col = layout.column(align=True)
        col.scale_y = 0.8
        col.label(text="item                 top key", icon="INFO")
        col.label(text="item.subitem      nested", icon="BLANK1")
        col.label(text="item.0.subitem   array item", icon="BLANK1")
        col.label(text="missing keys are created", icon="BLANK1")
