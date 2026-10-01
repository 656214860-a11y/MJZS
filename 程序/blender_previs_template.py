"""Run with Blender --background --python this_file -- config.json."""
import bpy, json, sys, math
from pathlib import Path
from mathutils import Vector

def build(c):
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene
    scene.render.engine='BLENDER_WORKBENCH'
    scene.display.shading.light='STUDIO'
    scene.display.shading.color_type='SINGLE'
    scene.display.shading.single_color=(.72,.72,.72)
    scene.render.resolution_x,scene.render.resolution_y=c['size']
    scene.render.resolution_percentage=100
    scene.render.fps=24; scene.frame_end=max(2,round(c['seconds']*24))
    def part(name,loc,scale,parent=None):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,location=loc)
        o=bpy.context.object;o.name=name;o.scale=scale
        if parent:o.parent=parent
        return o
    count=len(c['characters']) or 1
    for i,name in enumerate(c['characters'] or ['人物1']):
        actor=bpy.data.objects.new(str(name),None);scene.collection.objects.link(actor)
        actor.location=((i-(count-1)/2)*1.5,0,0)
        part(str(name)+'_头',(0,0,1.65),(.17,.17,.21),actor)
        part('躯干',(0,0,1.15),(.25,.15,.35),actor)
        arms=[]; legs=[]
        for side in (-1,1):
            arms.append(part('手臂',(side*.32,0,1.15),(.09,.09,.34),actor))
            legs.append(part('腿',(side*.13,0,.45),(.11,.12,.43),actor))
        action=c['action']
        for frame in range(1,scene.frame_end+1,4):
            t=(frame-1)/(scene.frame_end-1)
            if action=='走路':
                actor.location.y=-2*t
                for j,limb in enumerate(legs+arms):
                    limb.rotation_euler.x=math.sin(t*c['seconds']*7+(j%2)*math.pi)*.35
                    limb.keyframe_insert('rotation_euler',frame=frame)
            if action=='转身':actor.rotation_euler.z=math.pi*.5*t
            if action=='抬手指向':arms[1].rotation_euler.x=-math.pi*.5*min(1,t*3);arms[1].keyframe_insert('rotation_euler',frame=frame)
            actor.keyframe_insert('location',frame=frame);actor.keyframe_insert('rotation_euler',frame=frame)
    bpy.ops.mesh.primitive_plane_add(size=30)
    bpy.context.object.name='地面'
    bpy.ops.object.camera_add(location=(0,-max(7,count*2.4),3.2))
    camera=bpy.context.object;scene.camera=camera;camera.data.lens=40
    start=camera.location.copy()
    for frame in (1,scene.frame_end):
        t=(frame-1)/(scene.frame_end-1);camera.location=start.copy()
        if c['camera']=='推进':camera.location.y+=2*t
        if c['camera']=='拉远':camera.location.y-=2*t
        if c['camera']=='横移':camera.location.x+=2*t
        if c['camera']=='跟随':camera.location.y-=2*t
        target=Vector((0,-2*t if c['camera']=='跟随' else 0,1))
        camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.keyframe_insert('location',frame=frame);camera.keyframe_insert('rotation_euler',frame=frame)
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=c['blend'])
    if c.get('render'):
        scene.render.image_settings.file_format='PNG'
        scene.render.filepath=str(Path(c['frames'])/'frame_')
        bpy.ops.render.render(animation=True)

if __name__=='__main__':
    build(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8')))
