#!/usr/bin/env node
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function createClassList() {
  return {
    add() {},
    remove() {},
    toggle() {},
  };
}

function createElement(id) {
  const handlers = new Map();
  return {
    id,
    value: "",
    checked: false,
    textContent: "",
    disabled: false,
    files: [],
    style: {},
    elements: [],
    dataset: {},
    classList: createClassList(),
    setAttribute() {},
    scrollIntoView() {},
    addEventListener(event, handler) {
      handlers.set(event, handler);
    },
    getHandler(event) {
      return handlers.get(event);
    },
  };
}

function makeFetchResponse(status, payload) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return payload;
    },
    async text() {
      return JSON.stringify(payload);
    },
  };
}

async function runUploadScenario({
  scenarioName,
  uploadConcurrency,
  fileSize,
  csrfLifetimeSeconds,
  fetchHandler,
  xhrSendHandler,
  nowController,
}) {
  const submitButton = createElement("submitBtn");
  const cancelButton = createElement("cancelUploadBtn");
  const leavePageButton = createElement("leavePageBtn");
  const progressContainer = createElement("uploadProgress");
  const progressBar = createElement("uploadProgressBar");
  const progressStatus = createElement("uploadStatus");
  const progressPercent = createElement("uploadPercent");
  const errorBox = createElement("uploadError");
  const sessionDate = createElement("session_date");
  const notes = createElement("notes");
  const tags = createElement("tags");
  const visibility = createElement("visibility");
  const allowDownload = createElement("allow_download");
  const fileInput = createElement("video_file");
  const csrfHiddenField = { value: "csrf-old" };
  const form = createElement("uploadForm");

  form.dataset = {
    initiateUrl: "/api/uploads/multipart/initiate",
    completeUrl: "/api/uploads/multipart/complete",
    abortUrl: "/api/uploads/multipart/abort",
    refreshPartUrl: "/api/uploads/multipart/refresh-part",
    csrfTokenUrl: "/api/csrf-token",
    csrfTokenLifetimeSeconds: String(csrfLifetimeSeconds),
    maxFileSize: String(3 * 1024 * 1024 * 1024),
    uploadConcurrency: String(uploadConcurrency),
  };
  form.querySelector = (selector) =>
    selector === 'input[name="csrf_token"]' ? csrfHiddenField : null;
  form.checkValidity = () => true;
  form.classList = createClassList();
  form.elements = [
    fileInput,
    submitButton,
    cancelButton,
    leavePageButton,
    sessionDate,
    notes,
    tags,
    visibility,
    allowDownload,
  ];

  const fakeFile = {
    name: "match.mp4",
    size: fileSize,
    slice(start, end) {
      return { size: end - start };
    },
  };
  fileInput.files = [fakeFile];

  const elements = new Map(
    [
      form,
      fileInput,
      submitButton,
      cancelButton,
      leavePageButton,
      progressContainer,
      progressBar,
      progressStatus,
      progressPercent,
      errorBox,
      sessionDate,
      notes,
      tags,
      visibility,
      allowDownload,
    ].map((element) => [element.id, element])
  );

  const fetchCalls = [];
  const s3PutUrls = [];

  const document = {
    getElementById(id) {
      return elements.get(id) || null;
    },
  };

  const location = {
    assigned: null,
    assign(url) {
      this.assigned = url;
    },
  };

  const fetch = async (url, options = {}) => {
    fetchCalls.push({ url, options });
    return fetchHandler({ url, options, fetchCalls, scenarioName });
  };

  class FakeXMLHttpRequest {
    constructor() {
      this.status = 0;
      this.url = "";
      this._etag = null;
      this._eventHandlers = new Map();
      this.upload = {
        addEventListener: (event, handler) => {
          this._eventHandlers.set(`upload:${event}`, handler);
        },
      };
    }

    open(_method, url) {
      this.url = url;
    }

    addEventListener(event, handler) {
      this._eventHandlers.set(event, handler);
    }

    getResponseHeader(name) {
      if (name === "ETag" && this.status >= 200 && this.status < 300) {
        return this._etag || '"etag-1"';
      }
      return null;
    }

    send(blob) {
      s3PutUrls.push(this.url);
      const progressHandler = this._eventHandlers.get("upload:progress");
      if (progressHandler) {
        progressHandler({ lengthComputable: true, loaded: blob.size });
      }
      const outcome = xhrSendHandler({
        url: this.url,
        blob,
        putIndex: s3PutUrls.length,
        nowController,
      });
      this.status = outcome.status;
      this._etag = outcome.etag || '"etag-1"';
      if (outcome.event === "error") {
        this._eventHandlers.get("error")?.();
        return;
      }
      this._eventHandlers.get("load")?.();
    }

    abort() {
      this._eventHandlers.get("abort")?.();
    }
  }

  const FakeDate = class extends Date {};
  FakeDate.now = () => nowController.now();

  const context = {
    window: {
      setTimeout: (handler) => {
        handler();
      },
      addEventListener() {},
      location,
    },
    document,
    fetch,
    XMLHttpRequest: FakeXMLHttpRequest,
    DOMException,
    console,
    Date: FakeDate,
    Promise,
    Math,
    Set,
    JSON,
  };
  context.window.window = context.window;

  const scriptPath = path.join(__dirname, "..", "static", "upload.js");
  const scriptSource = fs.readFileSync(scriptPath, "utf8");
  vm.runInNewContext(scriptSource, context, { filename: "upload.js" });

  const submitHandler = form.getHandler("submit");
  assert.ok(submitHandler, `${scenarioName}: submit handler should be registered`);
  await submitHandler({ preventDefault() {} });

  return { fetchCalls, s3PutUrls, location, errorText: errorBox.textContent };
}

