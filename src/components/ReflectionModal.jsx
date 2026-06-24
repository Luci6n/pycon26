import React, { useState } from "react";
import { X } from "lucide-react";

const MIN_CHARS = 20;

/**
 * Proof-of-learning gate: a session is only "done" once the user writes what
 * they actually learned from the resource.
 */
function ReflectionModal({ session, onSubmit, onClose, status, error }) {
  const [content, setContent] = useState("");
  const trimmed = content.trim();
  const remaining = Math.max(0, MIN_CHARS - trimmed.length);
  const isLoading = status === "loading";

  const handleSubmit = (event) => {
    event.preventDefault();
    if (trimmed.length >= MIN_CHARS) onSubmit(trimmed);
  };

  return (
    <div className="reflection-overlay" role="dialog" aria-modal="true" aria-label="What did you learn?">
      <div className="reflection-modal">
        <button type="button" className="icon-button reflection-close" onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>
        <h3>What did you learn?</h3>
        <p className="reflection-sub">
          From <strong>{session.resource_title}</strong>. Write a few honest takeaways to mark this session complete.
        </p>
        <form onSubmit={handleSubmit}>
          <textarea
            className="reflection-textarea"
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="e.g. I learned how vector databases index embeddings and when to use HNSW vs IVF..."
            rows={5}
            autoFocus
          />
          <div className="reflection-meta">
            {remaining > 0 ? (
              <small>{remaining} more characters needed</small>
            ) : (
              <small className="reflection-ok">Looks good</small>
            )}
          </div>
          {error && <p className="schedule-error" role="alert">{error}</p>}
          <div className="reflection-actions">
            <button type="button" className="ghost-button" onClick={onClose}>Cancel</button>
            <button type="submit" className="secondary-button" disabled={trimmed.length < MIN_CHARS || isLoading}>
              {isLoading ? "Saving..." : "Mark complete"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default ReflectionModal;
