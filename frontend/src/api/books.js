import client from "./client";

export const listBooks = (params = {}) =>
  client.get("/api/v1/books", { params }).then((r) => r.data);

export const getBook = (bookId) =>
  client.get(`/api/v1/books/${bookId}`).then((r) => r.data);

export const deleteBook = (bookId) =>
  client.post(`/api/v1/books/${bookId}/delete`).then((r) => r.data);
