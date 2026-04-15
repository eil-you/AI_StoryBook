import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { getBook } from "../api/books";
import { getTemplate } from "../api/templates";
import { finalizeStory, publishContents, publishCover } from "../api/stories";
import Layout from "../components/Layout";
import LoadingSpinner from "../components/LoadingSpinner";
import TemplatePreview from "../components/TemplatePreview";

const COVER_TEMPLATE_UID = "7jOxkBjj6VGe";
const CONTENT_TEMPLATE_UID = "8DGGFyjtOu0E";

/**
 * The cover template is a full spread (back + spine + front).
 * The front cover starts at approximately x = 1057 in the 2013-wide canvas.
 */
const COVER_CANVAS_W = 2013;
const COVER_CANVAS_H = 1041;
const COVER_FRONT_X = 1057;   // front cover starts here
const COVER_FRONT_W = COVER_CANVAS_W - COVER_FRONT_X; // ~956 px

// ─── Fallback: server-rendered PNG (used for content pages until content
//     template layout JSON is available) ────────────────────────────────────

async function fetchPreviewUrl(apiPath) {
  const token = localStorage.getItem("access_token");
  const res = await fetch(apiPath, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`preview fetch failed: ${res.status}`);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

function RenderedPage({ apiPath }) {
  const [src, setSrc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const prevUrl = useRef(null);

  useEffect(() => {
    if (!apiPath) return;
    setLoading(true);
    setError(false);
    setSrc(null);

    fetchPreviewUrl(apiPath)
      .then((url) => {
        if (prevUrl.current) URL.revokeObjectURL(prevUrl.current);
        prevUrl.current = url;
        setSrc(url);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));

    return () => {
      if (prevUrl.current) {
        URL.revokeObjectURL(prevUrl.current);
        prevUrl.current = null;
      }
    };
  }, [apiPath]);

  if (loading) {
    return (
      <div className="w-full aspect-[978/1001] bg-amber-50 rounded-2xl flex items-center justify-center mb-4 shadow-lg">
        <div className="flex flex-col items-center gap-2 text-amber-400">
          <div className="w-8 h-8 border-2 border-amber-300 border-t-amber-500 rounded-full animate-spin" />
          <span className="text-sm">렌더링 중...</span>
        </div>
      </div>
    );
  }

  if (error || !src) {
    return (
      <div className="w-full aspect-[978/1001] bg-amber-50 rounded-2xl flex items-center justify-center mb-4 shadow-lg">
        <span className="text-gray-400 text-sm">미리보기를 불러올 수 없습니다</span>
      </div>
    );
  }

  return (
    <div className="w-full aspect-[978/1001] mb-4 rounded-2xl shadow-lg overflow-hidden">
      <img src={src} alt="페이지 미리보기" className="w-full h-full object-cover" />
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function StoryPreviewPage() {
  const { bookId } = useParams();
  const { state } = useLocation();
  const navigate = useNavigate();

  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(0);
  const [finalizing, setFinalizing] = useState(false);
  const [finalizeStep, setFinalizeStep] = useState("");
  const [error, setError] = useState("");

  // Full template layout JSON (not just thumbnail URL)
  const [coverLayout, setCoverLayout] = useState(undefined);      // undefined = loading
  const [contentLayout, setContentLayout] = useState(undefined);
  const [contentBaseLayer, setContentBaseLayer] = useState(null); // odd/even page numbers
  const [contentThumbnail, setContentThumbnail] = useState(null);

  // Container ref for measuring display width
  const containerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(600);

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      setContainerWidth(entries[0].contentRect.width);
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Fetch template layouts
  useEffect(() => {
    getTemplate(COVER_TEMPLATE_UID)
      .then((res) => {
        setCoverLayout(res.data?.layout ?? null);
      })
      .catch(() => setCoverLayout(null));

    getTemplate(CONTENT_TEMPLATE_UID)
      .then((res) => {
        setContentLayout(res.data?.layout ?? null);
        // FastAPI serialises the aliased field as snake_case "base_layer"
        setContentBaseLayer(res.data?.base_layer ?? null);
        setContentThumbnail(res.data?.thumbnails?.layout ?? null);
      })
      .catch(() => {
        setContentLayout(null);
        setContentBaseLayer(null);
        setContentThumbnail(null);
      });
  }, []);

  // Fetch book data
  useEffect(() => {
    if (state?.storyData) {
      const sd = state.storyData;
      setBook({
        id: null,
        title: sd.title,
        cover_image_url: sd.cover_image_url,
        status: "draft",
        pages: (sd.pages ?? []).map((p, i) => ({
          page_number: i + 1,
          text: p.text,
          image_url: p.image_url,
        })),
      });
      setLoading(false);
      return;
    }

    getBook(bookId)
      .then((data) => {
        setBook({
          title: data.title,
          cover_image_url: data.cover_image_url,
          status: data.status,
          pages: data.pages,
        });
      })
      .catch(() => setError("책 정보를 불러오는데 실패했습니다."))
      .finally(() => setLoading(false));
  }, [bookId, state]);

  const handleFinalize = async () => {
    setError("");
    setFinalizing(true);
    try {
      setFinalizeStep("표지 등록 중...");
      await publishCover(bookId, COVER_TEMPLATE_UID);
      setFinalizeStep("내지 등록 중...");
      await publishContents(bookId, CONTENT_TEMPLATE_UID);
      setFinalizeStep("최종 완료 처리 중...");
      await finalizeStory(bookId);
      navigate(`/order/${bookId}`, { state: { storyTitle: book?.title } });
    } catch (err) {
      setError(err.response?.data?.detail || "완료 처리에 실패했습니다.");
    } finally {
      setFinalizing(false);
      setFinalizeStep("");
    }
  };

  if (loading) {
    return (
      <Layout>
        <LoadingSpinner message="동화를 불러오는 중..." />
      </Layout>
    );
  }

  if (error && !book) {
    return (
      <Layout>
        <div className="text-center py-16">
          <p className="text-red-500 mb-4">{error}</p>
          <button onClick={() => navigate("/dashboard")} className="btn-primary">
            대시보드로 이동
          </button>
        </div>
      </Layout>
    );
  }

  const pages = book?.pages ?? [];
  const totalPages = pages.length;
  const isFinalized = book?.status === "finalized" || book?.status === "published";
  const templatesLoading = coverLayout === undefined || contentLayout === undefined;

  // ── Cover preview (TemplatePreview) ──────────────────────────────────────

  function CoverPreview() {
    if (coverLayout === undefined) {
      return (
        <div className="w-full bg-amber-50 rounded-2xl flex items-center justify-center mb-4 shadow-lg" style={{ aspectRatio: `${COVER_FRONT_W}/${COVER_CANVAS_H}` }}>
          <LoadingSpinner message="템플릿 불러오는 중..." />
        </div>
      );
    }

    if (coverLayout === null) {
      // Layout unavailable — fall back to backend rendering
      return (
        <RenderedPage
          key="cover"
          apiPath={`/api/v1/stories/${bookId}/preview/cover`}
        />
      );
    }

    return (
      <div className="w-full mb-4 rounded-2xl shadow-lg overflow-hidden">
        <TemplatePreview
          layout={coverLayout}
          bindings={{
            title: book?.title ?? "",
            coverphoto: book?.cover_image_url ?? "",
          }}
          canvasWidth={COVER_CANVAS_W}
          canvasHeight={COVER_CANVAS_H}
          containerWidth={containerWidth}
          cropX={COVER_FRONT_X}
          cropWidth={COVER_FRONT_W}
        />
      </div>
    );
  }

  // ── Content page preview ──────────────────────────────────────────────────

  function ContentPreview({ pageNumber }) {
    const page = pages.find((p) => p.page_number === pageNumber);

    if (contentLayout) {
      return (
        <div className="w-full mb-4 rounded-2xl shadow-lg overflow-hidden">
          <TemplatePreview
            layout={contentLayout}
            baseLayer={contentBaseLayer}
            bindings={{
              image: page?.image_url ?? "",   // $$image$$  → rowGallery photos
              text: page?.text ?? "",          // $$text$$   → story text
              pageNum: String(pageNumber),     // @@pageNum@@ → base layer page number
            }}
            canvasWidth={978}
            canvasHeight={1001}
            containerWidth={containerWidth}
            pageNumber={pageNumber}
          />
        </div>
      );
    }

    // Fallback: backend PNG rendering
    const base = `/api/v1/stories/${bookId}/preview/page/${pageNumber}`;
    const apiPath = contentThumbnail
      ? `${base}?template_thumbnail=${encodeURIComponent(contentThumbnail)}`
      : base;

    return <RenderedPage key={`page-${pageNumber}`} apiPath={apiPath} />;
  }

  return (
    <Layout>
      <div className="max-w-2xl mx-auto" ref={containerRef}>
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">{book?.title}</h1>
            <p className="text-sm text-gray-500 mt-0.5">총 {totalPages}페이지</p>
          </div>
          <button onClick={() => navigate("/dashboard")} className="btn-secondary text-sm">
            대시보드로
          </button>
        </div>

        {/* Preview area */}
        {templatesLoading ? (
          <div
            className="w-full bg-amber-50 rounded-2xl flex items-center justify-center mb-4 shadow-lg"
            style={{ aspectRatio: `${COVER_FRONT_W}/${COVER_CANVAS_H}` }}
          >
            <LoadingSpinner message="템플릿 불러오는 중..." />
          </div>
        ) : currentPage === 0 ? (
          <CoverPreview />
        ) : (
          <ContentPreview pageNumber={currentPage} />
        )}

        {/* Page navigation */}
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500">
              {currentPage === 0 ? "표지" : `${currentPage} / ${totalPages} 페이지`}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
                disabled={currentPage === 0}
                className="btn-secondary text-sm py-1 px-3 disabled:opacity-30"
              >
                이전
              </button>
              <button
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="btn-secondary text-sm py-1 px-3 disabled:opacity-30"
              >
                다음
              </button>
            </div>
          </div>

          {totalPages > 0 && (
            <div className="flex justify-center gap-1.5 mt-3">
              {Array.from({ length: totalPages + 1 }).map((_, i) => (
                <button
                  key={i}
                  onClick={() => setCurrentPage(i)}
                  className={`w-2 h-2 rounded-full transition-colors ${
                    currentPage === i ? "bg-primary-600" : "bg-gray-300"
                  }`}
                />
              ))}
            </div>
          )}
        </div>

        {error && (
          <p className="text-red-500 text-sm bg-red-50 rounded-lg px-3 py-2 mt-4">{error}</p>
        )}

        <div className="flex gap-3 mt-6">
          <button onClick={() => navigate("/generate")} className="btn-secondary flex-1">
            새 동화 만들기
          </button>
          {isFinalized ? (
            <button
              onClick={() => navigate(`/order/${bookId}`)}
              className="btn-primary flex-1"
            >
              주문하기
            </button>
          ) : (
            <button onClick={handleFinalize} disabled={finalizing} className="btn-primary flex-1">
              {finalizing ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  {finalizeStep || "처리 중..."}
                </span>
              ) : (
                "주문 준비 완료 →"
              )}
            </button>
          )}
        </div>
      </div>
    </Layout>
  );
}
