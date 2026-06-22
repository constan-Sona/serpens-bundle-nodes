import bpy
from random import uniform
from ..base_node import SN_ScriptingBaseNode


# portals whose label needs a deferred refresh (draw can't write ID data)
_LBL_PENDING = set()


def _deferred_label(tree_name, node_name):
    def run():
        _LBL_PENDING.discard((tree_name, node_name))
        try:
            nt = bpy.data.node_groups.get(tree_name)
            n = nt.nodes.get(node_name) if nt else None
            if n:
                n._refresh_label()
        except Exception:
            pass
        return None  # one-shot
    return run


class SN_BundlePortalNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_BundlePortalNode"
    bl_label = "Bundle Portal"
    bl_width_default = 150
    node_color = (0.10, 0.18, 0.22)

    def _matching(self, direction):
        """Yields bundle portals with the same var_name and the given direction."""
        for ntree in bpy.data.node_groups:
            if ntree.bl_idname == "ScriptingNodesTree":
                for node in ntree.nodes:
                    if (node.bl_idname == "SN_BundlePortalNode"
                            and node != self
                            and node.direction == direction
                            and node.var_name == self.var_name):
                        yield node

    def update_direction(self, context):
        self.inputs[0].set_hide(self.direction == "OUTPUT")
        self.outputs[0].set_hide(self.direction == "INPUT")
        if self.direction == "OUTPUT":
            self.sync_portals()
        self._evaluate(context)

    direction: bpy.props.EnumProperty(
        name="Direction",
        description="The direction this portal goes in",
        items=[("INPUT", "In", "Input", "BACK", 0),
               ("OUTPUT", "Out", "Output", "FORWARD", 1)],
        update=update_direction,
    )

    def sync_portals(self):
        """INPUT portals rename their connected OUTPUT portals so the link survives a
        rename; OUTPUT portals match the color of their target INPUT portal."""
        try:
            prev = self.get("_prev_var_name", self.var_name)

            # INPUT: relink every OUTPUT that still carries the previous name
            if self.direction == "INPUT" and prev != self.var_name:
                for ntree in bpy.data.node_groups:
                    if ntree.bl_idname == "ScriptingNodesTree":
                        for other in ntree.nodes:
                            if (other.bl_idname == "SN_BundlePortalNode"
                                    and other != self
                                    and other.direction == "OUTPUT"
                                    and other.var_name == prev):
                                other.var_name = self.var_name        # keep the link
                                if other.auto_label:                  # respect custom names
                                    other.label = self.var_name

            # OUTPUT: match the color of our target INPUT
            elif self.direction == "OUTPUT":
                for other in self._matching("INPUT"):
                    self.custom_color = other.custom_color
                    break

            self["_prev_var_name"] = self.var_name
        except Exception:
            pass

    def update_var_name(self, context=None):
        if self.auto_label:
            self.label = self.var_name
        self.sync_portals()
        self._evaluate(context)

    var_name: bpy.props.StringProperty(
        name="Name",
        description="The identifier that links this portal to another portal",
        update=update_var_name,
    )

    def update_custom_color(self, context):
        self.color = self.custom_color
        if self.direction == "INPUT":
            for node in self._matching("OUTPUT"):
                node.custom_color = self.custom_color

    custom_color: bpy.props.FloatVectorProperty(
        name="Color", size=3, min=0, max=1, subtype="COLOR",
        description="The color of this node",
        update=update_custom_color,
    )

    def update_auto_label(self, context=None):
        # when re-enabled, snap the label back to the automatic value
        if self.auto_label:
            self._refresh_label()

    auto_label: bpy.props.BoolProperty(
        name="Auto Name",
        description="Name this portal automatically from its variable / connection. "
                    "Disable to type a custom label that won't be overwritten",
        default=True,
        update=update_auto_label,
    )

    def on_create(self, context):
        self._add_input("SN_BundleSocket", "Bundle")
        self._add_output("SN_BundleSocket", "Bundle")
        self.outputs[0].set_hide(True)  # default direction is INPUT
        if not self.var_name:
            self.var_name = self.uuid
        self["_prev_var_name"] = self.var_name
        self.label = self.var_name
        self.use_custom_color = True
        self.custom_color = (uniform(0, 1), uniform(0, 1), uniform(0, 1))

    def evaluate(self, context):
        if self.direction == "INPUT":
            # nudge the connected OUTPUT portals so they pick up our new value
            for node in self._matching("OUTPUT"):
                node._evaluate(bpy.context)
        else:
            # copy the matching INPUT portal's incoming bundle
            for node in self._matching("INPUT"):
                self.outputs[0].python_value = node.inputs[0].python_value
                return
            self.outputs[0].reset_value()

    def _desired_label(self):
        """OUT portals show where they are connected ('name → Target'); IN portals and
        unconnected OUT portals just show the name. (Same behavior as the native Portal.)"""
        desired = self.var_name
        if self.direction == "OUTPUT" and len(self.outputs):
            targets = [l.to_socket.node for l in self.outputs[0].links if l.to_socket]
            if targets:
                t = targets[0]
                desired = f"{self.var_name} → {t.label or t.bl_label}"
                if len(targets) > 1:
                    desired += f" +{len(targets) - 1}"
        return desired

    def _refresh_label(self):
        # only call from safe contexts (updates/timers) — never from draw
        if not self.auto_label:
            return  # custom label -> leave it alone
        desired = self._desired_label()
        if self.label != desired:
            self.label = desired

    def on_node_update(self):
        # seed the rename tracker for portals created before this existed
        if "_prev_var_name" not in self:
            self["_prev_var_name"] = self.var_name
        self._refresh_label()

    def draw_node(self, context, layout):
        # draw can't write ID data -> if the label is stale, fix it on a timer
        if self.auto_label and self.label != self._desired_label():
            key = (self.node_tree.name, self.name)
            if key not in _LBL_PENDING:
                _LBL_PENDING.add(key)
                bpy.app.timers.register(_deferred_label(*key), first_interval=0.0)
        layout.prop(self, "direction", expand=True)
        row = layout.row(align=True)
        split = row.split(factor=0.55, align=True)
        split.prop(self, "var_name", text="")
        sub = split.row(align=True)
        sub.prop(self, "custom_color", text="")
        sub.operator("sn.portal_connections", text="", icon="VIEWZOOM").node = self.name
        # reuse the existing portal reset operator (needs var_name + custom_color + static_uid)
        sub.operator("sn.reset_portal", text="", icon="LOOP_BACK").node = self.name

        # auto vs. custom naming
        name_row = layout.row(align=True)
        name_row.prop(self, "auto_label", text="Auto Name")
        if not self.auto_label:
            layout.prop(self, "label", text="Label")
