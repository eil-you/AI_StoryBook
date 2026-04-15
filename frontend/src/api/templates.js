import client from "./client";

export const getTemplate = (templateUid) =>
  client.get(`/api/v1/templates/${templateUid}`).then((r) => r.data);
