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



class SN_PortalNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_PortalNode"
    bl_label = "Portal"
    bl_width_default = 100
    
    def update_connected_portals(self, context=None):
        if self.direction == "INPUT":
            for ntree in bpy.data.node_groups:
                if ntree.bl_idname == "ScriptingNodesTree":
                    for node in ntree.node_collection(self.bl_idname).nodes:
                        if node.direction == "OUTPUT" and node.var_name == self.var_name:
                            node.var_name = self.var_name

    def update_direction(self, context):
        self.inputs[0].set_hide(self.direction == "OUTPUT")
        self.outputs[0].set_hide(self.direction == "INPUT")
        # If switched to output, try to match the color of the target
        if self.direction == "OUTPUT":
            self.update_var_name(context)
        else:
            self._evaluate(context)
    
    direction: bpy.props.EnumProperty(name="Direction",
                                description="The direction this portal goes in",
                                items=[("INPUT", "In", "Input", "BACK", 0),
                                       ("OUTPUT", "Out", "Output", "FORWARD", 1)],
                                update=update_direction)

    def sync_portals(self):
        try:
            prev = self.get("_prev_var_name", self.var_name)
            
            # If we are an INPUT, update our children's names
            if self.direction == "INPUT" and prev != self.var_name:
                for ntree in bpy.data.node_groups:
                    if ntree.bl_idname == "ScriptingNodesTree":
                        coll = ntree.node_collection(self.bl_idname)
                        for other in coll.nodes:
                            if other and other.direction == "OUTPUT" and other.var_name == prev:
                                other.var_name = self.var_name        # keep the link
                                if other.auto_label:                  # respect custom names
                                    other.label = self.var_name

            # If we are an OUTPUT, match the color of our target
            elif self.direction == "OUTPUT":
                for ntree in bpy.data.node_groups:
                    if ntree.bl_idname == "ScriptingNodesTree":
                        coll = ntree.node_collection(self.bl_idname)
                        for other in coll.nodes:
                            if other and other.direction == "INPUT" and other.var_name == self.var_name:
                                self.custom_color = other.custom_color
                                break
            
            self["_prev_var_name"] = self.var_name
        except:
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
        # update own color
        self.color = self.custom_color
        # update connected color
        if self.direction == "INPUT":
            for ntree in bpy.data.node_groups:
                if ntree.bl_idname == "ScriptingNodesTree":
                    for node in ntree.node_collection(self.bl_idname).nodes:
                        if node.direction == "OUTPUT" and node.var_name == self.var_name:
                            node.custom_color = self.custom_color
    
    custom_color: bpy.props.FloatVectorProperty(name="Color",
                                size=3, min=0, max=1, subtype="COLOR",
                                description="The color of this node",
                                update=update_custom_color)

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
        self.add_data_input()
        out = self.add_data_output()
        out.changeable = True
        out.set_hide(True)
        # Only assign a new UUID if we don't have a name (e.g. fresh node vs duplicated node)
        if not self.var_name:
            self.var_name = self.uuid
        self["_prev_var_name"] = self.var_name
        self.label = self.var_name
        self.custom_color = (uniform(0, 1), uniform(0, 1), uniform(0, 1))

    def evaluate(self, context):
        if self.direction == "INPUT":
            self.update_connected_portals()
        elif self.direction == "OUTPUT":
            for ntree in bpy.data.node_groups:
                if ntree.bl_idname == "ScriptingNodesTree":
                    for node in ntree.node_collection(self.bl_idname).nodes:
                        if node.direction == "INPUT" and node.var_name == self.var_name:
                            self.outputs[0].python_value = node.inputs[0].python_value
                            return
            self.outputs[0].reset_value()
    
    def _desired_label(self):
        """OUT portals show where they are connected ('name → Target'); IN portals and
        unconnected OUT portals just show the name."""
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
        sub.operator("sn.reset_portal", text="", icon="LOOP_BACK").node = self.name

        # auto vs. custom naming
        name_row = layout.row(align=True)
        name_row.prop(self, "auto_label", text="Auto Name")
        if not self.auto_label:
            layout.prop(self, "label", text="Label")