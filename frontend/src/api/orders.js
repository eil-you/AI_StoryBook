import client from "./client";

export const estimateOrder = (bookId, quantity = 1) =>
  client.post("/api/v1/orders/estimate", { book_id: bookId, quantity }).then((r) => r.data);

export const createOrder = (data) =>
  client.post("/api/v1/orders", data).then((r) => r.data);

export const listOrders = (params = {}) =>
  client.get("/api/v1/orders", { params }).then((r) => r.data);

export const getOrder = (orderUid) =>
  client.get(`/api/v1/orders/${orderUid}`).then((r) => r.data);

export const cancelOrder = (orderUid, cancelReason) =>
  client.post(`/api/v1/orders/${orderUid}/cancel`, { cancel_reason: cancelReason }).then((r) => r.data);

export const updateShipping = (orderUid, data) =>
  client.patch(`/api/v1/orders/${orderUid}/shipping`, data).then((r) => r.data);
