"""Shared helpers for the Bundle node family.

A "struct" describes the contents of a bundle as a nested list of entries:
    [(name, bl_idname, children_or_None, src_socket_or_None, is_array), ...]
- name:        the key / socket name
- bl_idname:   the Serpens socket type for that value
- children:    for a nested bundle (dict OR array-of-objects), the struct of its contents; else None
- src_socket:  the original source socket if available (used to mirror subtype / vector
               size / enum items); None when it comes from data (e.g. JSON) with no socket.
- is_array:    True when the value is an array of objects exposed as a Bundle. The bundle then
               represents the FIRST element, so its value is read as (list or [{}])[0].
"""

import bpy

# Register the "Bundle" entry in Serpens' icon map at import time so changeable
# sockets can offer the Bundle type in their dropdown (runtime dict insert only,
# no native file is modified).
try:
    from ...addon.properties.settings.settings import property_icons
    property_icons.setdefault("Bundle", "PACKAGE")
    property_icons.setdefault("Bundle Array", "MOD_ARRAY")
except Exception:
    pass

# both socket idnames belong to the bundle wire family (same bl_label "Bundle")
BUNDLE_IDNAMES = ("SN_BundleSocket", "SN_BundleArraySocket")


class SN_OT_PortalConnections(bpy.types.Operator):
    """Lists every portal sharing this portal's name (any tree) and jumps to it,
    like the operator loupe. Works for the native Portal and the Bundle Portal."""
    bl_idname = "sn.portal_connections"
    bl_label = "Portal Connections"
    bl_description = "Show the portals connected to this one and jump to them"
    bl_options = {"REGISTER", "INTERNAL"}

    node: bpy.props.StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        tree = context.space_data.edit_tree
        node = tree.nodes.get(self.node)
        if node is None:
            return {"CANCELLED"}
        matches = []
        for ntree in bpy.data.node_groups:
            if ntree.bl_idname == "ScriptingNodesTree":
                for n in ntree.nodes:
                    if (n.bl_idname == node.bl_idname
                            and not (ntree == tree and n.name == node.name)
                            and n.var_name == node.var_name):
                        matches.append((ntree.name, n.name, n.direction, n.label or n.name))
        if not matches:
            self.report({"INFO"}, f"No other portals named '{node.var_name}'")
            return {"CANCELLED"}
        if len(matches) == 1:
            t, nname, _d, _l = matches[0]
            bpy.ops.sn.find_node(node_tree=t, node=nname)
            return {"FINISHED"}
        def draw_menu(menu, _context):
            for t, nname, dirn, label in matches:
                icon = "BACK" if dirn == "INPUT" else "FORWARD"
                op = menu.layout.operator("sn.find_node", text=f"{t}  ·  {label}", icon=icon)
                op.node_tree = t
                op.node = nname
        context.window_manager.popup_menu(draw_menu, title=f"Portals '{node.var_name}' ({len(matches)})", icon="VIEWZOOM")
        return {"FINISHED"}


def socket_idname_for_value(v):
    """Maps a python/json value to the Serpens socket type that fits it."""
    if isinstance(v, bool):
        return "SN_BooleanSocket"
    if isinstance(v, int):
        return "SN_IntegerSocket"
    if isinstance(v, float):
        return "SN_FloatSocket"
    if isinstance(v, str):
        return "SN_StringSocket"
    if isinstance(v, dict):
        return "SN_BundleSocket"
    if isinstance(v, (list, tuple)):
        return "SN_ListSocket"
    return "SN_DataSocket"  # None / unknown


def _entry_from_value(name, v):
    """One struct entry for a key/value.
    - object (dict) -> a Bundle (children = its keys), is_array=False
    - array of objects -> a Bundle holding the whole LIST (children = the element shape),
      is_array=True; iterate it with a 'Loop For Bundle' to get one item bundle per element
    - flat array / scalar -> its plain socket type."""
    if isinstance(v, dict):
        return (name, "SN_BundleSocket", struct_from_data(v), None, False)
    if isinstance(v, (list, tuple)) and len(v) and isinstance(v[0], dict):
        return (name, "SN_BundleArraySocket", struct_from_data(v[0]), None, True)
    return (name, socket_idname_for_value(v), None, None, False)


def struct_from_data(data):
    """Builds a nested struct from a parsed-JSON (or dict) value."""
    res = []
    if isinstance(data, dict):
        for k, v in data.items():
            res.append(_entry_from_value(str(k), v))
    return res


def matching_input_portals(var_name):
    """Yields INPUT Bundle Portals with the given var_name across all trees."""
    for ntree in bpy.data.node_groups:
        if ntree.bl_idname == "ScriptingNodesTree":
            for node in ntree.nodes:
                if (node.bl_idname == "SN_BundlePortalNode"
                        and node.direction == "INPUT"
                        and node.var_name == var_name):
                    yield node


def resolve_struct(socket, depth=0):
    """Returns the nested struct of the bundle feeding `socket`, or None if unknown.
    Hops reroutes (via from_socket), Bundle Portals, Combine, JSON and nested Separate
    bundle outputs."""
    if socket is None or depth > 64:
        return None
    from_out = socket.from_socket()
    if not from_out:
        return None
    node = from_out.node
    idn = node.bl_idname
    if idn == "SN_CombineBundleNode":
        res = []
        for i in node.inputs:
            if i.dynamic:
                continue
            if i.bl_idname in BUNDLE_IDNAMES:
                child = resolve_struct(i, depth + 1)
                if child is None:
                    # maybe an ARRAY bundle is plugged in -> children = element shape
                    elem = resolve_element_struct(i, depth + 1)
                    idn = "SN_BundleArraySocket" if elem is not None else i.bl_idname
                    res.append((i.name, idn, elem, i, elem is not None))
                else:
                    res.append((i.name, "SN_BundleSocket", child, i, False))
            else:
                res.append((i.name, i.bl_idname, None, i, False))
        return res
    if idn == "SN_BundlePortalNode" and node.direction == "OUTPUT":
        for ip in matching_input_portals(node.var_name):
            r = resolve_struct(ip.inputs[0], depth + 1)
            if r is not None:
                return r
        return None
    # any bundle-producing node (JSON, Separate, the loop nodes...) implements this
    if hasattr(node, "struct_for_output"):
        return node.struct_for_output(from_out)
    return None


def resolve_element_struct(socket, depth=0):
    """For an ARRAY bundle feeding `socket`, returns the (object) struct of ONE element,
    or None. Used by 'Loop For Bundle' to type its per-item output."""
    if socket is None or depth > 64:
        return None
    from_out = socket.from_socket()
    if not from_out:
        return None
    node = from_out.node
    idn = node.bl_idname
    if idn == "SN_BundlePortalNode" and node.direction == "OUTPUT":
        for ip in matching_input_portals(node.var_name):
            r = resolve_element_struct(ip.inputs[0], depth + 1)
            if r is not None:
                return r
        return None
    if hasattr(node, "element_struct_for_output"):
        return node.element_struct_for_output(from_out)
    return None


def resync_all_separate_bundles():
    """Re-syncs every Separate Bundle until stable (handles deep JSON / portal chains)."""
    for _ in range(8):
        changed = False
        for ntree in bpy.data.node_groups:
            if ntree.bl_idname == "ScriptingNodesTree":
                for node in ntree.nodes:
                    if node.bl_idname == "SN_SeparateBundleNode":
                        try:
                            if node.sync_structure():
                                changed = True
                        except Exception:
                            pass
        if not changed:
            break
