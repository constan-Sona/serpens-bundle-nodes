import bpy
from ..base_node import SN_ScriptingBaseNode
from ._bundle_common import resolve_struct, matching_input_portals


# (tree, name) of Separate nodes currently inside evaluate(); breaks cyclic
# re-evaluation. Module-level so it resets on reload and is never persisted.
_EVALUATING = set()


class SN_SeparateBundleNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_SeparateBundleNode"
    bl_label = "Separate Bundle"
    bl_width_default = 200
    node_color = (0.584, 0.294, 0.412)  # #954B69

    # Name of the Combine Bundle node feeding this one. Named ref_<collection_key>
    # so Serpens' trigger_ref_update finds it (collection_key == bl_idname).
    ref_SN_CombineBundleNode: bpy.props.StringProperty(
        name="Source",
        description="The Combine Bundle node this one mirrors",
    )

    def on_create(self, context):
        self._add_input("SN_BundleSocket", "Bundle")

    # --- structure resolution ---------------------------------------------

    def _desired_struct(self):
        """Nested struct of the bundle feeding our input (any source kind), or []."""
        return resolve_struct(self.inputs.get("Bundle")) or []

    def struct_for_output(self, out):
        """Object struct of our output named like `out` (for nested Separate chains).
        Returns None for array outputs (those go through a Loop For Bundle)."""
        for name, _idn, children, _src, arr in self._desired_struct():
            if name == out.name:
                return None if arr else children
        return None

    def element_struct_for_output(self, out):
        """Element struct for one of our ARRAY outputs (used by Loop For Bundle)."""
        for name, _idn, children, _src, arr in self._desired_struct():
            if name == out.name:
                return children if arr else None
        return None

    def _desired_sig(self):
        return [(name, idn) for name, idn, _c, _s, _a in self._desired_struct()]

    def _current_sig(self):
        return [(out.name, out.bl_idname) for out in self.outputs]

    def _resolve_combine(self, socket, depth=0):
        """Finds the root Combine feeding `socket`, through portals and nested
        Separates (used for the ref link and cycle detection). None for JSON sources."""
        if not socket or depth > 64:
            return None
        from_out = socket.from_socket()
        if not from_out:
            return None
        node = from_out.node
        if node.bl_idname == "SN_CombineBundleNode":
            return node
        if node.bl_idname == "SN_SeparateBundleNode":
            return self._resolve_combine(node.inputs.get("Bundle"), depth + 1)
        if node.bl_idname == "SN_BundlePortalNode" and node.direction == "OUTPUT":
            for ip in matching_input_portals(node.var_name):
                found = self._resolve_combine(ip.inputs[0], depth + 1)
                if found:
                    return found
        return None

    def get_source(self):
        """The root Combine feeding us (through portals / nested separates), or None."""
        return self._resolve_combine(self.inputs.get("Bundle"))

    def creates_cycle(self):
        """True if any output eventually feeds back into our source Combine."""
        source = self.get_source()
        if not source:
            return False
        source_name = source.name
        visited = set()
        stack = [self]
        while stack:
            node = stack.pop()
            if node.name in visited:
                continue
            visited.add(node.name)
            # data arriving at an INPUT Bundle Portal continues at its OUTPUT twins
            if node.bl_idname == "SN_BundlePortalNode" and node.direction == "INPUT":
                for ntree in bpy.data.node_groups:
                    if ntree.bl_idname == "ScriptingNodesTree":
                        for n in ntree.nodes:
                            if (n.bl_idname == "SN_BundlePortalNode"
                                    and n.direction == "OUTPUT"
                                    and n.var_name == node.var_name
                                    and n.name not in visited):
                                stack.append(n)
            for out in node.outputs:
                for to_socket in out.to_sockets():
                    tn = to_socket.node
                    if tn.name == source_name:
                        return True
                    if tn.name not in visited:
                        stack.append(tn)
        return False

    # --- socket mirroring --------------------------------------------------

    def _mirror_socket(self, src, dst):
        """Copies type-specific extras (subtype / vector size / enum items) when we
        have the original source socket (Combine). No-op for data-only sources (JSON)."""
        if src is None:
            return
        try:
            if src.subtype in dst.subtypes:
                dst.subtype = src.subtype
        except Exception:
            pass
        if hasattr(dst, "size") and hasattr(src, "size"):
            try:
                dst.size = src.size
            except Exception:
                pass
        if hasattr(src, "custom_items") and hasattr(dst, "custom_items"):
            try:
                dst.custom_items_editable = False
                dst.custom_items.clear()
                for item in src.custom_items:
                    new = dst.custom_items.add()
                    new.name = item.name
            except Exception:
                pass

    def _rebuild(self, struct):
        """Full rebuild of the outputs from a struct, preserving downstream links by name."""
        old_links = {out.name: out.to_sockets() for out in self.outputs if out.is_linked}
        self.disable_evaluation = True
        try:
            for i in range(len(self.outputs) - 1, -1, -1):
                self.outputs.remove(self.outputs[i])
            for name, idn, _children, src, _arr in (struct or []):
                new = self._add_output(idn, name)
                new.set_name_silent(name)
                self._mirror_socket(src, new)
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

    def sync_structure(self):
        """Topology-safe entry point that makes the outputs mirror the source.
        Returns True if it changed anything. Do NOT call from inside evaluate()."""
        struct = self._desired_struct()
        # keep the ref pointed at the root Combine (if any) for trigger_ref_update
        source = self.get_source()
        self.ref_SN_CombineBundleNode = source.name if source else ""

        desired = [(n, idn) for n, idn, _c, _s, _a in struct]
        current = self._current_sig()
        if desired == current:
            return False

        # Pure rename(s): same count and same types in order -> rename in place so
        # downstream links are preserved.
        same_types = [d[1] for d in desired] == [c[1] for c in current]
        if len(desired) == len(current) and same_types:
            for i, (name, _idname) in enumerate(desired):
                if self.outputs[i].name != name:
                    self.outputs[i].set_name_silent(name)
            self._evaluate(bpy.context)
            return True

        # Structural change (add / remove / retype) -> rebuild, links kept by name.
        self._rebuild(struct)
        return True

    def _deferred_sync(self):
        self["_sync_pending"] = False
        try:
            self.sync_structure()
        except Exception:
            pass
        return None  # one-shot

    def _schedule_sync(self):
        if not self.get("_sync_pending", False):
            self["_sync_pending"] = True
            bpy.app.timers.register(self._deferred_sync, first_interval=0.0)

    # --- triggers ----------------------------------------------------------

    def on_ref_update(self, node, data=None):
        # The source Combine told us it changed -> resync (topology-safe here).
        if node.bl_idname == "SN_CombineBundleNode" and node.name == self.ref_SN_CombineBundleNode:
            self.sync_structure()

    def on_link_insert(self, from_socket, to_socket, is_output):
        if is_output:
            return
        if to_socket == self.inputs.get("Bundle"):
            self.sync_structure()

    def on_link_remove(self, from_socket, to_socket, is_output):
        if is_output:
            return
        if to_socket == self.inputs.get("Bundle"):
            self.ref_SN_CombineBundleNode = ""
            self.sync_structure()

    # --- code generation ---------------------------------------------------

    def evaluate(self, context):
        # Re-entrancy guard: stop a feedback loop from re-evaluating us endlessly.
        key = (self.node_tree.name, self.name)
        if key in _EVALUATING:
            return
        _EVALUATING.add(key)
        try:
            # Safety net: if the structure drifted from the source, fix it next tick.
            if self._desired_sig() != self._current_sig():
                self._schedule_sync()

            bundle = self.inputs["Bundle"].python_value
            # A cycle (an output feeding back into the source Combine) would make the
            # python_value grow forever -> output None instead. Blender also flags the
            # offending link in red.
            if self.inputs["Bundle"].is_linked and len(self.outputs) and not self.creates_cycle():
                arr_names = {n for n, _i, _c, _s, a in self._desired_struct() if a}
                for out in self.outputs:
                    # `or {}` keeps it crash-proof at runtime: a missing key / missing
                    # parent object just yields None instead of erroring.
                    if out.name in arr_names:
                        # array bundle: forward the whole list (iterate w/ Loop For Bundle)
                        out.python_value = f'(({bundle}) or {{}}).get("{out.name}", [])'
                    else:
                        out.python_value = f'(({bundle}) or {{}}).get("{out.name}", None)'
            else:
                for out in self.outputs:
                    out.reset_value()
        finally:
            _EVALUATING.discard(key)

    def draw_node(self, context, layout):
        if not self.inputs["Bundle"].is_linked:
            layout.label(text="Connect a bundle source", icon="INFO")
        else:
            if self.creates_cycle():
                row = layout.row()
                row.alert = True
                row.label(text="Output loops back into the bundle!", icon="ERROR")
            elif not len(self.outputs):
                layout.label(text="Empty or unknown bundle", icon="INFO")
            op = layout.operator("sn.resync_bundle", text="Refresh", icon="FILE_REFRESH")
            op.node = self.name


class SN_OT_ResyncBundle(bpy.types.Operator):
    bl_idname = "sn.resync_bundle"
    bl_label = "Refresh Bundle"
    bl_description = "Rebuild the outputs to match the connected bundle source"
    bl_options = {"REGISTER", "INTERNAL"}

    node: bpy.props.StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        node = context.space_data.edit_tree.nodes[self.node]
        node.sync_structure()
        return {"FINISHED"}
