import React, { useState } from "react";
import { Copy, Linkedin, RefreshCw, Share2 } from "lucide-react";

/**
 * Phase-1 LinkedIn flow: generate a caption from verified learnings, let the
 * user edit it, then open LinkedIn's own composer via a share link. LinkedIn's
 * API has no "draft into composer" — so review happens here, posting happens there.
 */
function LinkedInShare({ caption, onCaptionChange, onGenerateCaption, onCreateShare, shareUrl, status, sourceCount }) {
  const [copied, setCopied] = useState(false);
  const isLoading = status === "loading";

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(caption ?? "");
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section className="panel linkedin-share" id="linkedin-share">
      <header className="panel-heading">
        <Linkedin size={20} />
        <div>
          <h2>Share your progress on LinkedIn</h2>
          <p>Turn your verified learnings into a post. You review it here, then post in LinkedIn's composer.</p>
        </div>
      </header>

      <button type="button" className="secondary-button" onClick={onGenerateCaption} disabled={isLoading}>
        <RefreshCw size={16} /> {isLoading ? "Writing..." : caption ? "Regenerate caption" : "Generate caption"}
      </button>
      {sourceCount === 0 && (
        <p className="schedule-hint">Complete a few sessions with reflections first — they become the post.</p>
      )}

      {caption !== null && caption !== undefined && (
        <>
          <textarea
            className="linkedin-caption"
            value={caption}
            onChange={(event) => onCaptionChange(event.target.value)}
            rows={8}
            aria-label="LinkedIn caption"
          />
          <div className="linkedin-actions">
            <button type="button" className="ghost-button" onClick={handleCopy}>
              <Copy size={16} /> {copied ? "Copied!" : "Copy caption"}
            </button>
            {shareUrl ? (
              <a className="secondary-button" href={shareUrl} target="_blank" rel="noreferrer">
                <Linkedin size={16} /> Open LinkedIn composer
              </a>
            ) : (
              <button type="button" className="secondary-button" onClick={onCreateShare} disabled={isLoading}>
                <Share2 size={16} /> Create share link
              </button>
            )}
          </div>
          <p className="linkedin-note">
            Tip: LinkedIn only pre-fills the link preview. Paste your copied caption into the composer, then post.
          </p>
        </>
      )}
    </section>
  );
}

export default LinkedInShare;
