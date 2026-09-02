(() => {
  "use strict";

  const form = document.getElementById("uploadForm");
  if (!form) {
    return;
  }

  const fileInput = document.getElementById("video_file");
  const submitButton = document.getElementById("submitBtn");
  const cancelButton = document.getElementById("cancelUploadBtn");
  const leavePageButton = document.getElementById("leavePageBtn");
  const progressContainer = document.getElementById("uploadProgress");
  const progressBar = document.getElementById("uploadProgressBar");
  const progressStatus = document.getElementById("uploadStatus");
  const progressPercent = document.getElementById("uploadPercent");
  const errorBox = document.getElementById("uploadError");
  let csrfToken = form.querySelector('input[name="csrf_token"]').value;

  const initiateUrl = form.dataset.initiateUrl;
  const completeUrl = form.dataset.completeUrl;
  const abortUrl = form.dataset.abortUrl;
  const refreshPartUrlEndpoint = form.dataset.refreshPartUrl;
  const csrfTokenUrl = form.dataset.csrfTokenUrl;
  const maxFileSize = Number(form.dataset.maxFileSize);
  const csrfTokenLifetimeSeconds = Number(form.dataset.csrfTokenLifetimeSeconds);
  // Refresh a part's presigned URL this far ahead of its expiry so that a
  // slow upload never attempts to PUT with an already-expired signature.
  const PART_URL_REFRESH_BUFFER_MS = 5 * 60 * 1000;
  const CSRF_REFRESH_BUFFER_MS = 5 * 60 * 1000;
  const UPLOAD_TOKEN_REFRESH_BUFFER_MS = 10 * 60 * 1000;
  const uploadConcurrency = Math.max(
    1,
    Number(form.dataset.uploadConcurrency) || 3
  );
  const allowedExtensions = new Set(["mp4", "avi", "mov", "mkv", "webm"]);

  const activeRequests = new Set();
  let uploadToken = null;
  let uploadTokenIssuedAt = 0;
  let uploadTokenMaxAgeMs = 0;
  let csrfTokenIssuedAt = Date.now();
  let csrfTokenMaxAgeMs =
    Number.isFinite(csrfTokenLifetimeSeconds) && csrfTokenLifetimeSeconds > 0
      ? csrfTokenLifetimeSeconds * 1000
      : 0;
  let csrfTokenRefreshPromise = null;
  let uploadInProgress = false;
  let uploadCompleted = false;
  let cancelRequested = false;

  function formatBytes(bytes) {
    const units = ["B", "KiB", "MiB", "GiB"];
    let value = bytes;
    let unitIndex = 0;
    while (value >= 1024 && unitIndex < units.length - 1) {
      value /= 1024;
      unitIndex += 1;
    }
    return `${value.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.classList.remove("d-none");
    errorBox.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function clearError() {
    errorBox.textContent = "";
    errorBox.classList.add("d-none");
  }

  function setProgress(percent, status) {
    const bounded = Math.max(0, Math.min(100, Math.round(percent)));
    progressBar.style.width = `${bounded}%`;
    progressBar.setAttribute("aria-valuenow", String(bounded));
    progressPercent.textContent = `${bounded}%`;
    if (status) {
      progressStatus.textContent = status;
    }
  }

  function setBusy(isBusy) {
    uploadInProgress = isBusy;
    for (const element of form.elements) {
      if (element === cancelButton) {
        continue;
      }
      element.disabled = isBusy;
    }

    leavePageButton.classList.toggle("disabled", isBusy);
    leavePageButton.setAttribute("aria-disabled", isBusy ? "true" : "false");
    cancelButton.classList.toggle("d-none", !isBusy);
    cancelButton.disabled = !isBusy;
    submitButton.textContent = isBusy ? "Uploading…" : "Upload";
    progressContainer.classList.toggle("d-none", !isBusy);
  }

  function isCsrfError(error) {
    return (
      error &&
      error.code === "csrf_failed" &&
      typeof error.message === "string" &&
      error.message.length > 0
    );
  }

  function isExpiredUploadCredentialError(error) {
    const message =
      error && typeof error.message === "string"
        ? error.message.toLowerCase()
        : "";
    return (
      message.includes("upload session has expired") ||
      message.includes("upload session no longer exists") ||
      message.includes("upload token is invalid") ||
      message.includes("upload token does not belong")
    );
  }

  async function refreshCsrfToken() {
    if (!csrfTokenUrl) {
      return;
    }
    const response = await fetch(csrfTokenUrl, {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    const payload = await response.json();
    if (!response.ok) {
      const error = new Error(
        payload.error || `The server returned HTTP ${response.status}.`
      );
      error.httpStatus = response.status;
      error.payload = payload;
      error.code = payload.code;
      throw error;
    }
    csrfToken = payload.csrf_token;
    csrfTokenIssuedAt = Date.now();
    if (
      Number.isFinite(Number(payload.expires_in)) &&
      Number(payload.expires_in) > 0
    ) {
      csrfTokenMaxAgeMs = Number(payload.expires_in) * 1000;
    }
  }

  async function refreshCsrfTokenSingleFlight() {
    if (csrfTokenRefreshPromise) {
      return csrfTokenRefreshPromise;
    }

    csrfTokenRefreshPromise = (async () => {
      await refreshCsrfToken();
    })();

    try {
      await csrfTokenRefreshPromise;
    } finally {
      csrfTokenRefreshPromise = null;
    }
  }

  async function ensureFreshCsrfToken() {
    if (csrfTokenMaxAgeMs <= 0) {
      return;
    }
    const age = Date.now() - csrfTokenIssuedAt;
    const refreshBufferMs = Math.min(
      CSRF_REFRESH_BUFFER_MS,
      Math.floor(csrfTokenMaxAgeMs / 2)
    );
    if (age >= csrfTokenMaxAgeMs - refreshBufferMs) {
      await refreshCsrfTokenSingleFlight();
    }
  }

  async function postJson(url, body, options = {}) {
    if (!options.skipCsrfRefresh) {
      await ensureFreshCsrfToken();
    }

    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      keepalive: Boolean(options.keepalive),
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify(body),
    });

    const text = await response.text();
    let payload = {};
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch (_error) {
        payload = {};
      }
    }

    if (!response.ok) {
      const error = new Error(
        payload.error || `The server returned HTTP ${response.status}.`
      );
      error.httpStatus = response.status;
      error.payload = payload;
      error.code = payload.code;
      if (!options.skipCsrfRefresh && !options._retryingAfterCsrf && isCsrfError(error)) {
        await refreshCsrfTokenSingleFlight();
        return postJson(url, body, {
          ...options,
          _retryingAfterCsrf: true,
        });
      }
      throw error;
    }
    return payload;
  }

  function sleep(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  function computeRefreshBufferMs(maxAgeMs, preferredBufferMs) {
    if (!Number.isFinite(maxAgeMs) || maxAgeMs <= 0) {
      return 0;
    }
    return Math.min(preferredBufferMs, Math.floor(maxAgeMs / 2));
  }

  function isUploadTokenRenewalDue() {
    if (uploadTokenMaxAgeMs <= 0) {
      return false;
    }
    const tokenRefreshBufferMs = computeRefreshBufferMs(
      uploadTokenMaxAgeMs,
      UPLOAD_TOKEN_REFRESH_BUFFER_MS
    );
    return Date.now() - uploadTokenIssuedAt >= uploadTokenMaxAgeMs - tokenRefreshBufferMs;
  }

  function uploadPart(url, blob, partIndex, loadedByPart, updateOverallProgress) {
    return new Promise((resolve, reject) => {
      const s3Request = new XMLHttpRequest();
      activeRequests.add(s3Request);
      s3Request.open("PUT", url, true);

      s3Request.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable) {
          loadedByPart[partIndex] = event.loaded;
          updateOverallProgress();
        }
      });

      s3Request.addEventListener("load", () => {
        activeRequests.delete(s3Request);
        if (s3Request.status < 200 || s3Request.status >= 300) {
          reject(
            new Error(`S3 returned HTTP ${s3Request.status} for an upload part.`)
          );
          return;
        }

        const etag = s3Request.getResponseHeader("ETag");
        if (!etag) {
          reject(
            new Error(
              "S3 did not expose the ETag response header. Update the bucket CORS rule to expose ETag."
            )
          );
          return;
        }

        loadedByPart[partIndex] = blob.size;
        updateOverallProgress();
        resolve(etag);
      });

      s3Request.addEventListener("error", () => {
        activeRequests.delete(s3Request);
        reject(
          new Error(
            "The browser could not upload a part to S3. Check the bucket CORS rule and your network connection."
          )
        );
      });

      s3Request.addEventListener("abort", () => {
        activeRequests.delete(s3Request);
        reject(new DOMException("Upload cancelled", "AbortError"));
      });

      // Blob.slice() without a content type returns a Blob with an empty type,
      // so the presigned request does not depend on a per-part Content-Type.
      s3Request.send(blob);
    });
  }

  async function uploadPartWithRetry(
    part,
    blob,
    partIndex,
    loadedByPart,
    updateOverallProgress,
    partState
  ) {
    const maxAttempts = 3;
    let lastError = null;

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      if (cancelRequested) {
        throw new DOMException("Upload cancelled", "AbortError");
      }

      await ensureFreshPartUrl(part, partIndex, partState);

      try {
        return await uploadPart(
          part.url,
          blob,
          partIndex,
          loadedByPart,
          updateOverallProgress
        );
      } catch (error) {
        lastError = error;
        loadedByPart[partIndex] = 0;
        updateOverallProgress();

        if (
          cancelRequested ||
          error.name === "AbortError" ||
          attempt === maxAttempts
        ) {
          throw error;
        }
        // The part may have failed because its presigned URL expired
        // mid-flight; force a refresh before the next attempt.
        await refreshPartUrl(part, partIndex, partState, {
          requireUploadTokenRenewal: isUploadTokenRenewalDue(),
        });
        await sleep(1000 * 2 ** (attempt - 1));
      }
    }

    throw lastError || new Error("An upload part failed.");
  }

  async function refreshPartUrl(
    part,
    partIndex,
    partState,
    options = {}
  ) {
    if (!refreshPartUrlEndpoint) {
      return;
    }
    try {
      const response = await postJson(refreshPartUrlEndpoint, {
        upload_token: uploadToken,
        part_number: part.part_number,
      });
      part.url = response.url;
      partState.issuedAt[partIndex] = Date.now();
      if (response.upload_token) {
        uploadToken = response.upload_token;
        uploadTokenIssuedAt = Date.now();
      }
      if (response.upload_token_expires_in) {
        uploadTokenMaxAgeMs = response.upload_token_expires_in * 1000;
      }
      if (response.expires_in) {
        partState.expiresInMs = response.expires_in * 1000;
      }
    } catch (error) {
      if (
        options.requireUploadTokenRenewal ||
        isExpiredUploadCredentialError(error)
      ) {
        throw error;
      }
      console.warn("Could not refresh a presigned part URL:", error);
    }
  }

  async function ensureFreshPartUrl(part, partIndex, partState) {
    const age = Date.now() - partState.issuedAt[partIndex];
    let refreshForPartUrl = false;
    if (partState.expiresInMs > 0) {
      const refreshBufferMs = computeRefreshBufferMs(
        partState.expiresInMs,
        PART_URL_REFRESH_BUFFER_MS
      );
      refreshForPartUrl = age >= partState.expiresInMs - refreshBufferMs;
    }

    const refreshForUploadToken = isUploadTokenRenewalDue();

    if (refreshForPartUrl || refreshForUploadToken) {
      await refreshPartUrl(part, partIndex, partState, {
        requireUploadTokenRenewal: refreshForUploadToken,
      });
    }
  }

  async function uploadAllParts(file, initiation) {
    const parts = initiation.parts;
    const loadedByPart = new Array(parts.length).fill(0);
    const completed = new Array(parts.length);
    const issuedAt = new Array(parts.length).fill(Date.now());
    const partState = {
      issuedAt,
      expiresInMs: (Number(initiation.expires_in) || 7200) * 1000,
    };
    let nextPartIndex = 0;
    let completedCount = 0;

    function updateOverallProgress() {
      const uploadedBytes = loadedByPart.reduce(
        (total, value) => total + value,
        0
      );
      const percentage = (uploadedBytes / file.size) * 100;
      setProgress(
        percentage,
        `Uploading ${completedCount} of ${parts.length} parts (${formatBytes(uploadedBytes)} of ${formatBytes(file.size)})`
      );
    }

    async function worker() {
      while (true) {
        const partIndex = nextPartIndex;
        nextPartIndex += 1;
        if (partIndex >= parts.length) {
          return;
        }

        const part = parts[partIndex];
        const start = (part.part_number - 1) * initiation.part_size;
        const end = Math.min(start + initiation.part_size, file.size);
        const blob = file.slice(start, end);

        const etag = await uploadPartWithRetry(
          part,
          blob,
          partIndex,
          loadedByPart,
          updateOverallProgress,
          partState
        );
        completed[partIndex] = {
          part_number: part.part_number,
          etag,
        };
        completedCount += 1;
        updateOverallProgress();
      }
    }

    const workers = Array.from(
      { length: Math.min(uploadConcurrency, parts.length) },
      () => worker()
    );
    await Promise.all(workers);
    return {
      completedParts: completed,
      parts,
      partState,
    };
  }

  async function ensureFreshUploadTokenBeforeComplete(uploadResult) {
    if (!isUploadTokenRenewalDue()) {
      return;
    }
    const lastPartIndex = uploadResult.parts.length - 1;
    if (lastPartIndex < 0) {
      return;
    }
    await refreshPartUrl(
      uploadResult.parts[lastPartIndex],
      lastPartIndex,
      uploadResult.partState,
      { requireUploadTokenRenewal: true }
    );
  }

  async function abortRemoteUpload(options = {}) {
    if (!uploadToken || uploadCompleted) {
      return;
    }

    try {
      await postJson(
        abortUrl,
        { upload_token: uploadToken },
        {
          keepalive: Boolean(options.keepalive),
          skipCsrfRefresh: Boolean(options.keepalive),
        }
      );
    } catch (error) {
      // A bucket lifecycle rule cleans up any incomplete multipart upload if
      // this best-effort abort cannot reach the application.
      console.warn("Could not abort multipart upload:", error);
    }
  }

  function validateSelectedFile(file) {
    if (!file) {
      throw new Error("Choose a video file first.");
    }
    const extension = file.name.includes(".")
      ? file.name.split(".").pop().toLowerCase()
      : "";
    if (!allowedExtensions.has(extension)) {
      throw new Error("Use an MP4, AVI, MOV, MKV, or WebM file.");
    }
    if (file.size <= 0) {
      throw new Error("The selected file is empty.");
    }
    if (file.size > maxFileSize) {
      throw new Error(
        `The selected file is ${formatBytes(file.size)}; the maximum is ${formatBytes(maxFileSize)}.`
      );
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError();
    form.classList.add("was-validated");

    if (!form.checkValidity()) {
      return;
    }

    const file = fileInput.files[0];
    try {
      validateSelectedFile(file);
    } catch (error) {
      showError(error.message);
      return;
    }

    uploadToken = null;
    uploadCompleted = false;
    cancelRequested = false;
    setBusy(true);
    setProgress(0, "Preparing secure multipart upload…");

    try {
      const initiation = await postJson(initiateUrl, {
        filename: file.name,
        file_size: file.size,
        session_date: document.getElementById("session_date").value || null,
        notes: document.getElementById("notes").value,
        tags: document.getElementById("tags").value,
        visibility: document.getElementById("visibility").value,
        allow_download: document.getElementById("allow_download").checked,
      });

      uploadToken = initiation.upload_token;
      uploadTokenIssuedAt = Date.now();
      uploadTokenMaxAgeMs =
        (Number(initiation.upload_token_expires_in) || 0) * 1000;
      setProgress(
        0,
        `Uploading ${initiation.total_parts} part${initiation.total_parts === 1 ? "" : "s"} directly to S3…`
      );

      const uploadResult = await uploadAllParts(file, initiation);
      if (cancelRequested) {
        throw new DOMException("Upload cancelled", "AbortError");
      }
      await ensureFreshUploadTokenBeforeComplete(uploadResult);

      setProgress(100, "Finalising upload and saving metadata…");
      const completion = await postJson(completeUrl, {
        upload_token: uploadToken,
        parts: uploadResult.completedParts,
      });

      uploadCompleted = true;
      progressBar.classList.remove("progress-bar-animated");
      setProgress(100, "Upload complete. Opening the video…");
      window.location.assign(completion.redirect_url);
    } catch (error) {
      for (const s3Request of activeRequests) {
        s3Request.abort();
      }
      activeRequests.clear();
      await abortRemoteUpload();

      if (cancelRequested || error.name === "AbortError") {
        showError("Upload cancelled. No video record was created.");
      } else {
        showError(error.message || "The upload failed. Please try again.");
      }
      setBusy(false);
      setProgress(0, "Upload stopped.");
      uploadToken = null;
    }
  });

  cancelButton.addEventListener("click", async () => {
    if (!uploadInProgress) {
      return;
    }
    cancelRequested = true;
    cancelButton.disabled = true;
    progressStatus.textContent = "Cancelling upload…";
    for (const s3Request of activeRequests) {
      s3Request.abort();
    }
    await abortRemoteUpload();
  });

  leavePageButton.addEventListener("click", (event) => {
    if (uploadInProgress) {
      event.preventDefault();
    }
  });

  window.addEventListener("beforeunload", (event) => {
    if (!uploadInProgress || uploadCompleted) {
      return;
    }

    // Best effort only; the S3 lifecycle rule remains the final cleanup layer.
    abortRemoteUpload({ keepalive: true });
    event.preventDefault();
    event.returnValue = "";
  });
})();
