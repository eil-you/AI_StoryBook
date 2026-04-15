"""
Server-side page preview rendering using Pillow.

Composites:
  Cover  : template background → cover image (full bleed) → title overlay at bottom
  Content: story image (full bleed) → semi-transparent text overlay at bottom center

Returns PNG bytes ready to serve as image/png.
"""

import io
import logging
import textwrap
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Preview canvas size
_W, _H = 978, 1001

# Cover: title bar at bottom
_COVER_TITLE_AREA = (0, 820, _W, _H)

# Content: text overlay at bottom center (full-bleed image design)
_CONTENT_TEXT_AREA = (0, 790, _W, _H)

_FALLBACK_BG = (255, 253, 230)    # warm cream

_FONT_PATH_CANDIDATES = [
    # Windows system fonts that support Korean
    "C:/Windows/Fonts/malgun.ttf",        # Malgun Gothic (Korean)
    "C:/Windows/Fonts/NanumGothic.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

# ---------------------------------------------------------------------------
# In-memory image cache (template thumbnails are static; story images reused
# across page navigation).  Simple LRU via ordered dict eviction.
# ---------------------------------------------------------------------------
_image_cache: dict[str, Image.Image] = {}
_MAX_CACHE = 30


def _cache_get(url: str) -> Image.Image | None:
    img = _image_cache.get(url)
    if img is None:
        return None
    # Move to end (most-recently-used)
    _image_cache.pop(url)
    _image_cache[url] = img
    return img.copy()


def _cache_set(url: str, img: Image.Image) -> None:
    if len(_image_cache) >= _MAX_CACHE:
        # Remove the oldest entry
        oldest = next(iter(_image_cache))
        del _image_cache[oldest]
    _image_cache[url] = img


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_PATH_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


async def _fetch_image(url: str) -> Image.Image | None:
    """Download an image from a URL or local /static/ path and return a PIL Image.

    Results are cached in-memory so repeated calls for the same URL (e.g.
    the same template thumbnail across many pages) avoid redundant HTTP round-trips.
    """
    if not url:
        return None

    cached = _cache_get(url)
    if cached is not None:
        return cached

    if url.startswith("/static/"):
        static_root = Path(__file__).resolve().parents[2] / "static"
        local_path = static_root / url[len("/static/"):]
        if not local_path.exists():
            logger.warning("Preview: local file not found: %s", local_path)
            return None
        try:
            img = Image.open(local_path).convert("RGBA")
            _cache_set(url, img)
            return img.copy()
        except Exception as exc:
            logger.warning("Preview: failed to open local file %s: %s", local_path, exc)
            return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            _cache_set(url, img)
            return img.copy()
    except Exception as exc:
        logger.warning("Preview: failed to fetch image %s: %s", url, exc)
        return None


def _paste_fit(canvas: Image.Image, img: Image.Image, area: tuple[int, int, int, int]) -> None:
    """Scale img to fill the area (cover-fit) and paste it onto canvas."""
    left, top, right, bottom = area
    area_w = right - left
    area_h = bottom - top

    img_ratio = img.width / img.height
    area_ratio = area_w / area_h

    if img_ratio > area_ratio:
        new_h = area_h
        new_w = int(new_h * img_ratio)
    else:
        new_w = area_w
        new_h = int(new_w / img_ratio)

    img_resized = img.resize((new_w, new_h), Image.LANCZOS)

    crop_left = (new_w - area_w) // 2
    crop_top = (new_h - area_h) // 2
    img_cropped = img_resized.crop((crop_left, crop_top, crop_left + area_w, crop_top + area_h))

    if img_cropped.mode == "RGBA":
        canvas.paste(img_cropped, (left, top), img_cropped)
    else:
        canvas.paste(img_cropped, (left, top))


def _draw_text_overlay(
    canvas: Image.Image,
    text: str,
    area: tuple[int, int, int, int],
    *,
    bg_color: tuple = (20, 15, 10, 180),
    text_color: tuple = (255, 250, 235),
    font_size: int = 24,
    padding: int = 20,
    center: bool = True,
) -> None:
    """Draw a semi-transparent text overlay over the given area.

    Unlike the old version this draws ON TOP of the image (alpha-composite)
    so it matches the 'full-bleed image + bottom text' template design.
    """
    left, top, right, bottom = area
    area_w = right - left

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    draw_overlay.rectangle([left, top, right, bottom], fill=bg_color)
    canvas.alpha_composite(overlay)

    if not text:
        return

    font = _load_font(font_size)
    draw = ImageDraw.Draw(canvas)

    # Wrap text — estimate chars per line from pixel width
    avg_char_w = max(1, font_size * 6 // 10)
    max_chars = max(1, (area_w - padding * 2) // avg_char_w)
    lines = []
    for paragraph in text.split("\n"):
        wrapped = textwrap.wrap(paragraph, width=max_chars) or [""]
        lines.extend(wrapped)

    line_height = font_size + 6
    total_text_h = len(lines) * line_height
    y = top + max(padding, (bottom - top - total_text_h) // 2)

    for line in lines:
        if y + line_height > bottom - padding:
            break
        if center:
            try:
                bbox = font.getbbox(line)
                line_w = bbox[2] - bbox[0]
            except AttributeError:
                line_w = len(line) * avg_char_w
            x = left + (area_w - line_w) // 2
        else:
            x = left + padding
        draw.text((x, y), line, font=font, fill=text_color)
        y += line_height


async def render_content_page(
    story_image_url: str,
    text: str,
    template_thumbnail_url: str | None,
) -> bytes:
    """Render a content page matching the 'full-bleed image + bottom center text' template design.

    Layout:
      1. Template thumbnail as full-page background (shows template's text-bar design)
      2. Story image fills the IMAGE area (top 78% of page), bottom text bar left transparent
         so the template background shows through
      3. Text drawn centered in the text bar area
    """
    logger.info(
        "render_content_page: story=%s template=%s",
        story_image_url,
        template_thumbnail_url,
    )
    canvas = Image.new("RGBA", (_W, _H), _FALLBACK_BG + (255,))

    # 1. Template thumbnail as background — its text bar area will be visible at the bottom
    template_loaded = False
    if template_thumbnail_url:
        bg = await _fetch_image(template_thumbnail_url)
        if bg:
            _paste_fit(canvas, bg, (0, 0, _W, _H))
            template_loaded = True
            logger.info("render_content_page: template background applied")
        else:
            logger.warning("render_content_page: template image fetch failed url=%s", template_thumbnail_url)
    else:
        logger.warning("render_content_page: no template_thumbnail_url received")

    # 2. Story image fills the IMAGE area (top portion); bottom text bar left for template
    story_img = await _fetch_image(story_image_url)
    if story_img:
        _paste_fit(canvas, story_img, (0, 0, _W, _CONTENT_TEXT_AREA[1]))
        logger.info("render_content_page: story image applied")
    else:
        logger.warning("render_content_page: story image fetch failed url=%s", story_image_url)

    # 3. If template wasn't loaded, draw a fallback dark overlay for the text bar
    if not template_loaded:
        _draw_text_overlay(
            canvas,
            "",
            _CONTENT_TEXT_AREA,
            bg_color=(30, 22, 12, 200),
            text_color=(255, 250, 235),
            font_size=22,
            padding=18,
            center=True,
        )

    # 4. Draw text centered in the text bar area (on top of whatever is there)
    if text:
        draw = ImageDraw.Draw(canvas)
        font = _load_font(22)
        avg_char_w = max(1, 22 * 6 // 10)
        max_chars = max(1, (_W - 36) // avg_char_w)
        lines = []
        for paragraph in text.split("\n"):
            wrapped = textwrap.wrap(paragraph, width=max_chars) or [""]
            lines.extend(wrapped)

        line_height = 22 + 6
        area_top, area_bottom = _CONTENT_TEXT_AREA[1], _CONTENT_TEXT_AREA[3]
        total_text_h = len(lines) * line_height
        y = area_top + max(18, (area_bottom - area_top - total_text_h) // 2)

        for line in lines:
            if y + line_height > area_bottom - 18:
                break
            try:
                bbox = font.getbbox(line)
                line_w = bbox[2] - bbox[0]
            except AttributeError:
                line_w = len(line) * avg_char_w
            x = (_W - line_w) // 2
            draw.text((x, y), line, font=font, fill=(255, 250, 235))
            y += line_height

    output = canvas.convert("RGB")
    buf = io.BytesIO()
    output.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def render_cover_page(
    cover_image_url: str,
    title: str,
    template_thumbnail_url: str | None,
) -> bytes:
    """Render the cover page.

    Layout:
      1. Template thumbnail as full-page background
      2. Cover image fills the IMAGE area (top 82%), bottom title bar shows template background
      3. Title drawn centered in the title bar area
    """
    logger.info(
        "render_cover_page: cover=%s template=%s",
        cover_image_url,
        template_thumbnail_url,
    )
    canvas = Image.new("RGBA", (_W, _H), _FALLBACK_BG + (255,))

    # 1. Template background (the title bar area at the bottom will show through)
    template_loaded = False
    if template_thumbnail_url:
        bg = await _fetch_image(template_thumbnail_url)
        if bg:
            _paste_fit(canvas, bg, (0, 0, _W, _H))
            template_loaded = True
            logger.info("render_cover_page: template background applied")
        else:
            logger.warning("render_cover_page: template image fetch failed url=%s", template_thumbnail_url)
    else:
        logger.warning("render_cover_page: no template_thumbnail_url received")

    # 2. Cover image fills the top image area; title bar left for template
    cover_img = await _fetch_image(cover_image_url)
    if cover_img:
        _paste_fit(canvas, cover_img, (0, 0, _W, _COVER_TITLE_AREA[1]))
        logger.info("render_cover_page: cover image applied")
    else:
        logger.warning("render_cover_page: cover image fetch failed url=%s", cover_image_url)

    # 3. If template wasn't loaded, draw a dark fallback title bar
    if not template_loaded:
        _draw_text_overlay(
            canvas,
            "",
            _COVER_TITLE_AREA,
            bg_color=(20, 12, 5, 210),
            text_color=(255, 245, 200),
            font_size=30,
            padding=22,
            center=True,
        )

    # 4. Draw title centered in the title bar (on top of whatever background is there)
    if title:
        draw = ImageDraw.Draw(canvas)
        font = _load_font(30)
        avg_char_w = max(1, 30 * 6 // 10)
        max_chars = max(1, (_W - 44) // avg_char_w)
        lines = []
        for paragraph in title.split("\n"):
            wrapped = textwrap.wrap(paragraph, width=max_chars) or [""]
            lines.extend(wrapped)

        line_height = 30 + 8
        area_top, area_bottom = _COVER_TITLE_AREA[1], _COVER_TITLE_AREA[3]
        total_text_h = len(lines) * line_height
        y = area_top + max(22, (area_bottom - area_top - total_text_h) // 2)

        for line in lines:
            if y + line_height > area_bottom - 22:
                break
            try:
                bbox = font.getbbox(line)
                line_w = bbox[2] - bbox[0]
            except AttributeError:
                line_w = len(line) * avg_char_w
            x = (_W - line_w) // 2
            draw.text((x, y), line, font=font, fill=(255, 245, 200))
            y += line_height

    output = canvas.convert("RGB")
    buf = io.BytesIO()
    output.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