async function scenarioSuccessRetryAndSingleFlight() {
  let csrfTokenGetCount = 0;
  let refreshPartCallCount = 0;
  const nowController = {
    value: 0,
    now() {
      this.value += 700;
      return this.value;
    },
  };

  const result = await runUploadScenario({
    scenarioName: "success-retry-single-flight",
    uploadConcurrency: 2,
    fileSize: 20,
    csrfLifetimeSeconds: 2,
    fetchHandler: async ({ url, options }) => {
      if (url === "/api/csrf-token" && options.method === "GET") {
        csrfTokenGetCount += 1;
        await Promise.resolve();
        return makeFetchResponse(200, { csrf_token: "csrf-new", expires_in: 3600 });
      }
      if (url === "/api/uploads/multipart/initiate") {
        assert.equal(options.headers["X-CSRFToken"], "csrf-old");
        return makeFetchResponse(200, {
          upload_token: "token-1",
          upload_token_expires_in: 1,
          part_size: 10,
          total_parts: 2,
          parts: [
            { part_number: 1, url: "https://s3/original-1" },
            { part_number: 2, url: "https://s3/original-2" },
          ],
          expires_in: 1,
        });
      }
      if (url === "/api/uploads/multipart/refresh-part") {
        refreshPartCallCount += 1;
        assert.equal(options.headers["X-CSRFToken"], "csrf-new");
        const requestBody = JSON.parse(options.body);
        if (requestBody.part_number === 1 && requestBody.upload_token === "token-2") {
          return makeFetchResponse(200, {
            part_number: 1,
            url: "https://s3/refreshed-retry",
            expires_in: 3600,
            upload_token: "token-3",
            upload_token_expires_in: 3600,
          });
        }
        if (requestBody.part_number === 1) {
          return makeFetchResponse(200, {
            part_number: 1,
            url: "https://s3/refreshed-proactive",
            expires_in: 3600,
            upload_token: "token-2",
            upload_token_expires_in: 3600,
          });
        }
        if (requestBody.part_number === 2) {
          return makeFetchResponse(200, {
            part_number: 2,
            url: "https://s3/refreshed-proactive-2",
            expires_in: 3600,
            upload_token: "token-2",
            upload_token_expires_in: 3600,
          });
        }
        throw new Error(`Unexpected part_number ${requestBody.part_number}`);
      }
      if (url === "/api/uploads/multipart/complete") {
        const requestBody = JSON.parse(options.body);
        assert.notEqual(requestBody.upload_token, "token-1");
        assert.equal(requestBody.parts.length, 2);
        return makeFetchResponse(200, { redirect_url: "/videos/123" });
      }
      if (url === "/api/uploads/multipart/abort") {
        return makeFetchResponse(200, { aborted: true });
      }
      throw new Error(`Unexpected fetch URL ${url}`);
    },
    xhrSendHandler: ({ putIndex }) => {
      if (putIndex === 1) {
        return { status: 500 };
      }
      return { status: 200 };
    },
    nowController,
  });

  assert.equal(csrfTokenGetCount, 1);
  assert.ok(refreshPartCallCount >= 3);
  assert.ok(result.s3PutUrls.includes("https://s3/refreshed-proactive"));
  assert.ok(result.s3PutUrls.includes("https://s3/refreshed-proactive-2"));
  assert.ok(result.s3PutUrls.includes("https://s3/refreshed-retry"));
  assert.equal(result.location.assigned, "/videos/123");
  assert.equal(
    result.fetchCalls.some((call) => call.url === "/api/uploads/multipart/abort"),
    false
  );
}

