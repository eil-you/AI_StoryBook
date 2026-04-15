import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { createOrder, estimateOrder } from "../api/orders";
import Layout from "../components/Layout";
import LoadingSpinner from "../components/LoadingSpinner";

export default function OrderPage() {
  const { bookId } = useParams();
  const { state } = useLocation();
  const navigate = useNavigate();
  const storyData = state?.storyData;

  const [estimate, setEstimate] = useState(null);
  const [loadingEstimate, setLoadingEstimate] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(null);

  const [form, setForm] = useState({
    quantity: 1,
    recipient_name: "",
    recipient_phone: "",
    postal_code: "",
    address1: "",
    address2: "",
    memo: "",
  });

  const update = (field, value) => setForm((f) => ({ ...f, [field]: value }));

  useEffect(() => {
    estimateOrder(Number(bookId), form.quantity)
      .then(setEstimate)
      .catch(() => setError("금액 조회에 실패했습니다."))
      .finally(() => setLoadingEstimate(false));
  }, [bookId, form.quantity]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const result = await createOrder({ ...form, book_id: Number(bookId) });
      setSuccess(result);
    } catch (err) {
      setError(err.response?.data?.detail || "주문에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  if (success) {
    return (
      <Layout>
        <div className="max-w-md mx-auto text-center py-16">
          <div className="text-6xl mb-4">🎉</div>
          <h1 className="text-2xl font-bold text-primary-700 mb-2">주문 완료!</h1>
          <p className="text-gray-500 mb-2">주문번호: <strong>{success.order_uid}</strong></p>
          <p className="text-gray-500 mb-6">
            결제금액: <strong>{Number(success.paid_amount).toLocaleString()}원</strong>
          </p>
          <button onClick={() => navigate("/dashboard")} className="btn-primary">
            대시보드로 이동
          </button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">주문하기</h1>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Order form */}
          <form onSubmit={handleSubmit} className="md:col-span-2 space-y-4">
            <div className="card">
              <h2 className="font-semibold mb-4">배송지 정보</h2>
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">수령인 이름</label>
                    <input
                      type="text"
                      value={form.recipient_name}
                      onChange={(e) => update("recipient_name", e.target.value)}
                      className="input-field"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">전화번호</label>
                    <input
                      type="tel"
                      value={form.recipient_phone}
                      onChange={(e) => update("recipient_phone", e.target.value)}
                      className="input-field"
                      placeholder="010-0000-0000"
                      required
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">우편번호</label>
                  <input
                    type="text"
                    value={form.postal_code}
                    onChange={(e) => update("postal_code", e.target.value)}
                    className="input-field"
                    placeholder="12345"
                    maxLength={10}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">기본 주소</label>
                  <input
                    type="text"
                    value={form.address1}
                    onChange={(e) => update("address1", e.target.value)}
                    className="input-field"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">상세 주소</label>
                  <input
                    type="text"
                    value={form.address2}
                    onChange={(e) => update("address2", e.target.value)}
                    className="input-field"
                    placeholder="동/호수 (선택)"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">배송 메모</label>
                  <input
                    type="text"
                    value={form.memo}
                    onChange={(e) => update("memo", e.target.value)}
                    className="input-field"
                    placeholder="경비실 맡겨주세요 (선택)"
                  />
                </div>
              </div>
            </div>

            {error && (
              <p className="text-red-500 text-sm bg-red-50 rounded-lg px-3 py-2">{error}</p>
            )}

            <button type="submit" disabled={submitting} className="btn-primary w-full">
              {submitting ? "결제 중..." : "결제하기"}
            </button>
          </form>

          {/* Summary */}
          <div className="space-y-4">
            <div className="card">
              <h2 className="font-semibold mb-3">주문 요약</h2>
              {storyData?.title && (
                <p className="text-sm text-gray-600 mb-3 font-medium">{storyData.title}</p>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">수량</label>
                <select
                  value={form.quantity}
                  onChange={(e) => update("quantity", Number(e.target.value))}
                  className="input-field"
                >
                  {[1, 2, 3, 5, 10].map((q) => (
                    <option key={q} value={q}>{q}권</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="card">
              <h2 className="font-semibold mb-3">결제 금액</h2>
              {loadingEstimate ? (
                <LoadingSpinner message="금액 조회 중..." />
              ) : estimate ? (
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between text-gray-600">
                    <span>배송비</span>
                    <span>{Number(estimate.shipping_amount).toLocaleString()}원</span>
                  </div>
                  <div className="flex justify-between text-gray-600">
                    <span>패키징</span>
                    <span>{Number(estimate.packaging_amount).toLocaleString()}원</span>
                  </div>
                  <div className="border-t pt-2 flex justify-between font-bold text-base">
                    <span>합계</span>
                    <span className="text-primary-600">{Number(estimate.total_amount).toLocaleString()}원</span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-400">금액 조회 실패</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
