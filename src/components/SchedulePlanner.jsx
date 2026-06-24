import React, { useState } from "react";
import { CalendarClock, Plus, Trash2 } from "lucide-react";

const WEEKDAYS = [
  { value: 0, label: "Mon" },
  { value: 1, label: "Tue" },
  { value: 2, label: "Wed" },
  { value: 3, label: "Thu" },
  { value: 4, label: "Fri" },
  { value: 5, label: "Sat" },
  { value: 6, label: "Sun" },
];

const RESOURCE_TYPES = [
  { key: "video", label: "Videos" },
  { key: "course", label: "Courses" },
  { key: "book", label: "Books" },
  { key: "project", label: "Projects" },
];

const browserTimezone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
};

const DEFAULT_SLOTS = [
  { weekday: 1, start: "19:00", end: "21:00" },
  { weekday: 3, start: "19:00", end: "21:00" },
];

const DEFAULT_WEIGHTS = { video: 50, course: 20, book: 10, project: 20 };

/**
 * Collects the user's free time + content-type preferences, then asks the
 * parent to generate a schedule. The parent supplies the resources/skills.
 */
function SchedulePlanner({ onGenerate, status, error, hasResources }) {
  const [horizonDays, setHorizonDays] = useState(30);
  const [slots, setSlots] = useState(DEFAULT_SLOTS);
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [maxPerDay, setMaxPerDay] = useState(2);

  const isLoading = status === "loading";
  const timezone = browserTimezone();

  const updateSlot = (index, field, value) =>
    setSlots((current) => current.map((slot, i) => (i === index ? { ...slot, [field]: value } : slot)));

  const addSlot = () =>
    setSlots((current) => [...current, { weekday: 5, start: "10:00", end: "12:00" }]);

  const removeSlot = (index) => setSlots((current) => current.filter((_, i) => i !== index));

  const updateWeight = (key, value) =>
    setWeights((current) => ({ ...current, [key]: Number(value) }));

  const handleSubmit = (event) => {
    event.preventDefault();
    onGenerate({
      horizon_days: Number(horizonDays),
      timezone,
      availability: slots.map((slot) => ({
        weekday: Number(slot.weekday),
        start: slot.start,
        end: slot.end,
      })),
      preferences: {
        weights: { ...weights },
        max_sessions_per_day: Number(maxPerDay),
      },
    });
  };

  return (
    <section className="panel schedule-planner" id="arrange-time">
      <header className="panel-heading">
        <CalendarClock size={20} />
        <div>
          <h2>Arrange my time</h2>
          <p>Pick when you are free and how you like to learn. We fit the resources into a {horizonDays}-day plan.</p>
        </div>
      </header>

      <form className="schedule-form" onSubmit={handleSubmit}>
        <div className="schedule-field-group">
          <span className="schedule-label">Plan length</span>
          <div className="horizon-tabs" role="tablist">
            {[30, 60].map((days) => (
              <button
                key={days}
                type="button"
                role="tab"
                aria-selected={horizonDays === days}
                className={horizonDays === days ? "active" : ""}
                onClick={() => setHorizonDays(days)}
              >
                {days} days
              </button>
            ))}
          </div>
        </div>

        <div className="schedule-field-group">
          <span className="schedule-label">When are you free each week?</span>
          <div className="availability-rows">
            {slots.map((slot, index) => (
              <div className="availability-row" key={index}>
                <select
                  value={slot.weekday}
                  onChange={(event) => updateSlot(index, "weekday", event.target.value)}
                  aria-label="Day of week"
                >
                  {WEEKDAYS.map((day) => (
                    <option key={day.value} value={day.value}>{day.label}</option>
                  ))}
                </select>
                <input
                  type="time"
                  value={slot.start}
                  onChange={(event) => updateSlot(index, "start", event.target.value)}
                  aria-label="Start time"
                />
                <span className="availability-dash">to</span>
                <input
                  type="time"
                  value={slot.end}
                  onChange={(event) => updateSlot(index, "end", event.target.value)}
                  aria-label="End time"
                />
                <button
                  type="button"
                  className="icon-button"
                  onClick={() => removeSlot(index)}
                  disabled={slots.length === 1}
                  aria-label="Remove slot"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
          <button type="button" className="ghost-button add-slot" onClick={addSlot}>
            <Plus size={16} /> Add another time
          </button>
        </div>

        <div className="schedule-field-group">
          <span className="schedule-label">Content mix (more = scheduled more often)</span>
          <div className="weight-rows">
            {RESOURCE_TYPES.map((type) => (
              <label className="weight-row" key={type.key}>
                <span>{type.label}</span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={weights[type.key]}
                  onChange={(event) => updateWeight(type.key, event.target.value)}
                />
                <span className="weight-value">{weights[type.key]}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="schedule-field-group">
          <label className="schedule-label" htmlFor="max-per-day">Max sessions per day</label>
          <input
            id="max-per-day"
            type="number"
            min="1"
            max="6"
            value={maxPerDay}
            onChange={(event) => setMaxPerDay(event.target.value)}
            className="max-per-day-input"
          />
        </div>

        {!hasResources && (
          <p className="schedule-hint">Run an analysis first so we have learning resources to schedule.</p>
        )}
        {error && <p className="schedule-error" role="alert">{error}</p>}

        <button type="submit" className="live-button" disabled={isLoading || !hasResources}>
          <CalendarClock size={18} />
          <span>{isLoading ? "Arranging..." : "Arrange my time"}</span>
        </button>
      </form>
    </section>
  );
}

export default SchedulePlanner;
