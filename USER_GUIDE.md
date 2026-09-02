# Badminton Video Vault — User Guide

Badminton Video Vault is a private web application for uploading, organising, playing, and sharing badminton session videos.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Logging In](#logging-in)
3. [Dashboard](#dashboard)
4. [Uploading Videos](#uploading-videos)
5. [Browsing Your Video Library](#browsing-your-video-library)
6. [Viewing and Playing Videos](#viewing-and-playing-videos)
7. [Editing Video Details](#editing-video-details)
8. [Sharing Videos](#sharing-videos)
9. [Downloading Videos](#downloading-videos)
10. [Deleting Videos](#deleting-videos)
11. [Admin Features](#admin-features)
12. [Frequently Asked Questions](#frequently-asked-questions)
13. [Troubleshooting](#troubleshooting)

---

## Getting Started

You need:

- A modern browser such as Chrome, Edge, Firefox, or Safari
- An account created by the administrator
- A stable internet connection, especially for large uploads
- JavaScript enabled for video uploads

### Supported Formats

| Format | Extension |
|---|---|
| MP4 | `.mp4` |
| AVI | `.avi` |
| QuickTime | `.mov` |
| Matroska | `.mkv` |
| WebM | `.webm` |

The default maximum file size is **3 GiB**. An administrator can configure a different limit.

---

## Logging In

1. Open the application URL.
2. Enter your email address and password.
3. Select **Log In**.

After login, the application opens the Dashboard.

Select **Log Out** from the user menu to end the session.

---

## Dashboard

The Dashboard shows:

- Your total number of videos
- Your five most recently uploaded videos
- Links to upload a new video or browse the full library

---

## Uploading Videos

### How Uploading Works

The browser divides the video into smaller parts and sends those parts **directly to the private Amazon S3 bucket**. The application server coordinates the upload and saves the title, date, notes, tags, visibility, and file size only after S3 confirms completion.

This design avoids copying a multi-gigabyte video through the application server and allows failed parts to be retried independently.

### Step by Step

1. Select **Upload** from the navigation menu.
2. Complete the form:

   | Field | Required | Description |
   |---|---|---|
   | Video File | Yes | MP4, AVI, MOV, MKV, or WebM |
   | Session Date | No | Date of the badminton session |
   | Notes | No | Up to 2,000 characters |
   | Tags | No | Comma-separated labels such as `singles, tournament, training` |
   | Visibility | Yes | Private, Shared link, or Public |
   | Allow Download | No | Whether permitted viewers may download the file |

3. Select **Upload**.
4. Keep the page open while the progress bar advances.
5. The application redirects to the video page after S3 completion and metadata verification.

### Progress, Retry, and Cancellation

- Several parts may upload in parallel.
- A failed part is retried automatically up to three times.
- Select **Cancel Upload** to stop the active requests and ask S3 to discard the incomplete upload.
- Do not close or reload the page during an upload. Uploads do not currently resume after the page is closed.
- If the browser cannot contact S3, verify your network and report the error message to the administrator; the bucket CORS configuration may need attention.

### Large-File Tips

- Prefer a stable wired or strong Wi-Fi connection.
- Disable sleep mode during a long upload.
- A 3 GiB upload can take many minutes on a slow upstream connection.
- The final percentage may pause briefly while S3 combines the parts and the application saves metadata.

---

## Browsing Your Video Library

Select **My Videos** to see:

- Every video you uploaded, regardless of visibility
- Videos marked Public by other users

Filter by tag or visibility. Results are paginated when the library grows.

---

## Viewing and Playing Videos

Open a video to:

- Play it in the browser
- View filename, session date, size, tags, notes, and visibility
- Edit details when you are the owner or an administrator
- Download it when downloads are enabled
- Delete it when authorised

Playback links are temporary. Refresh the page to obtain a fresh link if playback later stops.

---

## Editing Video Details

The uploader or an administrator can change:

- Session date
- Notes
- Tags
- Visibility
- Download permission

Select **Save Changes** to apply the update.

---

## Sharing Videos

### Private

Only the uploader and administrators can access the video.

### Shared Link

Anyone with the generated link can open the video without logging in. The application-level share link expires after 30 days. The S3 playback URL embedded in the page has a shorter security lifetime and is regenerated whenever the page is loaded.

### Public

All logged-in users can see the video in the library.

To share outside the user community, select **Shared (link)** rather than Public.

---

## Downloading Videos

A Download button appears only when **Allow Download** is enabled. Download URLs are temporary; refresh the video page when an old URL expires.

---

## Deleting Videos

1. Open the video.
2. Select **Delete Video**.
3. Confirm the warning.

Deletion removes both the S3 object and the metadata record. It cannot be undone unless an administrator has a separate backup.

---

## Admin Features

Administrators can:

- View user accounts
- Create users
- Assign User or Admin roles
- Activate or deactivate accounts

Deactivation prevents login but preserves existing video metadata and S3 objects.

---

## Frequently Asked Questions

### What formats and sizes are accepted?

MP4, AVI, MOV, MKV, and WebM. The default maximum is 3 GiB.

### Can I upload several videos at once?

Not currently. Complete one upload before starting the next.

### Does the video pass through the EC2 server?

No. After the server authorises the upload, the browser sends each video part directly to private S3 using temporary presigned URLs.

### Can an interrupted upload resume after closing the browser?

Not yet. Individual parts retry automatically while the page remains open, but a closed or refreshed page requires a new upload.

### Can someone with a share link download the video?

Only when **Allow Download** is enabled.

### Why did playback stop?

The temporary playback URL may have expired. Refresh the page.

### Is there a limit on the number of videos?

The application does not impose a count limit, although S3 storage and transfer charges still apply.

---

## Troubleshooting

| Problem | Suggested action |
|---|---|
| Cannot log in | Check the email and password; ask the administrator whether the account is active |
| Upload rejected immediately | Confirm the extension is supported and the file is within the displayed limit |
| Upload reports a CORS or missing ETag error | Send the exact message and application URL to the administrator; the S3 CORS origin or exposed headers may be wrong |
| Upload repeatedly fails on one part | Check network stability and retry; the application automatically attempts each part three times |
| Browser was closed during upload | Start a new upload; incomplete S3 parts are cleaned up by cancellation or the bucket lifecycle rule |
| Upload reaches 100% and pauses | Wait while S3 completes the multipart object and the application records metadata |
| Video will not play | Refresh the page to generate a new playback URL |
| Share link is expired | Ask the owner to generate a new Shared link |
| 500 error | Record the time and action, then contact the administrator |

---

*Badminton Video Vault — Store, organise, and share your badminton journey.*
