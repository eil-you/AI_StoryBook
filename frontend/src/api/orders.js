import client from "./client";

export const estimateOrder = (bookId, quantity = 1) =>
  client.post("/api/v1/orders/estimate", { book_id: bookId, quantity }).then((r) => r.data);

export const createOrder = (data) =>
  client.post("/api/v1/orders", data).then((r) => r.data);

export const listOrders = (params = {}) =>
  client.get("/api/v1/orders", { params }).then((r) => r.data);
