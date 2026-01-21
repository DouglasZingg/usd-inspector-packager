from __future__ import annotations

from pathlib import Path

from pxr import Usd, UsdGeom, UsdShade, Sdf


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_dummy_texture(path: Path) -> None:
    ensure_dir(path.parent)
    path.write_bytes(b"demo texture placeholder\n")


def make_sample_usda(out_path: Path) -> None:
    stage = Usd.Stage.CreateNew(str(out_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

    UsdGeom.Xform.Define(stage, "/Root")
    cube = UsdGeom.Cube.Define(stage, "/Root/Geom/Cube")
    cube.CreateSizeAttr(1.0)

    stage.GetRootLayer().Save()


def make_asset_usda(out_path: Path) -> None:
    stage = Usd.Stage.CreateNew(str(out_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

    UsdGeom.Xform.Define(stage, "/Asset")
    UsdGeom.Cube.Define(stage, "/Asset/Cube")

    stage.GetRootLayer().Save()


def make_main_usda(out_path: Path, referenced_asset_path: str) -> None:
    stage = Usd.Stage.CreateNew(str(out_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

    UsdGeom.Xform.Define(stage, "/Root")

    ref_prim = stage.DefinePrim("/Root/ReferencedAsset", "Xform")
    # Use relative reference like "asset.usda"
    ref_prim.GetReferences().AddReference(referenced_asset_path)

    stage.GetRootLayer().Save()


def make_textured_usda(out_path: Path, texture_rel_path: str) -> None:
    stage = Usd.Stage.CreateNew(str(out_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

    UsdGeom.Xform.Define(stage, "/Root")
    UsdGeom.Sphere.Define(stage, "/Root/Geom/Sphere")

    # Material
    mat = UsdShade.Material.Define(stage, "/Root/Looks/Mat1")

    # PreviewSurface shader
    ps = UsdShade.Shader.Define(stage, "/Root/Looks/Mat1/PreviewSurface")
    ps.CreateIdAttr("UsdPreviewSurface")

    # Create the PreviewSurface "surface" output explicitly (compatible with your build)
    ps_surface_out = ps.CreateOutput("surface", Sdf.ValueTypeNames.Token)

    # Texture shader
    tex = UsdShade.Shader.Define(stage, "/Root/Looks/Mat1/DiffuseTex")
    tex.CreateIdAttr("UsdUVTexture")

    # Asset-typed input that Day 4 scans for
    tex_file_in = tex.CreateInput("file", Sdf.ValueTypeNames.Asset)
    tex_file_in.Set(texture_rel_path)

    # Connect tex.rgb -> ps.diffuseColor
    tex_rgb_out = tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
    ps_diff_in = ps.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f)
    ps_diff_in.ConnectToSource(tex_rgb_out)

    # Connect material surface -> preview surface surface output
    mat_surface_out = mat.CreateSurfaceOutput()
    mat_surface_out.ConnectToSource(ps_surface_out)

    # Bind
    UsdShade.MaterialBindingAPI(stage.GetPrimAtPath("/Root/Geom/Sphere")).Bind(mat)

    stage.GetRootLayer().Save()


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]  # tools/ -> repo root
    samples_dir = repo_root / "samples"
    tex_dir = samples_dir / "textures"

    ensure_dir(samples_dir)
    ensure_dir(tex_dir)

    sample_path = samples_dir / "sample.usda"
    asset_path = samples_dir / "asset.usda"
    main_path = samples_dir / "main.usda"
    textured_path = samples_dir / "textured.usda"
    albedo_path = tex_dir / "albedo.png"

    # Create files
    make_sample_usda(sample_path)
    make_asset_usda(asset_path)

    # Reference asset.usda by relative name (since main.usda sits in same folder)
    make_main_usda(main_path, "asset.usda")

    # Textured USD references samples/textures/albedo.png relatively
    make_textured_usda(textured_path, "textures/albedo.png")

    # Dummy texture file
    write_dummy_texture(albedo_path)

    print("Demo files created:")
    print(f"  {sample_path}")
    print(f"  {asset_path}")
    print(f"  {main_path}   (references asset.usda)")
    print(f"  {textured_path} (uses textures/albedo.png)")
    print(f"  {albedo_path}")

    print("\nTo test missing texture detection:")
    print(f"  Delete: {albedo_path}")


if __name__ == "__main__":
    main()
