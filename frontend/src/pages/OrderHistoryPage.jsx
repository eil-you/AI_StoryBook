import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { cancelOrder, getOrder, listOrders, updateShipping } from "../api/orders";
import Layout from "../components/Layout";
import LoadingSpinner from "../components/LoadingSpinner";

// ─── Status metadata ──────────────────────────────────────────────────────────

const ORDER_STATUS = {
  10:  { label: "주문 대기",  color: "bg-gray-100 text-gray-600",    icon: "🕐" },
  20:  { label: "결제 완료",  color: "bg-blue-100 text-blue-700",    icon: "✅" },
  30:  { label: "PDF 준비",   color: "bg-indigo-100 text-indigo-700",icon: "📄" },
  40:  { label: "인쇄 중",    color: "bg-yellow-100 text-yellow-700",icon: "🖨️" },
  50:  { label: "배송 중",    color: "bg-orange-100 text-orange-700",icon: "🚚" },
  60:  { label: "배송 완료",  color: "bg-green-100 text-green-700",  icon: "📦" },
  "-1": { label: "취소됨",   color: "bg-red-100 text-red-600",      icon: "✖️" },
};

/** status가 없거나 0이면 PAID(20) 기본값으로 처리 */
function normalizeStatus(status) {
  return status || 20;
}

function statusInfo(status) {
  return ORDER_STATUS[String(normalizeStatus(status))] ?? { label: `상태 ${status}`, color: "bg-gray-100 text-gray-500", icon: "❓" };
}

/** 취소 가능 상태: PAID(20), PDF_READY(30) */
const CANCELLABLE = new Set([20, 30]);
/** 배송지 변경 가능 상태: PAID(20), PDF_READY(30) */
const SHIPPABLE   = new Set([20, 30]);

// ─── Modal base ───────────────────────────────────────────────────────────────

function Modal({ title, onClose, children }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.45)" }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-lg">{title}</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 text-gray-400 transition-colors"
          >
            ✕
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

// ─── Cancel modal ─────────────────────────────────────────────────────────────

function CancelModal({ orderUid, onClose, onSuccess }) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const REASONS = ["단순 변심", "배송지 오입력", "중복 주문", "기타"];

  const handleSubmit = async () => {
    if (!reason.trim()) { setError("취소 사유를 선택하거나 입력해주세요."); return; }
    setSubmitting(true);
    setError("");
    try {
      await cancelOrder(orderUid, reason);
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || "취소 처리에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal title="주문 취소" onClose={onClose}>
      <p className="text-sm text-gray-500 mb-4">
        취소 후에는 복구할 수 없습니다. 신중히 진행해주세요.
      </p>

      <div className="space-y-2 mb-4">
        {REASONS.map((r) => (
          <label key={r} className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="cancel-reason"
              value={r}
              checked={reason === r}
              onChange={() => setReason(r)}
              className="accent-primary-600"
            />
            <span className="text-sm text-gray-700">{r}</span>
          </label>
        ))}
      </div>

      {reason === "기타" && (
        <textarea
          className="input-field text-sm resize-none mb-4"
          rows={3}
          placeholder="취소 사유를 직접 입력해주세요"
          value={reason === "기타" ? "" : reason}
          onChange={(e) => setReason(e.target.value)}
        />
      )}

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      <div className="flex gap-3">
        <button onClick={onClose} className="btn-secondary flex-1">
          돌아가기
        </button>
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="flex-1 bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded-lg transition-colors disabled:opacity-50"
        >
          {submitting ? "처리 중..." : "주문 취소"}
        </button>
      </div>
    </Modal>
  );
}

// ─── Shipping modal ───────────────────────────────────────────────────────────

