/**
 * TemplatePreview
 *
 * Renders a SweetBook template layout JSON directly in React using absolute
 * positioning. Supports all element types found in the children's book templates:
 *   photo       – single image with optional cornerRadius + fit mode
 *   rowGallery  – full-width image gallery (treated as single photo for preview)
 *   text        – styled text with horizontal/vertical alignment, vertical writing
 *   rectangle   – solid-color decorative box
 *
 * Also renders baseLayer elements (odd/even page numbers via @@pageNum@@).
 *
 * Props
 * ─────
 *  layout         {object}  templateJson.layout  { backgroundColor, elements[] }
 *  baseLayer      {object?} templateJson.baseLayer  { odd: { elements[] }, even: { elements[] } }
 *  bindings       {object}  Variable map, e.g.:
 *                             Cover:   { title, coverphoto }
 *                             Content: { text, image, pageNum }
 *  canvasWidth    {number}  Native canvas width  (cover: 2013, content: 978)
 *  canvasHeight   {number}  Native canvas height (cover: 1041, content: 1001)
 *  containerWidth {number}  Desired display width px – component scales to fit
 *  cropX          {number?} Crop start x (cover: 1057 to show front only)
 *  cropWidth      {number?} Crop width  (cover: ~956)
 */

// ─── Color ───────────────────────────────────────────────────────────────────

/** Convert SweetBook's #AARRGGBB → CSS rgba(). */
function argbToCss(hex) {
  if (!hex || !hex.startsWith("#")) return "transparent";
  const h = hex.slice(1);
  if (h.length === 8) {
    const a = (parseInt(h.slice(0, 2), 16) / 255).toFixed(3);
    const r = parseInt(h.slice(2, 4), 16);
    const g = parseInt(h.slice(4, 6), 16);
    const b = parseInt(h.slice(6, 8), 16);
    return `rgba(${r},${g},${b},${a})`;
  }
  if (h.length === 6) return `#${h}`;
  return "transparent";
}

// ─── Variable substitution ───────────────────────────────────────────────────

/**
 * Replace both $$varname$$ (template params) and @@varname@@ (system vars)
 * with values from the bindings object.
 */
function resolveText(template, bindings) {
  if (!template) return "";
  return template
    .replace(/\$\$(\w+)\$\$/g, (_, k) => bindings[k] ?? "")
    .replace(/@@(\w+)@@/g, (_, k) => bindings[k] ?? "");
}

/**
 * Resolve a photo/file binding placeholder to a URL string.
 * e.g.  "$$coverphoto$$" with bindings { coverphoto: "/static/..." } → "/static/..."
 */
function resolveImageUrl(fileName, bindings) {
  if (!fileName) return null;
  const resolved = resolveText(fileName, bindings);
  if (resolved && (resolved.startsWith("http") || resolved.startsWith("/"))) {
    return resolved;
  }
  return null;
}

// ─── Element renderers ───────────────────────────────────────────────────────

function PhotoElement({ el, bindings, zIndex }) {
  const src = resolveImageUrl(el.fileName ?? "", bindings);

  return (
    <div
      style={{
        position: "absolute",
        left: el.position.x,
        top: el.position.y,
        width: el.width,
        height: el.height,
        borderRadius: el.cornerRadius ?? 0,
        overflow: "hidden",
        zIndex,
        backgroundColor: "#ede8e0",
      }}
    >
      {src ? (
        <img
          src={src}
          alt=""
          draggable={false}
          style={{
            width: "100%",
            height: "100%",
            objectFit: el.fit === "contain" ? "contain" : "cover",
            display: "block",
          }}
        />
      ) : (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "#e8e0d4",
            color: "#b0a898",
            fontSize: 40,
          }}
        >
          🖼
        </div>
      )}
    </div>
  );
}

/**
 * RowGallery: used in content pages to fill the page with one or more photos.
 * For preview purposes we render the first (only) resolved image as a single
 * photo covering its container area, stretched to full canvas width.
 */
function RowGalleryElement({ el, bindings, canvasWidth, zIndex }) {
  // $$image$$ resolves to the page image URL
  const src = resolveImageUrl(el.photos ?? "", bindings);
  // Row galleries fill the full canvas width regardless of el.width
  const displayWidth = canvasWidth;

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        top: el.position.y,
        width: displayWidth,
        height: el.height,
        overflow: "hidden",
        zIndex,
        backgroundColor: "#ede8e0",
      }}
    >
      {src ? (
        <img
          src={src}
          alt=""
          draggable={false}
          style={{
            width: "100%",
            height: "100%",
            objectFit: el.fit === "contain" ? "contain" : "cover",
            display: "block",
          }}
        />
      ) : (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "#e8e0d4",
            color: "#b0a898",
            fontSize: 48,
          }}
        >
          🖼
        </div>
      )}
    </div>
  );
}

