# Badminton Video Vault — User Guide

Welcome to **Badminton Video Vault**, your personal platform for uploading, organizing, and sharing badminton session videos. This guide will walk you through everything you need to get started and make the most of the application.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Logging In](#logging-in)
3. [Dashboard](#dashboard)
4. [Uploading Videos](#uploading-videos)
5. [Browsing Your Video Library](#browsing-your-video-library)
6. [Viewing & Playing Videos](#viewing--playing-videos)
7. [Editing Video Details](#editing-video-details)
8. [Sharing Videos](#sharing-videos)
9. [Downloading Videos](#downloading-videos)
10. [Deleting Videos](#deleting-videos)
11. [Admin Features](#admin-features)
12. [Frequently Asked Questions](#frequently-asked-questions)
13. [Troubleshooting](#troubleshooting)

---

## Getting Started

Badminton Video Vault is a web application — you access it through your browser. No software installation is required on your device.

### What You Need

- A modern web browser (Chrome, Firefox, Safari, or Edge)
- An account created by your administrator
- An internet connection

### Supported Video Formats

You can upload videos in the following formats:

| Format | Extension |
|--------|-----------|
| MP4    | `.mp4`    |
| AVI    | `.avi`    |
| QuickTime | `.mov` |
| Matroska | `.mkv`  |
| WebM   | `.webm`   |

The maximum file size for uploads is **2 GB**.

---

## Logging In

1. Open the application URL in your browser.
2. You will be directed to the **Login** page.
3. Enter your **email address** and **password**.
4. Click **Log In**.

> 💡 **Tip:** If you cannot log in, contact your administrator to verify your account is active and your credentials are correct.

After logging in, you will be redirected to your **Dashboard**.

### Logging Out

Click **Log Out** in the navigation bar at any time to securely end your session.

---

## Dashboard

The Dashboard is your home screen after logging in. It provides a quick overview of your activity:

- **Total Videos** — the number of videos you have uploaded
- **Recent Videos** — your 5 most recently uploaded videos for quick access

From the Dashboard, you can navigate to:
- **Upload** — add a new video
- **Videos** — browse your full video library

---

## Uploading Videos

### Step-by-Step

1. Click **Upload** in the navigation menu.
2. Fill in the upload form:

| Field | Required | Description |
|-------|----------|-------------|
| Video File | ✅ Yes | Select a video file from your device (mp4, avi, mov, mkv, or webm) |
| Session Date | No | The date the badminton session took place |
| Notes | No | Any notes about the session (up to 2,000 characters) |
| Tags | No | Comma-separated tags for organizing videos (e.g., `doubles, tournament, practice`) |
| Visibility | ✅ Yes | Who can see this video (see [Sharing Videos](#sharing-videos)) |
| Allow Download | No | Whether viewers can download the video file |

3. Click **Upload**.
4. Wait for the upload to complete — you will be redirected to the video detail page upon success.

### Tips for Uploading

- **Use descriptive tags** to make videos easy to find later (e.g., `singles, footwork, 2024`).
- **Add a session date** to keep your library chronologically organized.
- **Use notes** to record game scores, practice focuses, or coaching feedback.

---

## Browsing Your Video Library

Click **Videos** in the navigation menu to see your full video library.

### What You Can See

- All videos **you uploaded** (regardless of visibility)
- All videos marked as **Public** by other users

### Filtering Videos

Use the filters at the top of the page to narrow down results:

- **By Tag** — enter a tag to show only videos with that tag
- **By Visibility** — filter by Private, Shared, or Public videos

### Pagination

Videos are displayed 12 per page. Use the pagination controls at the bottom to browse through pages.

---

## Viewing & Playing Videos

Click on any video in your library to open the **Video Detail** page.

On this page you can:

- **Play the video** directly in your browser using the built-in video player
- View all video metadata (filename, upload date, session date, file size, tags, notes)
- Edit video details (if you are the uploader or an admin)
- Download the video (if downloads are enabled)
- Delete the video (if you are the uploader or an admin)

> 💡 **Tip:** Playback links are temporary and automatically expire for security. If a video stops playing, simply refresh the page to get a new playback link.

---

## Editing Video Details

If you uploaded the video (or you are an admin), you can edit its details:

1. Navigate to the video's detail page.
2. Update any of the following fields:
   - **Session Date**
   - **Notes**
   - **Tags**
   - **Visibility** (Private / Shared / Public)
   - **Allow Download** (on/off)
3. Click **Save Changes**.

Changes take effect immediately.

---

## Sharing Videos

Badminton Video Vault offers three visibility levels for each video:

### Private (Default)

- Only **you** (and admins) can see and access the video.
- The video does not appear in other users' libraries.

### Shared (Link)

- Anyone with the **share link** can view the video — no login required.
- Share links expire automatically after **30 days** for security.
- If the link expires, change the visibility back to "Shared" to generate a fresh link.
- Share links are displayed on the video detail page when visibility is set to "Shared".

### Public

- The video is visible to **all logged-in users** in the Videos library.
- Accessing a public video still requires logging in. To share a video with someone who doesn't have an account, use **Shared (link)** visibility instead.

### How to Share a Video

1. Go to the video's detail page.
2. Set **Visibility** to **Shared (link)**.
3. Click **Save Changes**.
4. Copy the **share link** displayed on the page and send it to anyone you want to view the video — no login required.

---

## Downloading Videos

If a video has **Allow Download** enabled:

- A **Download** button will appear on the video detail page.
- Clicking it will start downloading the video file to your device.
- Download links are temporary and expire after a set period — refresh the page if needed.

> 💡 **Tip:** To enable or disable downloads for your videos, edit the video and toggle the "Allow Download" checkbox.

---

## Deleting Videos

To permanently delete a video:

1. Navigate to the video's detail page.
2. Click the **Delete** button.
3. Confirm the deletion.

> ⚠️ **Warning:** Deletion is permanent. The video file is removed from storage and cannot be recovered.

Only the video's uploader or an admin can delete a video.

---

## Admin Features

If your account has the **Admin** role, you have access to additional user management features.

### Managing Users

Navigate to **Admin > Users** to see a list of all registered users, including:

- Name and email
- Role (User or Admin)
- Account status (Active / Inactive)
- Number of videos uploaded

### Creating a New User

1. Go to **Admin > Users**.
2. Click **Create User**.
3. Fill in the form:
   - **Full Name** — the user's display name
   - **Email** — used for login (must be unique)
   - **Password** — minimum 8 characters
   - **Confirm Password** — must match
   - **Role** — User or Admin
4. Click **Create User**.

The new user can immediately log in with the provided credentials.

### Activating / Deactivating Users

- Click the **Activate** or **Deactivate** button next to a user to toggle their account status.
- Deactivated users **cannot log in** but their data (videos, etc.) is preserved.
- You cannot deactivate your own admin account.

---

## Frequently Asked Questions

### Q: What video formats can I upload?

**A:** MP4, AVI, MOV, MKV, and WebM files up to 2 GB in size.

### Q: Can I upload multiple videos at once?

**A:** Currently, videos must be uploaded one at a time.

### Q: How long do share links last?

**A:** Share links expire after 30 days. You can regenerate a link by setting the video back to "Shared" visibility.

### Q: Can someone with a share link download my video?

**A:** Only if you have enabled "Allow Download" for that video.

### Q: Why did my video stop playing?

**A:** Playback links expire after a period of time for security. Simply refresh the page to resume watching.

### Q: Can I change my password?

**A:** Contact your administrator to have your password reset.

### Q: What happens to my videos if my account is deactivated?

**A:** Your videos remain stored but are not accessible until your account is reactivated by an administrator.

### Q: Is there a limit to how many videos I can upload?

**A:** There is no enforced limit on the number of videos. However, individual files cannot exceed 2 GB.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Cannot log in | Verify your email and password. Contact your admin if your account may be deactivated. |
| Upload fails | Check that your file is a supported format and under 2 GB. Ensure you have a stable internet connection. |
| Video won't play | Refresh the page to get a new playback link. Try a different browser if the issue persists. |
| Share link returns "expired" | The link has passed its 30-day expiry. Ask the video owner to regenerate the share link. |
| "Permission denied" error | You may be trying to access a private video that isn't yours. Contact the video owner. |
| Page shows "500 error" | An internal error occurred. Try again later or contact your administrator. |

---

## Need Help?

If you encounter issues not covered in this guide, please reach out to your system administrator for assistance.

---

*Badminton Video Vault — Store, organize, and share your badminton journey.* 🏸
