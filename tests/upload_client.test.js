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

async function main() {
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
    csrfTokenLifetimeSeconds: "1",
    maxFileSize: String(3 * 1024 * 1024 * 1024),
    uploadConcurrency: "1",
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
    size: 15,
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
  let refreshPartCallCount = 0;

  const makeFetchResponse = (status, payload) => ({
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return payload;
    },
    async text() {
      return JSON.stringify(payload);
    },
  });

  const fetch = async (url, options = {}) => {
    fetchCalls.push({ url, options });
    if (url === "/api/csrf-token" && options.method === "GET") {
      return makeFetchResponse(200, { csrf_token: "csrf-new", expires_in: 3600 });
    }
    if (url === "/api/uploads/multipart/initiate") {
      assert.equal(options.headers["X-CSRFToken"], "csrf-new");
      return makeFetchResponse(200, {
        upload_token: "token-1",
        upload_token_expires_in: 1,
        part_size: 16 * 1024 * 1024,
        total_parts: 1,
        parts: [{ part_number: 1, url: "https://s3/original" }],
        expires_in: 1,
      });
    }
    if (url === "/api/uploads/multipart/refresh-part") {
      refreshPartCallCount += 1;
      const requestBody = JSON.parse(options.body);
      if (refreshPartCallCount === 1) {
        assert.equal(requestBody.upload_token, "token-1");
        return makeFetchResponse(200, {
          part_number: 1,
          url: "https://s3/refreshed-proactive",
          expires_in: 3600,
          upload_token: "token-2",
          upload_token_expires_in: 1,
        });
      }
      assert.equal(requestBody.upload_token, "token-2");
      return makeFetchResponse(200, {
        part_number: 1,
        url: "https://s3/refreshed-retry",
        expires_in: 3600,
        upload_token: "token-3",
        upload_token_expires_in: 3600,
      });
    }
    if (url === "/api/uploads/multipart/complete") {
      const requestBody = JSON.parse(options.body);
      assert.equal(requestBody.upload_token, "token-3");
      return makeFetchResponse(200, { redirect_url: "/videos/123" });
    }
    if (url === "/api/uploads/multipart/abort") {
      return makeFetchResponse(200, { aborted: true });
    }
    throw new Error(`Unexpected fetch URL ${url}`);
  };

  class FakeXMLHttpRequest {
    constructor() {
      this.status = 0;
      this.url = "";
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
        return '"etag-1"';
      }
      return null;
    }

    send(blob) {
      s3PutUrls.push(this.url);
      const progressHandler = this._eventHandlers.get("upload:progress");
      if (progressHandler) {
        progressHandler({ lengthComputable: true, loaded: blob.size });
      }

      if (s3PutUrls.length === 1) {
        this.status = 500;
      } else {
        this.status = 200;
      }
      this._eventHandlers.get("load")?.();
    }

    abort() {
      this._eventHandlers.get("abort")?.();
    }
  }

  const document = {
    getElementById(id) {
      return elements.get(id) || null;
    },
  };

  const windowEventHandlers = new Map();
  const location = {
    assigned: null,
    assign(url) {
      this.assigned = url;
    },
  };

  let fakeNow = 0;
  Date.now = () => {
    fakeNow += 700;
    return fakeNow;
  };

  const context = {
    window: {
      setTimeout: (handler) => {
        handler();
      },
      addEventListener(event, handler) {
        windowEventHandlers.set(event, handler);
      },
      location,
    },
    document,
    fetch,
    XMLHttpRequest: FakeXMLHttpRequest,
    DOMException,
    console,
    Date,
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
  assert.ok(submitHandler, "submit handler should be registered");
  await submitHandler({
    preventDefault() {},
  });

  assert.equal(refreshPartCallCount, 2, "refresh endpoint should be called twice");
  assert.deepEqual(s3PutUrls, [
    "https://s3/refreshed-proactive",
    "https://s3/refreshed-retry",
  ]);

  const csrfFetch = fetchCalls.find(
    (call) => call.url === "/api/csrf-token" && call.options.method === "GET"
  );
  assert.ok(csrfFetch, "csrf token refresh should be requested");

  const completeCall = fetchCalls.find(
    (call) => call.url === "/api/uploads/multipart/complete"
  );
  assert.ok(completeCall, "complete endpoint should be called");

  const abortCall = fetchCalls.find((call) => call.url === "/api/uploads/multipart/abort");
  assert.equal(abortCall, undefined, "abort endpoint should not be called on recovery");
  assert.equal(location.assigned, "/videos/123");

  console.log("upload client behavior test passed");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
