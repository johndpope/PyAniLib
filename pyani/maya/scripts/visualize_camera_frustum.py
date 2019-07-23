import maya.cmds as cmds
import math

# Version 1.0
#
# Makes geo to visualize camera frustums in Maya's viewport. Select camera and run script. Creates the geo, a lambert
# shader, and responds to change sin camera attributes


def apply_material(node):
    """
    Apply material to geo
    :param node: a transform node for the geo
    :return: the shader (not the shader group)
    """
    if cmds.objExists(node):
        shader = cmds.shadingNode('lambert', name="%s_lambert" % node, asShader=True)
        shaderSG = cmds.sets(name='%sSG' % shader, empty=True, renderable=True, noSurfaceShader=True)
        cmds.connectAttr('%s.outColor' % shader, '%s.surfaceShader' % shaderSG)
        cmds.sets(node, e=True, forceElement=shaderSG)
    return shader

# get all cameras selected
cameras_selected = cmds.ls(selection=True)

for camera_selected in cameras_selected:

    shape_node = cmds.listRelatives(camera_selected)

    # get transform and shape node, handles both the shape node selected and transform selected
    if shape_node:
        # the shape node is the first element in list
        camera_shape_node = [shape_node[0]]
        camera_transform_node = camera_selected[0]
    else:
        camera_shape_node = camera_selected
        camera_transform_node = cmds.listRelatives(camera_shape_node, parent=True)[0]

    # make sure its a camera
    if cmds.objectType(camera_shape_node, isType="camera"):
        # get children to check for existing frustum
        children = cmds.listRelatives(camera_selected)
        for child in children:
            if 'Frustum' in child:
                cmds.delete(child)

        # get properties
        focalLength = cmds.getAttr(camera_shape_node[0] + ".focalLength")
        horizontalAperture = cmds.getAttr(camera_shape_node[0] + ".cameraAperture")[0][0]
        verticalAperture = cmds.getAttr(camera_shape_node[0] + ".cameraAperture")[0][1]
        nearClipping = cmds.getAttr(camera_shape_node[0] + ".nearClipPlane")
        farClipping = cmds.getAttr(camera_shape_node[0] + ".farClipPlane")
        adjacent = focalLength
        opposite = horizontalAperture * .5 * 25.4
        horizontalFOV = math.degrees(math.atan(opposite / adjacent)) * 2
        plane = horizontalAperture * 25.4
        nearScaleValue = nearClipping * plane / focalLength
        farScaleValue = farClipping * plane / focalLength

        print "---- Camera Attributes:\n\tfocal length: %s\n\thorizontal aperture: %s" % (
            focalLength, horizontalAperture
        )
        print "---- Right Triangle Values:\n\tadjacent: %s\n\topposite: %s" % (adjacent, opposite)
        print "\tcomputed horizontal FOV: %s" % (horizontalFOV)
        print "---- Lens:\n\tprojection ratio: %s" % (plane / focalLength)

        # name for frustum geo shape node
        frustum_name = camera_shape_node[0].replace("Shape", "Frustum")
        # the geo for the frustum
        myCube = cmds.polyCube(w=1, h=1, d=farClipping - nearClipping, sy=1, sx=1, sz=1, ax=[0, 1, 0], ch=1,
                               name=frustum_name)
        # set the dimensions
        cmds.setAttr(myCube[0] + ".translateZ", nearClipping + (farClipping - nearClipping) * .5)
        cmds.makeIdentity(apply=True, t=1, r=1, s=1, n=0, pn=1);
        cmds.setAttr(myCube[0] + ".rotatePivotZ", 0)
        cmds.setAttr(myCube[0] + ".scalePivotZ", 0)
        cmds.setAttr(myCube[0] + ".rotateY", 180)
        cmds.move(0, 0, 0, myCube[0] + ".f[2]", absolute=True)
        cmds.scale(nearScaleValue, 0, 1, myCube[0] + ".f[2]", pivot=[0, 0, 0])

        # now add attributes for later scaling geo if properities like far clipping change
        # init far clip is the initial far clip value when geo created. new_far_clip_ratio is the new far clip value
        # / by the initial far clip value. This is used to control the depth of the geo, ie. z direction
        if not cmds.attributeQuery('init_far_clip', node=camera_shape_node[0], ex=True):
            cmds.addAttr(camera_shape_node[0], shortName='ifc', longName='init_far_clip', attributeType="float")
        if not cmds.attributeQuery('new_far_clip_ratio', node=camera_shape_node[0], ex=True):
            cmds.addAttr(camera_shape_node[0], shortName='nfcr', longName='new_far_clip_ratio', attributeType="float")
            cmds.expression(s="%s.new_far_clip_ratio = %s.farClipPlane / %s.init_far_clip" % (
                camera_shape_node[0], camera_shape_node[0], camera_shape_node[0]),
                            n="%s_far_clip_expr" % camera_shape_node[0])
        cmds.setAttr(camera_shape_node[0] + ".init_far_clip", farClipping)

        scaleX = "%s.new_far_clip_ratio*%s.init_far_clip*%s.horizontalFilmAperture*25.4/%s.focalLength" % (
            camera_shape_node[0], camera_shape_node[0], camera_shape_node[0], camera_shape_node[0])
        scaleY = "%s.new_far_clip_ratio*%s.init_far_clip*%s.verticalFilmAperture*25.4/%s.focalLength" % (
            camera_shape_node[0], camera_shape_node[0], camera_shape_node[0], camera_shape_node[0])

        cmds.expression(s="%s.scaleX = %s;%s.scaleY = %s;%s.scaleZ = %s.new_far_clip_ratio" % (
            myCube[0], scaleX, myCube[0], scaleY, myCube[0], camera_shape_node[0]), n="%s_Frustum_expr" % myCube[0])

        cmds.parent(myCube, camera_selected, relative=True)

        # now add material
        frustum_transform_node = cmds.ls(frustum_name)[0]
        frustum_transform_node = cmds.listRelatives(frustum_transform_node)[0]
        shader = apply_material(frustum_transform_node)
        opacity = 0.75
        cmds.setAttr('%s.transparency' % shader, opacity, opacity, opacity)

    else:
        print "ERROR: {0} is not a camera and will be skipped.".format(shape_node)
