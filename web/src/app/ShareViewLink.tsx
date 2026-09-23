import { Link2 } from "lucide-react";
import { useState } from "react";

export interface ShareViewLinkProps {
  readonly getUrl?: () => string;
  readonly writeClipboard?: (value: string) => Promise<void>;
}

type ShareStatus = "idle" | "copied" | "failed";

function currentUrl(): string {
  return window.location.href;
}

async function writeCurrentUrl(value: string): Promise<void> {
  if (!navigator.clipboard?.writeText) {
    throw new Error("Clipboard API unavailable");
  }
  await navigator.clipboard.writeText(value);
}

function statusMessage(status: ShareStatus): string {
  if (status === "copied") {
    return "View link copied.";
  }
  if (status === "failed") {
    return "Copy unavailable. Use your browser address bar.";
  }
  return "";
}

export function ShareViewLink({
  getUrl = currentUrl,
  writeClipboard = writeCurrentUrl,
}: ShareViewLinkProps) {
  const [status, setStatus] = useState<ShareStatus>("idle");
  const statusText = statusMessage(status);

  const handleCopy = async () => {
    try {
      await writeClipboard(getUrl());
      setStatus("copied");
    } catch {
      setStatus("failed");
    }
  };

  return (
    <div className="share-view-link">
      <button type="button" className="share-view-link-button" onClick={() => void handleCopy()}>
        <Link2 size={15} aria-hidden="true" />
        <span>Copy view link</span>
      </button>
      <output className="share-view-link-status" aria-live="polite">{statusText}</output>
    </div>
  );
}
