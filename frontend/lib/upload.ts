// Client-side checks are only for quick feedback. The server re-checks
// everything from the file's actual bytes (SR-1..3), for posts and scans alike.
export const ACCEPT = "image/jpeg,image/png,image/gif,video/mp4";
export const MAX_IMAGE_MB = 10;
export const MAX_VIDEO_MB = 50;

export function precheck(file: File): string | null {
  if (!ACCEPT.split(",").includes(file.type)) return "Choose a JPEG, PNG or GIF image, or an MP4 video.";
  const isVideo = file.type.startsWith("video/");
  const limit = isVideo ? MAX_VIDEO_MB : MAX_IMAGE_MB;
  if (file.size > limit * 1024 * 1024) return `That file is over ${limit} MB.`;
  return null;
}
