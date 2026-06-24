import React, { useMemo } from "react";
import { BookOpen, Check, Download, FolderGit2, GraduationCap, Save, Video } from "lucide-react";

const TYPE_ICON = {
  video: Video,
  course: GraduationCap,
  book: BookOpen,
  project: FolderGit2,
};

const formatWhen = (startUtc, endUtc) => {
  try {
    const start = new Date(startUtc);
    const end = new Date(endUtc);
    const day = start.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
    const time = `${start.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`;
    const endTime = end.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    return `${day} · ${time}–${endTime}`;
  } catch {
    return startUtc;
  }
};

/**
 * Renders a generated/saved schedule grouped by week, with export + save and
 * a per-session "mark done" that requires a reflection (proof of learning).
 */
function ScheduleCalendar({ schedule, progress, isSaved, canSave, onExport, onSave, onMarkDone, saveStatus }) {
  const weeks = useMemo(() => {
    const grouped = new Map();
    (schedule.sessions ?? []).forEach((session) => {
      const key = session.week_index ?? 0;
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(session);
    });
    return [...grouped.entries()].sort((a, b) => a[0] - b[0]);
  }, [schedule.sessions]);

  if (!schedule.sessions?.length) {
    return (
      <section className="panel schedule-result">
        <p className="schedule-hint">No sessions could fit. Add more free time or widen your content mix.</p>
      </section>
    );
  }

  return (
    <section className="panel schedule-result" id="schedule-result" aria-live="polite">
      <header className="schedule-result-head">
        <div>
          <h3>Your study schedule</h3>
          <p>{schedule.summary}</p>
        </div>
        <div className="schedule-actions">
          <button type="button" className="secondary-button" onClick={onExport}>
            <Download size={16} /> Add to calendar (.ics)
          </button>
          <button type="button" className="secondary-button" onClick={onSave} disabled={!canSave || isSaved || saveStatus === "loading"}>
            <Save size={16} /> {isSaved ? "Saved" : saveStatus === "loading" ? "Saving..." : "Save schedule"}
          </button>
        </div>
      </header>

      {progress && (
        <div className="schedule-progress">
          <div className="schedule-progress-bar">
            <span style={{ width: `${progress.percent}%` }} />
          </div>
          <small>{progress.completed} of {progress.total} sessions completed ({progress.percent}%)</small>
        </div>
      )}

      {!isSaved && (
        <p className="schedule-hint">Save the schedule to track progress and mark sessions complete.</p>
      )}

      <div className="schedule-weeks">
        {weeks.map(([weekIndex, sessions]) => (
          <div className="schedule-week" key={weekIndex}>
            <h4>Week {weekIndex + 1}</h4>
            <ul className="session-list">
              {sessions.map((session) => {
                const Icon = TYPE_ICON[session.resource_type] ?? GraduationCap;
                const done = session.status === "completed";
                return (
                  <li key={session.uid ?? session.id} className={`session-card${done ? " done" : ""}`}>
                    <span className="session-icon"><Icon size={18} /></span>
                    <div className="session-body">
                      <div className="session-when">{formatWhen(session.start_utc, session.end_utc)}</div>
                      {session.resource_url ? (
                        <a href={session.resource_url} target="_blank" rel="noreferrer" className="session-title">
                          {session.resource_title}
                        </a>
                      ) : (
                        <span className="session-title">{session.resource_title}</span>
                      )}
                      {session.goal && <p className="session-goal">{session.goal}</p>}
                      <span className="session-tag">{session.resource_type}{session.skill ? ` · ${session.skill}` : ""}</span>
                    </div>
                    <div className="session-action">
                      {done ? (
                        <span className="session-done-badge"><Check size={14} /> Done</span>
                      ) : (
                        <button
                          type="button"
                          className="ghost-button"
                          onClick={() => onMarkDone(session)}
                          disabled={!isSaved}
                        >
                          Mark done
                        </button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

export default ScheduleCalendar;
