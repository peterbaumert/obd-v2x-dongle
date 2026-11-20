"""Preview images of the case (pyvista / VTK, off-screen)."""
import numpy as np
import pyvista as pv

pv.OFF_SCREEN = True


def mesh(shape, offset=(0, 0, 0), tol=0.05):
    verts, faces = shape.tessellate(tol, 0.2)
    v = np.array([[p.X, p.Y, p.Z] for p in verts]) + np.array(offset)
    f = np.hstack([np.full((len(faces), 1), 3), np.array(faces)]).ravel()
    return pv.PolyData(v, f)


def _shot(path, items, camera, size=(1100, 850)):
    p = pv.Plotter(off_screen=True, window_size=size)
    p.set_background('white')
    for m, color, opacity in items:
        p.add_mesh(m, color=color, opacity=opacity, smooth_shading=False, specular=0.2)
    p.camera_position = camera
    p.reset_camera()
    p.camera.zoom(1.25)
    p.enable_anti_aliasing('ssaa')
    p.screenshot(str(path))
    p.close()


def render(bottom, lid, plug, out, board=None):
    b, l, pl = mesh(bottom), mesh(lid), mesh(plug)
    case = '#5b7fb5'
    lidc = '#7f9fd0'
    plugc = '#2b2b2b'
    iso = [(-40, -230, 110), (126, -85, 3), (0, 0, 1)]
    _shot(out / 'case_closed.png', [(b, case, 1), (l, lidc, 1), (pl, plugc, 1)],
          [(-10, 20, 110), (126, -85, 3), (0, 0, 1)])
    _shot(out / 'case_closed_rear.png', [(b, case, 1), (l, lidc, 1), (pl, plugc, 1)],
          [(240, -230, -60), (126, -85, 3), (0, 0, 1)])
    items = [(b, case, 1), (mesh(lid, (0, 0, 40)), lidc, 1), (pl, plugc, 1)]
    if board is not None:
        items.insert(1, (mesh(board, tol=0.1), '#2e7d32', 1))
    _shot(out / 'case_open.png', items, iso)
    _shot(out / 'case_bottom_shell.png', [(b, case, 1)], [(126, -95, 200), (126, -85, 0), (0, 1, 0)])
    _shot(out / 'case_lid_inside.png', [(l, lidc, 1)], [(126, -95, -200), (126, -85, 10), (0, 1, 0)])
