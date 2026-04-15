import client from "./client";

export const generateStory = (data) =>
  client.post("/api/v1/stories/generate", data).then((r) => r.data);

export const publishCover = (bookId, coverTemplateUid) =>
  client
    .post(`/api/v1/stories/${bookId}/publish/cover`, {
      cover_template_uid: coverTemplateUid,
    })
    .then((r) => r.data);

export const publishContents = (bookId, contentTemplateUid, extraParameters = {}) =>
  client
    .post(`/api/v1/stories/${bookId}/publish/contents`, {
      content_template_uid: contentTemplateUid,
      extra_parameters: extraParameters,
    })
    .then((r) => r.data);

export const finalizeStory = (bookId) =>
  client.post(`/api/v1/stories/${bookId}/finalize`).then((r) => r.data);
