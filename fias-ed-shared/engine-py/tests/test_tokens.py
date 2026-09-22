import json
import subprocess
import sys

from fias_ed_engine.paths import DESIGN_TOKENS_DIR, SHARED_ROOT

sys.path.insert(0, str(SHARED_ROOT / "scripts"))
import build_tokens  # noqa: E402

T = json.loads((DESIGN_TOKENS_DIR / "tokens.json").read_text(encoding="utf-8"))
ALL = {**T["color"]["brand"], **T["color"]["semantic"]}


def test_official_palette_exact():
    assert T["color"]["brand"] == {"navy": "#2F4156", "teal": "#567C8D", "sky": "#C8D9E6",
                                   "beige": "#F5EFEB", "white": "#FFFFFF"}


def test_contrast_function_known_values():
    assert round(build_tokens.contrast("#2F4156", "#FFFFFF"), 2) == 10.44
    assert build_tokens.contrast("#567C8D", "#FFFFFF") >= 4.5
    assert build_tokens.contrast("#567C8D", "#F5EFEB") < 4.5


def test_all_declared_text_pairs_pass_aa():
    for fg, bg in T["text_pairs"]:
        assert build_tokens.contrast(ALL[fg], ALL[bg]) >= 4.5, (fg, bg)


def test_forbidden_pairs_really_fail():
    for fg, bg in T["forbidden_text_pairs"]:
        assert build_tokens.contrast(ALL[fg], ALL[bg]) < 4.5, (fg, bg)


def test_editorial_font_not_used_for_small_text():
    for name, style in T["type_scale"].items():
        if style["font"] == "editorial":
            assert style["size_px"] >= 24, name


def test_build_outputs():
    subprocess.run([sys.executable, str(SHARED_ROOT / "scripts" / "build_tokens.py")], check=True)
    css = (DESIGN_TOKENS_DIR / "build" / "tokens.css").read_text(encoding="utf-8")
    kt = (DESIGN_TOKENS_DIR / "build" / "FiasTokens.kt").read_text(encoding="utf-8")
    assert "--color-navy: #2F4156;" in css
    assert "--font-interface: 'Ubuntu', system-ui, sans-serif;" in css
    assert "--font-editorial: 'Rokkitt', Georgia, serif;" in css
    assert "gradient" not in css.lower()
    assert "val Navy = Color(0xFF2F4156)" in kt


def test_fonts_bundled_with_licenses():
    fonts = DESIGN_TOKENS_DIR / "fonts"
    manifest = json.loads((fonts / "manifest.json").read_text(encoding="utf-8"))
    for name in ("Ubuntu-Regular.woff2", "Ubuntu-Medium.woff2", "Ubuntu-Bold.woff2", "Rokkitt[wght].woff2", "UFL.txt", "OFL-Rokkitt.txt"):
        assert (fonts / name).exists() and name in manifest