function RectangleElement({ el, zIndex }) {
  return (
    <div
      style={{
        position: "absolute",
        left: el.position.x,
        top: el.position.y,
        width: el.width,
        height: el.height,
        backgroundColor: argbToCss(el.color),
        borderRadius: el.cornerRadius ?? 0,
        zIndex,
      }}
    />
  );
}

function TextElement({ el, bindings, zIndex }) {
  const text = resolveText(el.text ?? "", bindings);
  const color = argbToCss(el.textBrush);
  const bg = argbToCss(el.backgroundColor);
  const isVertical = el.isVertical ?? false;

  const alignH = (el.textAlignment ?? "Left").toLowerCase();
  const alignV = (el.verticalAlignment ?? "Top").toLowerCase();

  // Map SweetBook alignment → CSS flex values
  const justifyContent =
    alignH === "center" ? "center" : alignH === "right" ? "flex-end" : "flex-start";
  const alignItems =
    alignV === "center" ? "center" : alignV === "bottom" ? "flex-end" : "flex-start";

  return (
    <div
      style={{
        position: "absolute",
        left: el.position.x,
        top: el.position.y,
        width: el.width,
        height: el.height,
        backgroundColor: bg,
        zIndex,
        display: "flex",
        // For vertical text swap the axes
        justifyContent: isVertical ? alignItems : justifyContent,
        alignItems: isVertical ? justifyContent : alignItems,
        overflow: "hidden",
        writingMode: isVertical ? "vertical-rl" : "horizontal-tb",
        textOrientation: isVertical ? "mixed" : undefined,
      }}
    >
      <span
        style={{
          fontFamily: `"${el.fontFamily}", "BMJUA", "나눔고딕", "Nanum Gothic", "Malgun Gothic", sans-serif`,
          fontSize: el.fontSize ?? 16,
          fontWeight: el.textBold ? "bold" : "normal",
          color,
          lineHeight: el.textLineHeight ? `${el.textLineHeight}px` : 1.5,
          textAlign:
            alignH === "center" ? "center" : alignH === "right" ? "right" : "left",
          whiteSpace: isVertical ? "normal" : "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {text}
      </span>
    </div>
  );
}

// ─── Element dispatcher ──────────────────────────────────────────────────────

function renderElement(el, index, bindings, canvasWidth, zIndexBase = 0) {
  const zIndex = zIndexBase + index + 1;
  switch (el.type) {
    case "photo":
      return (
        <PhotoElement key={el.element_id} el={el} bindings={bindings} zIndex={zIndex} />
      );
    case "rowGallery":
      return (
        <RowGalleryElement
          key={el.element_id}
          el={el}
          bindings={bindings}
          canvasWidth={canvasWidth}
          zIndex={zIndex}
        />
      );
    case "rectangle":
      return (
        <RectangleElement key={el.element_id} el={el} zIndex={zIndex} />
      );
    case "text":
      return (
        <TextElement key={el.element_id} el={el} bindings={bindings} zIndex={zIndex} />
      );
    default:
      return null;
  }
}

// ─── Main component ──────────────────────────────────────────────────────────

export default function TemplatePreview({
  layout,
  baseLayer,
  bindings = {},
  canvasWidth = 978,
  canvasHeight = 1001,
  containerWidth,
  cropX,
  cropWidth,
  pageNumber,      // used for odd/even baseLayer selection
}) {
  if (!layout) return null;

  // Determine crop / scale
  const effectiveCropX = cropX ?? 0;
  const effectiveCropW = cropWidth ?? canvasWidth;
  const scale = containerWidth != null ? containerWidth / effectiveCropW : 1;
  const displayW = containerWidth ?? effectiveCropW;
  const displayH = canvasHeight * scale;

  // Determine which baseLayer to use (odd/even pages)
  const isEven = typeof pageNumber === "number" && pageNumber % 2 === 0;
  const baseLayerElements = baseLayer
    ? (isEven ? baseLayer.even?.elements : baseLayer.odd?.elements) ?? []
    : [];

  // baseLayer renders on top of everything
  const mainZBase = 0;
  const baseZBase = layout.elements.length + 10;

  return (
    <div
      style={{
        position: "relative",
        width: displayW,
        height: displayH,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: canvasWidth,
          height: canvasHeight,
          backgroundColor: argbToCss(layout.backgroundColor),
          transform: `scale(${scale}) translateX(${-effectiveCropX}px)`,
          transformOrigin: "top left",
          userSelect: "none",
        }}
      >
        {/* Main layout elements */}
        {layout.elements.map((el, i) =>
          renderElement(el, i, bindings, canvasWidth, mainZBase)
        )}

        {/* Base layer (page numbers etc.) */}
        {baseLayerElements.map((el, i) =>
          renderElement(el, i, bindings, canvasWidth, baseZBase)
        )}
      </div>
    </div>
  );
}