function ShippingModal({ orderUid, initialShipping, onClose, onSuccess }) {
  const [form, setForm] = useState({
    recipient_name:  initialShipping?.recipient_name  ?? "",
    recipient_phone: initialShipping?.recipient_phone ?? "",
    postal_code:     initialShipping?.postal_code     ?? "",
    address1:        initialShipping?.address1        ?? "",
    address2:        initialShipping?.address2        ?? "",
    memo:            initialShipping?.memo            ?? "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]   = useState("");

  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await updateShipping(orderUid, form);
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || "배송지 변경에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal title="배송지 변경" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">수령인 이름</label>
            <input
              className="input-field text-sm"
              value={form.recipient_name}
              onChange={(e) => update("recipient_name", e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">전화번호</label>
            <input
              className="input-field text-sm"
              value={form.recipient_phone}
              onChange={(e) => update("recipient_phone", e.target.value)}
              placeholder="010-0000-0000"
              required
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">우편번호</label>
          <input
            className="input-field text-sm"
            value={form.postal_code}
            onChange={(e) => update("postal_code", e.target.value)}
            maxLength={10}
            required
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">기본 주소</label>
          <input
            className="input-field text-sm"
            value={form.address1}
            onChange={(e) => update("address1", e.target.value)}
            required
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">상세 주소</label>
          <input
            className="input-field text-sm"
            value={form.address2}
            onChange={(e) => update("address2", e.target.value)}
            placeholder="동/호수 (선택)"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">배송 메모</label>
          <input
            className="input-field text-sm"
            value={form.memo}
            onChange={(e) => update("memo", e.target.value)}
            placeholder="경비실 맡겨주세요 (선택)"
          />
        </div>

        {error && <p className="text-red-500 text-sm">{error}</p>}

        <div className="flex gap-3 pt-2">
          <button type="button" onClick={onClose} className="btn-secondary flex-1">
            취소
          </button>
          <button type="submit" disabled={submitting} className="btn-primary flex-1">
            {submitting ? "저장 중..." : "변경 저장"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ─── Order card ───────────────────────────────────────────────────────────────

function OrderCard({ order, onCancelSuccess, onShippingSuccess }) {
  const [expanded, setExpanded]   = useState(false);
  const [detail, setDetail]       = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [showCancel, setShowCancel]   = useState(false);
  const [showShipping, setShowShipping] = useState(false);

  const normalStatus = normalizeStatus(order.status);
  const si = statusInfo(normalStatus);
  const canCancel  = CANCELLABLE.has(normalStatus);
  const canShip    = SHIPPABLE.has(normalStatus);

  const loadDetail = async () => {
    if (detail) return;
    setDetailLoading(true);
    try {
      const d = await getOrder(order.order_uid);
      setDetail(d);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleExpand = () => {
    setExpanded((v) => !v);
    if (!expanded) loadDetail();
  };

  return (
    <>
      <div className="card hover:shadow-md transition-shadow">
        {/* Card header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5">
              <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${si.color}`}>
                {si.icon} {si.label}
              </span>
            </div>
            {order.book_title && (
              <p className="font-semibold text-gray-900 truncate mb-0.5">{order.book_title}</p>
            )}
            <p className="text-xs text-gray-400 font-mono truncate">{order.order_uid ?? "처리 중"}</p>
            {order.created_at && (
              <p className="text-xs text-gray-400 mt-0.5">
                {new Date(order.created_at).toLocaleString("ko-KR", {
                  year: "numeric", month: "2-digit", day: "2-digit",
                  hour: "2-digit", minute: "2-digit",
                })}
              </p>
            )}
          </div>
          <div className="text-right shrink-0">
            <p className="font-bold text-primary-600">
              {Number(order.paid_amount).toLocaleString()}원
            </p>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2 mt-4">
          <button
            onClick={handleExpand}
            className="btn-secondary text-xs py-1.5 flex-1"
          >
            {expanded ? "접기" : "상세 보기"}
          </button>
          {canShip && (
            <button
              onClick={() => { loadDetail(); setShowShipping(true); }}
              className="btn-secondary text-xs py-1.5 flex-1"
            >
              배송지 변경
            </button>
          )}
          {canCancel && (
            <button
              onClick={() => setShowCancel(true)}
              className="text-xs py-1.5 px-3 rounded-lg border border-red-200 text-red-500 hover:bg-red-50 transition-colors"
            >
              주문 취소
            </button>
          )}
        </div>

        {/* Expanded detail */}
        {expanded && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            {detailLoading && <LoadingSpinner message="불러오는 중..." />}
            {detail && !detailLoading && (
              <div className="space-y-3 text-sm">
                {/* Shipping address */}
                {detail.shipping && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">배송지</p>
                    <div className="bg-gray-50 rounded-xl p-3 space-y-0.5 text-gray-700">
                      <p className="font-medium">{detail.shipping.recipient_name}</p>
                      <p className="text-gray-500">{detail.shipping.recipient_phone}</p>
                      <p>{detail.shipping.postal_code && `[${detail.shipping.postal_code}] `}{detail.shipping.address1}</p>
                      {detail.shipping.address2 && <p>{detail.shipping.address2}</p>}
                      {detail.shipping.memo && (
                        <p className="text-gray-400 text-xs">메모: {detail.shipping.memo}</p>
                      )}
                    </div>
                  </div>
                )}

                {/* Cancel reason */}
                {detail.cancel_reason && (
                  <div className="bg-red-50 rounded-xl p-3 text-red-600 text-sm">
                    취소 사유: {detail.cancel_reason}
                  </div>
                )}

                {/* Amount breakdown */}
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">결제 내역</p>
                  <div className="bg-gray-50 rounded-xl p-3 space-y-1 text-gray-700">
                    <div className="flex justify-between">
                      <span className="text-gray-500">결제 금액</span>
                      <span>{Number(detail.paid_amount).toLocaleString()}원</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">배송비</span>
                      <span>{Number(detail.shipping_amount).toLocaleString()}원</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modals */}
      {showCancel && (
        <CancelModal
          orderUid={order.order_uid}
          onClose={() => setShowCancel(false)}
          onSuccess={() => {
            setShowCancel(false);
            onCancelSuccess(order.order_uid);
          }}
        />
      )}
      {showShipping && (
        <ShippingModal
          orderUid={order.order_uid}
          initialShipping={detail?.shipping}
          onClose={() => setShowShipping(false)}
          onSuccess={() => {
            setShowShipping(false);
            setDetail(null); // force re-fetch to show updated address
            loadDetail();
            onShippingSuccess();
          }}
        />
      )}
    </>
  );
}

// ─── Toast notification ───────────────────────────────────────────────────────

function Toast({ message, type = "success", onDismiss }) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 3000);
    return () => clearTimeout(t);
  }, [onDismiss]);

  return (
    <div
      className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl shadow-lg text-sm font-medium text-white transition-all ${
        type === "success" ? "bg-green-500" : "bg-red-500"
      }`}
    >
      {message}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function OrderHistoryPage() {
  const navigate = useNavigate();
  const [orders, setOrders]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState("");
  const [toast, setToast]     = useState(null);

  const showToast = (message, type = "success") => setToast({ message, type });

  const fetchOrders = () => {
    setLoading(true);
    listOrders({ limit: 50 })
      .then((data) => setOrders(data.orders ?? []))
      .catch(() => setError("주문 목록을 불러오는데 실패했습니다."))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchOrders(); }, []);

  const handleCancelSuccess = (orderUid) => {
    // Optimistically mark as cancelled (status -1)
    setOrders((prev) =>
      prev.map((o) => (o.order_uid === orderUid ? { ...o, status: -1 } : o))
    );
    showToast("주문이 취소됐습니다.");
  };

  const handleShippingSuccess = () => {
    showToast("배송지가 변경됐습니다.");
  };

  return (
    <Layout>
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">주문 내역</h1>
            <p className="text-sm text-gray-400 mt-0.5">
              결제 완료 · PDF 준비 상태에서 취소 및 배송지 변경이 가능합니다
            </p>
          </div>
          <div className="flex gap-2">
            <button onClick={fetchOrders} className="btn-secondary text-sm">
              새로고침
            </button>
            <button onClick={() => navigate("/dashboard")} className="btn-primary text-sm">
              대시보드로
            </button>
          </div>
        </div>

        {/* Status legend */}
        <div className="flex flex-wrap gap-2 mb-6">
          {Object.entries(ORDER_STATUS).map(([, s]) => (
            <span key={s.label} className={`text-xs px-2.5 py-1 rounded-full font-medium ${s.color}`}>
              {s.icon} {s.label}
            </span>
          ))}
        </div>

        {/* Content */}
        {loading && <LoadingSpinner message="주문 내역을 불러오는 중..." />}

        {error && (
          <div className="card text-center py-10 text-red-500">
            <p>{error}</p>
            <button onClick={fetchOrders} className="btn-secondary mt-4 text-sm">
              다시 시도
            </button>
          </div>
        )}

        {!loading && !error && orders.length === 0 && (
          <div className="card text-center py-16">
            <p className="text-4xl mb-4">📭</p>
            <p className="text-gray-400 text-lg">아직 주문 내역이 없어요</p>
          </div>
        )}

        {!loading && !error && orders.length > 0 && (
          <div className="space-y-4">
            {orders.map((order) => (
              <OrderCard
                key={order.order_uid}
                order={order}
                onCancelSuccess={handleCancelSuccess}
                onShippingSuccess={handleShippingSuccess}
              />
            ))}
          </div>
        )}
      </div>

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToast(null)}
        />
      )}
    </Layout>
  );
}
