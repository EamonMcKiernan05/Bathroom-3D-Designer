"""Reconstruction pipeline for image-to-3D fragment-soup output (Rodin trial key).

Turns a shattered generated mesh into one continuous hull:
  fragment soup -> surface sample -> Poisson reconstruction -> density trim ->
  cluster keep (drop junk blobs) -> radial spike cut -> exact-dim scale ->
  smooth (Laplacian+Taubin) -> decimate -> GLB.

Usage:
  python rodin_recon.py <fragment_mesh.obj> <out.glb> <L mm> <W mm> <H mm>

Requires: open3d (pip install open3d)

VERIFIED 2026-08-06: recovers MACRO shape correctly (axis-aligned hull, cavity
open, correct slipper silhouette) but CANNOT fix the surface noise — the trial
key's fragmentation bakes in ~20 deg face-angle noise that smoothing can't
remove without destroying the shape. This pipeline is worth keeping: with a
PAID Rodin key (or TRELLIS/FAL output) the same steps produce catalogue-ready
meshes from single-image generations.
"""
import sys
import numpy as np
import open3d as o3d


def reconstruct(soup_path, out_path, length_m, width_m, height_m,
                density_percentile=8, cluster_keep_ratio=0.20,
                spike_radius=1.08, spike_min_height=0.25,
                smooth_rounds=3, target_tris=16000):
    soup = o3d.io.read_triangle_mesh(soup_path)
    soup.compute_vertex_normals()
    print("soup:", len(soup.vertices), "verts")

    pc = soup.sample_points_poisson_disk(number_of_points=120000)
    pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.04, max_nn=30))
    pc.orient_normals_consistent_tangent_plane(k=25)
    pts = np.asarray(pc.points)
    nrm = np.asarray(pc.normals)
    centroid = pts.mean(axis=0)
    outward = ((centroid - pts) * nrm).sum(axis=1)
    nrm[outward > 0] *= -1  # make normals point away from centroid (hull-ish objects)
    pc.normals = o3d.utility.Vector3dVector(nrm)

    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pc, depth=11, width=0, scale=1.15, linear_fit=True)
    print("poisson:", len(mesh.triangles), "tris")

    # trim reconstruction filler (low-density interpolated regions)
    densities = np.asarray(densities)
    mesh.remove_vertices_by_mask(
        (densities < np.percentile(densities, density_percentile)).tolist())

    # keep only well-sized connected clusters (drops absorbed-prop blobs)
    clusters = mesh.cluster_connected_triangles()
    tri_labels = np.asarray(clusters[0])
    counts = np.asarray(clusters[1])
    keep = counts[tri_labels] >= counts.max() * cluster_keep_ratio
    mesh.remove_triangles_by_mask((~keep).tolist())
    mesh.remove_unreferenced_vertices()

    # radial spike cut: junk fused to the hull sticks out beyond the ellipse
    vs = np.asarray(mesh.vertices)
    xs, ys, zs = vs[:, 0], vs[:, 1], vs[:, 2]
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    w = xs.max() - xs.min(); d = ys.max() - ys.min(); h = zs.max() - zs.min()
    z0 = zs.min()
    rad = np.sqrt(((xs - cx) / (w / 2)) ** 2 + ((ys - cy) / (d / 2)) ** 2)
    junk_v = (rad > spike_radius) & ((zs - z0) > h * spike_min_height)
    junk_face = junk_v[np.asarray(mesh.triangles)].any(axis=1)
    mesh.remove_triangles_by_mask(junk_face.tolist())
    mesh.remove_unreferenced_vertices()
    print("after spike cut:", len(mesh.triangles), "tris")

    # heavy smoothing: Laplacian + Taubin rounds (Taubin prevents shrinkage)
    for _ in range(smooth_rounds):
        mesh = mesh.filter_smooth_laplacian(
            number_of_iterations=12, filter_scope=o3d.geometry.FilterScope.Vertex)
        mesh = mesh.filter_smooth_taubin(number_of_iterations=8)

    # exact scale to real product dims, floor at z=0, centered on x/y
    vs = np.asarray(mesh.vertices)
    xs, ys, zs = vs[:, 0], vs[:, 1], vs[:, 2]
    sx = length_m / (xs.max() - xs.min())
    sy = width_m / (ys.max() - ys.min())
    sz = height_m / (zs.max() - zs.min())
    vs[:, 0] = (xs - (xs.min() + xs.max()) / 2) * sx
    vs[:, 1] = (ys - (ys.min() + ys.max()) / 2) * sy
    vs[:, 2] = (zs - zs.min()) * sz
    mesh.vertices = o3d.utility.Vector3dVector(vs)

    mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=target_tris)
    mesh.compute_vertex_normals()

    vs = np.asarray(mesh.vertices)
    print("FINAL mm:", round((vs[:, 0].max() - vs[:, 0].min()) * 1000),
          round((vs[:, 1].max() - vs[:, 1].min()) * 1000),
          round((vs[:, 2].max() - vs[:, 2].min()) * 1000))
    o3d.io.write_triangle_mesh(out_path, mesh)
    print("saved", out_path)


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print(__doc__)
        sys.exit(1)
    reconstruct(sys.argv[1], sys.argv[2],
                float(sys.argv[3]) / 1000, float(sys.argv[4]) / 1000, float(sys.argv[5]) / 1000)