async function scenarioRenewalFailureBlocksNextPutAndComplete() {
  const nowController = {
    value: 0,
    now() {
      this.value += 1000;
      return this.value;
    },
  };

  const result = await runUploadScenario({
    scenarioName: "renewal-failure-blocks-put",
    uploadConcurrency: 1,
    fileSize: 10,
    csrfLifetimeSeconds: 3600,
    fetchHandler: async ({ url, options }) => {
      if (url === "/api/uploads/multipart/initiate") {
        return makeFetchResponse(200, {
          upload_token: "token-1",
          upload_token_expires_in: 1,
          part_size: 10,
          total_parts: 1,
          parts: [{ part_number: 1, url: "https://s3/original-1" }],
          expires_in: 3600,
        });
      }
      if (url === "/api/uploads/multipart/refresh-part") {
        return makeFetchResponse(502, { error: "Could not refresh upload URL." });
      }
      if (url === "/api/uploads/multipart/complete") {
        throw new Error("complete should not be called when renewal fails");
      }
      if (url === "/api/uploads/multipart/abort") {
        return makeFetchResponse(200, { aborted: true });
      }
      if (url === "/api/csrf-token") {
        return makeFetchResponse(200, { csrf_token: "csrf-new", expires_in: 3600 });
      }
      throw new Error(`Unexpected fetch URL ${url}`);
    },
    xhrSendHandler: () => ({ status: 200 }),
    nowController,
  });

  assert.equal(result.s3PutUrls.length, 0);
  assert.equal(
    result.fetchCalls.some((call) => call.url === "/api/uploads/multipart/complete"),
    false
  );
  assert.equal(
    result.fetchCalls.some((call) => call.url === "/api/uploads/multipart/abort"),
    true
  );
}

async function scenarioFinalTokenRefreshBeforeComplete() {
  const nowController = {
    value: 0,
    now() {
      return this.value;
    },
    advance(ms) {
      this.value += ms;
    },
  };

  const result = await runUploadScenario({
    scenarioName: "refresh-before-complete",
    uploadConcurrency: 1,
    fileSize: 20,
    csrfLifetimeSeconds: 3600,
    fetchHandler: async ({ url, options }) => {
      if (url === "/api/uploads/multipart/initiate") {
        return makeFetchResponse(200, {
          upload_token: "token-1",
          upload_token_expires_in: 20,
          part_size: 10,
          total_parts: 2,
          parts: [
            { part_number: 1, url: "https://s3/part-1" },
            { part_number: 2, url: "https://s3/part-2" },
          ],
          expires_in: 3600,
        });
      }
      if (url === "/api/uploads/multipart/refresh-part") {
        const requestBody = JSON.parse(options.body);
        assert.equal(requestBody.part_number, 2);
        assert.equal(requestBody.upload_token, "token-1");
        return makeFetchResponse(200, {
          part_number: 2,
          url: "https://s3/part-2-refresh-before-complete",
          expires_in: 3600,
          upload_token: "token-2",
          upload_token_expires_in: 3600,
        });
      }
      if (url === "/api/uploads/multipart/complete") {
        const requestBody = JSON.parse(options.body);
        assert.equal(requestBody.upload_token, "token-2");
        return makeFetchResponse(200, { redirect_url: "/videos/456" });
      }
      if (url === "/api/uploads/multipart/abort") {
        return makeFetchResponse(200, { aborted: true });
      }
      if (url === "/api/csrf-token") {
        return makeFetchResponse(200, { csrf_token: "csrf-new", expires_in: 3600 });
      }
      throw new Error(`Unexpected fetch URL ${url}`);
    },
    xhrSendHandler: ({ putIndex, nowController: nc }) => {
      if (putIndex === 1) {
        nc.advance(3000);
      } else if (putIndex === 2) {
        nc.advance(9000);
      }
      return { status: 200 };
    },
    nowController,
  });

  assert.equal(result.location.assigned, "/videos/456");
  assert.equal(
    result.fetchCalls.filter((call) => call.url === "/api/uploads/multipart/refresh-part")
      .length,
    1
  );
  assert.equal(
    result.fetchCalls.some((call) => call.url === "/api/uploads/multipart/abort"),
    false
  );
}

async function main() {
  await scenarioSuccessRetryAndSingleFlight();
  await scenarioRenewalFailureBlocksNextPutAndComplete();
  await scenarioFinalTokenRefreshBeforeComplete();
  console.log("upload client behavior test passed");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
