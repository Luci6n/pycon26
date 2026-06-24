import {
  ArrowLeftRight,
  BookOpen,
  Brain,
  CheckCircle2,
  CircleDot,
  Clock3,
  ExternalLink,
  Flag,
  GitBranch,
  Layers3,
  Link as LinkIcon,
  Upload,
  Route,
  RotateCcw,
  ShieldCheck,
  SkipForward,
  Sparkles,
  X,
} from "lucide-react";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { roles } from "./data/roles.js";
import {
  completeSession,
  createSharePage,
  downloadScheduleIcs,
  extractResumeFromApi,
  fetchAnalysisFromApi,
  fetchAdminRoadmaps,
  fetchAdminUsers,
  fetchEvidenceFromApi,
  fetchMarketEnrichment,
  fetchResourceEnrichment,
  fetchRolesFromApi,
  fetchSavedRoadmaps,
  fetchScheduleProgress,
  generateLinkedInDraft,
  generateSchedule,
  loginUser,
  registerUser,
  saveRoadmap,
  saveSchedule,
} from "./utils/api.js";
import { analyzeTransition } from "./utils/analysis.js";
import SchedulePlanner from "./components/SchedulePlanner.jsx";
import ScheduleCalendar from "./components/ScheduleCalendar.jsx";
import ReflectionModal from "./components/ReflectionModal.jsx";
import LinkedInShare from "./components/LinkedInShare.jsx";

const emptyLiveEvidence = {
  status: "idle",
  resources: null,
  market: null,
  error: "",
};

function normalizeSavedLiveEvidence(liveEvidence) {
  if (!liveEvidence) {
    return emptyLiveEvidence;
  }

  const resources = liveEvidence.resources ?? null;
  const market = liveEvidence.market ?? null;

  if (liveEvidence.status === "loading") {
    return {
      status: resources || market ? "ready" : "idle",
      resources,
      market,
      error: "",
    };
  }

  return {
    status: liveEvidence.status ?? "idle",
    resources,
    market,
    error: liveEvidence.error ?? "",
  };
}

const storedSessionKey = "pathforge-session";
const marketCountries = [
  "Singapore",
  "Malaysia",
  "United States",
  "United Kingdom",
  "Australia",
  "Canada",
  "India",
  "Indonesia",
  "Philippines",
  "Thailand",
  "Vietnam",
  "Japan",
];

function App() {
  const [currentRole, setCurrentRole] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [resumeName, setResumeName] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [resumeParseStatus, setResumeParseStatus] = useState("idle");
  const [resumeParseMessage, setResumeParseMessage] = useState("");
  const [isResumeDragActive, setIsResumeDragActive] = useState(false);
  const [selectedSkills, setSelectedSkills] = useState([]);
  const [githubUrl, setGithubUrl] = useState("");
  const [portfolioLinks, setPortfolioLinks] = useState([]);
  const [activeEvidenceTab, setActiveEvidenceTab] = useState("resume");
  const [marketScope, setMarketScope] = useState("country");
  const [marketCountry, setMarketCountry] = useState("Singapore");
  const [availableRoles, setAvailableRoles] = useState(roles);
  const [apiStatus, setApiStatus] = useState("checking");
  const [result, setResult] = useState(null);
  const [apiEvidence, setApiEvidence] = useState(null);
  const [liveEvidence, setLiveEvidence] = useState(emptyLiveEvidence);
  const [formError, setFormError] = useState("");
  const [session, setSession] = useState(null);
  const [accountOpen, setAccountOpen] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState({ email: "", password: "", name: "" });
  const [authStatus, setAuthStatus] = useState("idle");
  const [authMessage, setAuthMessage] = useState("");
  const [savedRoadmaps, setSavedRoadmaps] = useState([]);
  const [adminSummary, setAdminSummary] = useState(null);
  const [schedule, setSchedule] = useState(null);
  const [scheduleForm, setScheduleForm] = useState(null);
  const [scheduleStatus, setScheduleStatus] = useState("idle");
  const [scheduleError, setScheduleError] = useState("");
  const [savedScheduleId, setSavedScheduleId] = useState(null);
  const [saveStatus, setSaveStatus] = useState("idle");
  const [scheduleProgress, setScheduleProgress] = useState(null);
  const [reflectionSession, setReflectionSession] = useState(null);
  const [reflectionStatus, setReflectionStatus] = useState("idle");
  const [reflectionError, setReflectionError] = useState("");
  const [linkedInCaption, setLinkedInCaption] = useState(null);
  const [linkedInSourceCount, setLinkedInSourceCount] = useState(null);
  const [linkedInStatus, setLinkedInStatus] = useState("idle");
  const [shareUrl, setShareUrl] = useState("");
  const skipNextAnalysisReset = useRef(false);
  const activeAnalysisRun = useRef(0);

  const skillOptions = useMemo(() => {
    const names = new Set();
    availableRoles.forEach((role) => {
      (role.skills ?? []).forEach((skill) => names.add(skill));
    });
    selectedSkills.forEach((skill) => names.add(skill));
    return Array.from(names).sort((a, b) => a.localeCompare(b));
  }, [availableRoles, selectedSkills]);

  const isAnalyzing = liveEvidence.status === "loading";

  useEffect(() => {
    let cancelled = false;

    fetchRolesFromApi()
      .then((payload) => {
        if (!cancelled) {
          setAvailableRoles(payload.roles);
          setApiStatus("live");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAvailableRoles(roles);
          setApiStatus("fallback");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const stored = window.localStorage.getItem(storedSessionKey);
    if (stored) {
      try {
        setSession(JSON.parse(stored));
      } catch {
        window.localStorage.removeItem(storedSessionKey);
      }
    }
  }, []);

  useEffect(() => {
    if (skipNextAnalysisReset.current) {
      skipNextAnalysisReset.current = false;
      setFormError("");
      return;
    }

    activeAnalysisRun.current += 1;
    setResult(null);
    setApiEvidence(null);
    setLiveEvidence(emptyLiveEvidence);
    setFormError("");
  }, [currentRole, targetRole, resumeName, resumeText, githubUrl, portfolioLinks, selectedSkills]);

  const swapRoles = () => {
    setCurrentRole(targetRole);
    setTargetRole(currentRole);
  };

  const handleResumeFile = async (file) => {
    setResumeName(file?.name ?? "");
    setResumeText("");
    setResumeParseMessage("");

    if (!file) {
      setResumeParseStatus("idle");
      return;
    }

    setResumeParseStatus("loading");

    try {
      const payload = await extractResumeFromApi(file);
      setResumeText(payload.text ?? "");
      setResumeParseStatus(payload.status === "parsed" ? "ready" : "warning");
      setResumeParseMessage(payload.detail);
    } catch (error) {
      setResumeParseStatus("warning");
      setResumeParseMessage(error instanceof Error ? error.message : "Could not extract resume text.");

      if (/\.(txt|md)$/i.test(file.name)) {
        try {
          setResumeText(await file.text());
          setResumeParseStatus("ready");
          setResumeParseMessage("Text resume extracted in the browser.");
        } catch {
          setResumeText("");
        }
      }
    }
  };

  const handleResumeUpload = async (event) => {
    await handleResumeFile(event.target.files?.[0]);
  };

  const handleResumeDrop = async (event) => {
    event.preventDefault();
    setIsResumeDragActive(false);
    await handleResumeFile(event.dataTransfer.files?.[0]);
  };

  const updateAuthField = (field, value) => {
    setAuthForm((current) => ({ ...current, [field]: value }));
  };

  const handleAuthSubmit = async (event) => {
    event.preventDefault();
    setAuthStatus("loading");
    setAuthMessage("");

    try {
      const payload = authMode === "register"
        ? await registerUser(authForm)
        : await loginUser(authForm);

      setSession(payload);
      window.localStorage.setItem(storedSessionKey, JSON.stringify(payload));
      setAuthMessage(authMode === "register" ? "Account created." : "Signed in.");
      setAuthForm({ email: "", password: "", name: "" });
      setSavedRoadmaps([]);
      setAdminSummary(null);
    } catch (error) {
      setAuthMessage(error instanceof Error ? error.message : "Authentication failed.");
    } finally {
      setAuthStatus("idle");
    }
  };

  const handleSignOut = () => {
    setSession(null);
    setSavedRoadmaps([]);
    setAdminSummary(null);
    window.localStorage.removeItem(storedSessionKey);
  };

  const handleSaveRoadmap = async () => {
    if (!session || !result) {
      return;
    }

    setAuthStatus("loading");
    setAuthMessage("");

    try {
      await saveRoadmap(session.token, {
        title: `${result.current.title} to ${result.target.title}`,
        current_role_id: currentRole,
        target_role_id: targetRole,
        payload: {
          result,
          evidence: apiEvidence,
          liveEvidence: normalizeSavedLiveEvidence(liveEvidence),
        },
      });
      const listing = await fetchSavedRoadmaps(session.token);
      setSavedRoadmaps(listing.roadmaps);
      setAuthMessage("Roadmap saved.");
    } catch (error) {
      setAuthMessage(error instanceof Error ? error.message : "Could not save roadmap.");
    } finally {
      setAuthStatus("idle");
    }
  };

  const handleLoadRoadmaps = async () => {
    if (!session) {
      return;
    }

    setAuthStatus("loading");
    setAuthMessage("");

    try {
      const listing = await fetchSavedRoadmaps(session.token);
      setSavedRoadmaps(listing.roadmaps);
      if (listing.roadmaps[0]) {
        setAuthMessage("Saved roadmaps loaded. Choose one to open.");
      } else {
        setAuthMessage("No saved roadmaps yet.");
      }
    } catch (error) {
      setAuthMessage(error instanceof Error ? error.message : "Could not load roadmaps.");
    } finally {
      setAuthStatus("idle");
    }
  };

  const handleOpenSavedRoadmap = (roadmap, options = {}) => {
    const payload = roadmap.payload ?? {};
    skipNextAnalysisReset.current = true;

    if (roadmap.current_role_id) {
      setCurrentRole(roadmap.current_role_id);
    }

    if (roadmap.target_role_id) {
      setTargetRole(roadmap.target_role_id);
    }

    if (payload.result) {
      setResult(payload.result);
    }

    setApiEvidence(payload.evidence ?? null);
    setLiveEvidence(normalizeSavedLiveEvidence(payload.liveEvidence));
    setFormError("");
    setAuthMessage(`Loaded ${roadmap.title}.`);
    if (!options.keepMenuOpen) {
      setAccountOpen(false);
    }
  };

  const handleLoadAdmin = async () => {
    if (!session || session.user.role !== "admin") {
      return;
    }

    setAuthStatus("loading");
    setAuthMessage("");

    try {
      const [users, roadmaps] = await Promise.all([
        fetchAdminUsers(session.token),
        fetchAdminRoadmaps(session.token),
      ]);
      setAdminSummary({
        users: users.users.length,
        roadmaps: roadmaps.roadmaps.length,
      });
      setAuthMessage("Admin summary loaded.");
    } catch (error) {
      setAuthMessage(error instanceof Error ? error.message : "Could not load admin summary.");
    } finally {
      setAuthStatus("idle");
    }
  };

  const runLiveEvidence = async () => {
    if (!currentRole || !targetRole) {
      setFormError("Choose both roles before running the analysis.");
      return;
    }

    const runId = activeAnalysisRun.current + 1;
    activeAnalysisRun.current = runId;
    const isCurrentRun = () => activeAnalysisRun.current === runId;

    setFormError("");
    setResult(null);
    setApiEvidence(null);
    setLiveEvidence({ status: "loading", resources: null, market: null, error: "" });

    try {
      const enrichmentErrors = [];
      const evidenceRequest = {
        targetRoleId: targetRole,
        resumeName,
        resumeText,
        manualSkills: selectedSkills,
        githubUrl,
        portfolioLinks,
      };
      let quickEvidence = null;

      try {
        quickEvidence = await fetchEvidenceFromApi({
          ...evidenceRequest,
          fetchRepository: false,
        });

        if (!isCurrentRun()) {
          return;
        }

        setApiEvidence(quickEvidence);
      } catch {
        enrichmentErrors.push("Profile evidence scan failed.");
      }

      const profileSkills = collectProfileSkills(quickEvidence, selectedSkills);
      let analysis = await runPersonalizedAnalysis(currentRole, targetRole, profileSkills);

      if (!isCurrentRun()) {
        return;
      }

      setResult(analysis);

      const targetSkills = analysis.missing.slice(0, 4).map((skill) => skill.name);
      const resourceSkill = targetSkills[0] || analysis.target.skills[0] || analysis.target.title;

      const resourcePromise = fetchResourceEnrichment({
        skill: resourceSkill,
        targetRole: analysis.target.title,
        numResults: 4,
      });
      const marketPromise = fetchMarketEnrichment({
        targetRole: analysis.target.title,
        skills: targetSkills,
        country: marketScope === "country" ? marketCountry : "",
      });

      if (githubUrl.trim()) {
        refineAnalysisWithGithubEvidence(runId, evidenceRequest, profileSkills);
      }

      const [resourceResult, marketResult] = await Promise.allSettled([resourcePromise, marketPromise]);
      let resources = null;
      let market = null;

      if (resourceResult.status === "fulfilled") {
        resources = resourceResult.value;
      } else {
        enrichmentErrors.push("Learning resource search failed.");
      }

      if (marketResult.status === "fulfilled") {
        market = marketResult.value;
      } else {
        enrichmentErrors.push("Job market search failed.");
      }

      if (isCurrentRun()) {
        setLiveEvidence({
          status: enrichmentErrors.length ? "error" : "ready",
          resources,
          market,
          error: enrichmentErrors.join(" "),
        });
      }
    } catch (error) {
      if (isCurrentRun()) {
        setLiveEvidence({
          status: "error",
          resources: null,
          market: null,
          error: error instanceof Error ? error.message : "Live evidence analysis failed.",
        });
      }
    }
  };

  const runPersonalizedAnalysis = async (fromRole, toRole, profileSkills) => {
    try {
      const analysis = await fetchAnalysisFromApi(fromRole, toRole, profileSkills);
      setApiStatus("live");
      return analysis;
    } catch {
      const canUseLocalFallback = roles.some((role) => role.id === fromRole)
        && roles.some((role) => role.id === toRole);

      if (!canUseLocalFallback) {
        throw new Error("Official dataset analysis failed.");
      }

      setApiStatus("fallback");
      return analyzeTransition(fromRole, toRole, profileSkills);
    }
  };

  const refineAnalysisWithGithubEvidence = async (runId, evidenceRequest, existingProfileSkills) => {
    try {
      const fullEvidence = await fetchEvidenceFromApi({
        ...evidenceRequest,
        fetchRepository: true,
      });

      if (activeAnalysisRun.current !== runId) {
        return;
      }

      setApiEvidence(fullEvidence);
      const refinedProfileSkills = collectProfileSkills(fullEvidence, selectedSkills);

      if (sameSkillSet(existingProfileSkills, refinedProfileSkills)) {
        return;
      }

      const refinedAnalysis = await runPersonalizedAnalysis(currentRole, targetRole, refinedProfileSkills);

      if (activeAnalysisRun.current === runId) {
        setResult(refinedAnalysis);
      }
    } catch {
      // Keep the fast resume/manual evidence and role analysis visible when GitHub is slow or unavailable.
    }
  };

  const schedulableResources = useMemo(() => {
    const categories = liveEvidence.resources?.categories ?? [];
    const topSkill = result?.missing?.[0]?.name || result?.target?.title || "";
    return categories.flatMap((category) =>
      (category.results ?? []).map((item) => ({
        type: item.type || category.type,
        title: item.title,
        url: item.url,
        skill: topSkill,
      }))
    );
  }, [liveEvidence.resources, result]);

  const hasSchedulableResources = schedulableResources.length > 0;
  const isLoggedIn = Boolean(session?.token);

  const refreshProgress = async (scheduleId) => {
    if (!session?.token) return;
    try {
      const progress = await fetchScheduleProgress(session.token, scheduleId);
      setScheduleProgress(progress);
    } catch {
      // Progress is best-effort; ignore transient failures.
    }
  };

  const handleGenerateSchedule = async (formData) => {
    setScheduleStatus("loading");
    setScheduleError("");
    setScheduleForm(formData);
    setShareUrl("");
    try {
      const data = await generateSchedule({
        ...formData,
        target_role: result?.target?.title ?? null,
        target_role_id: result?.target?.id ?? null,
        resources: schedulableResources,
        skills: (result?.missing ?? []).map((skill) => ({
          name: skill.name,
          urgency: skill.urgency,
          demand: skill.demand,
        })),
      });
      setSchedule(data);
      setSavedScheduleId(null);
      setSaveStatus("idle");
      setScheduleProgress(null);
      setScheduleStatus("ready");
    } catch (error) {
      setScheduleStatus("error");
      setScheduleError(error instanceof Error ? error.message : "Could not arrange your time.");
    }
  };

  const handleExportIcs = async () => {
    if (!schedule?.sessions?.length) return;
    try {
      const title = `PathForge plan - ${result?.target?.title ?? "Learning"}`;
      await downloadScheduleIcs(title, schedule.sessions);
    } catch (error) {
      setScheduleError(error instanceof Error ? error.message : "Calendar export failed.");
    }
  };

  const handleSaveSchedule = async () => {
    if (!session?.token || !schedule || !scheduleForm) return;
    setSaveStatus("loading");
    setScheduleError("");
    try {
      const data = await saveSchedule(session.token, {
        title: `${result?.target?.title ?? "Learning"} plan`,
        target_role_id: result?.target?.id ?? null,
        horizon_days: scheduleForm.horizon_days,
        timezone: scheduleForm.timezone,
        preferences: scheduleForm.preferences,
        availability: scheduleForm.availability,
        sessions: schedule.sessions,
      });
      const saved = data.schedule;
      setSchedule((prev) => ({ ...prev, id: saved.id, sessions: saved.sessions }));
      setSavedScheduleId(saved.id);
      setSaveStatus("saved");
      await refreshProgress(saved.id);
    } catch (error) {
      setSaveStatus("error");
      setScheduleError(error instanceof Error ? error.message : "Could not save your plan.");
    }
  };

  const handleSubmitReflection = async (content) => {
    if (!session?.token || !reflectionSession) return;
    setReflectionStatus("loading");
    setReflectionError("");
    try {
      const data = await completeSession(session.token, reflectionSession.id, content);
      const updated = data.session;
      setSchedule((prev) =>
        prev
          ? {
              ...prev,
              sessions: prev.sessions.map((item) =>
                item.id === updated.id ? { ...item, status: updated.status } : item
              ),
            }
          : prev
      );
      setReflectionSession(null);
      setReflectionStatus("idle");
      if (savedScheduleId) await refreshProgress(savedScheduleId);
    } catch (error) {
      setReflectionStatus("error");
      setReflectionError(error instanceof Error ? error.message : "Could not save reflection.");
    }
  };

  const handleGenerateCaption = async () => {
    if (!session?.token) {
      setLinkedInStatus("error");
      return;
    }
    setLinkedInStatus("loading");
    try {
      const data = await generateLinkedInDraft(session.token, {
        schedule_id: savedScheduleId,
        target_role: result?.target?.title ?? null,
      });
      setLinkedInCaption(data.caption ?? "");
      setLinkedInSourceCount(data.source_count ?? 0);
      setLinkedInStatus("idle");
    } catch (error) {
      setLinkedInStatus("error");
    }
  };

  const handleCreateShare = async () => {
    if (!session?.token) return;
    setLinkedInStatus("loading");
    try {
      const completed = (schedule?.sessions ?? []).filter((item) => item.status === "completed");
      const data = await createSharePage(session.token, {
        title: `My progress toward ${result?.target?.title ?? "my goal"}`,
        target_role: result?.target?.title ?? null,
        completed_count: completed.length,
        highlights: completed.slice(0, 5).map((item) => `Completed ${item.resource_title}`),
      });
      setShareUrl(data.share_url);
      setLinkedInStatus("idle");
    } catch (error) {
      setLinkedInStatus("error");
    }
  };

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to Main Content
      </a>
      <main className="workspace" id="main-content">
        <header className="topbar">
          <div className="topbar-title">
            <div className="brand-mark">
              <GitBranch size={22} strokeWidth={2.4} />
            </div>
            <div>
              <span>PathForge AI</span>
              <h1>Career Pivot Navigator</h1>
              <p>Choose a path, add evidence, then run one explainable analysis.</p>
            </div>
          </div>
          <AccountPanel
            open={accountOpen}
            onOpenChange={setAccountOpen}
            session={session}
            authMode={authMode}
            authForm={authForm}
            authStatus={authStatus}
            authMessage={authMessage}
            savedRoadmaps={savedRoadmaps}
            adminSummary={adminSummary}
            hasResult={Boolean(result)}
            onModeChange={setAuthMode}
            onFieldChange={updateAuthField}
            onSubmit={handleAuthSubmit}
            onSignOut={handleSignOut}
            onSaveRoadmap={handleSaveRoadmap}
            onLoadRoadmaps={handleLoadRoadmaps}
            onOpenRoadmap={handleOpenSavedRoadmap}
            onLoadAdmin={handleLoadAdmin}
          />
        </header>

        <section className="selector-strip" id="overview" aria-label="Role Selectors">
          <RoleSelect
            label="Current role"
            name="current-role"
            value={currentRole}
            onChange={setCurrentRole}
            disabledId={targetRole}
            roles={availableRoles}
            placeholder="Choose current role..."
          />
          <button
            className="swap-button"
            type="button"
            onClick={swapRoles}
            aria-label="Swap roles"
            title="Swap roles"
            disabled={!currentRole && !targetRole}
          >
            <ArrowLeftRight size={19} />
          </button>
          <RoleSelect
            label="Target role"
            name="target-role"
            value={targetRole}
            onChange={setTargetRole}
            disabledId={currentRole}
            roles={availableRoles}
            placeholder="Choose target role..."
          />
        </section>

        <section className="panel intake-panel" id="evidence">
          <PanelHeading
            icon={Upload}
            title="Profile evidence"
            subtitle="Add what you already have. The role path still works without uploads."
          />
          <div
            className={activeEvidenceTab === "links" ? "evidence-tabs links-active" : "evidence-tabs resume-active"}
            role="tablist"
            aria-label="Evidence Type"
          >
            <button
              type="button"
              role="tab"
              aria-selected={activeEvidenceTab === "resume"}
              className={activeEvidenceTab === "resume" ? "evidence-tab active" : "evidence-tab"}
              onClick={() => setActiveEvidenceTab("resume")}
            >
              Resume/CV
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeEvidenceTab === "links"}
              className={activeEvidenceTab === "links" ? "evidence-tab active" : "evidence-tab"}
              onClick={() => setActiveEvidenceTab("links")}
            >
              Links & portfolio
            </button>
          </div>

          {activeEvidenceTab === "resume" ? (
            <div className="intake-grid resume-grid">
              <label className="text-field resume-text-field">
                <textarea
                  name="resume-text"
                  aria-label="Paste resume text"
                  value={resumeText}
                  onChange={(event) => setResumeText(event.target.value)}
                  placeholder="Paste your resume, CV, portfolio summary, or profile bio here."
                />
              </label>
              <div className="resume-divider" aria-hidden="true">
                <span>or</span>
              </div>
              <label
                className={isResumeDragActive ? "file-drop resume-drop-zone dragging" : "file-drop resume-drop-zone"}
                onDragOver={(event) => {
                  event.preventDefault();
                  setIsResumeDragActive(true);
                }}
                onDragLeave={() => setIsResumeDragActive(false)}
                onDrop={handleResumeDrop}
              >
                <Upload size={20} />
                <span>{resumeName || "Click to upload or drag resume/CV here"}</span>
                <small>PDF, TXT, or Markdown</small>
                <input
                  name="resume"
                  type="file"
                  accept=".pdf,.txt,.md"
                  onChange={handleResumeUpload}
                />
              </label>
              {resumeParseStatus === "loading" || resumeParseMessage ? (
                <p className={`resume-parse-status ${resumeParseStatus}`}>
                  {resumeParseStatus === "loading" ? "Extracting resume text..." : resumeParseMessage}
                </p>
              ) : null}
            </div>
          ) : (
            <div className="intake-grid links-grid">
              <label className="text-field link-input-card">
                <span>GitHub profile or repository</span>
                <input
                  name="github-url"
                  type="url"
                  inputMode="url"
                  autoComplete="off"
                  spellCheck={false}
                  value={githubUrl}
                  onChange={(event) => setGithubUrl(event.target.value)}
                  placeholder="https://github.com/user"
                />
              </label>
              <LinkTagInput
                links={portfolioLinks}
                onChange={setPortfolioLinks}
              />
            </div>
          )}

          <SkillTagInput
            skills={selectedSkills}
            options={skillOptions}
            onChange={setSelectedSkills}
          />

          <div className="analysis-action-row">
            <div>
              <strong>Ready to analyze?</strong>
              <p>
                {currentRole && targetRole
                  ? "Runs role scoring, profile evidence, live job postings, and learning resources."
                  : "Choose both roles first. Resume, links, and skills are optional evidence."}
              </p>
              {formError ? <span className="form-error">{formError}</span> : null}
            </div>
            <div className="market-scope-control" aria-label="Job market search scope">
              <div className={marketScope === "country" ? "market-scope-tabs country-active" : "market-scope-tabs global-active"}>
                <button
                  type="button"
                  className={marketScope === "global" ? "market-scope-tab active" : "market-scope-tab"}
                  onClick={() => setMarketScope("global")}
                >
                  Global
                </button>
                <button
                  type="button"
                  className={marketScope === "country" ? "market-scope-tab active" : "market-scope-tab"}
                  onClick={() => setMarketScope("country")}
                >
                  Country
                </button>
              </div>
              <select
                aria-label="Job search country"
                value={marketCountry}
                onChange={(event) => {
                  setMarketCountry(event.target.value);
                  setMarketScope("country");
                }}
                disabled={marketScope !== "country"}
              >
                {marketCountries.map((country) => (
                  <option value={country} key={country}>
                    {country}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              className="live-button"
              onClick={runLiveEvidence}
              disabled={isAnalyzing}
            >
              <Sparkles size={18} />
              <span>{isAnalyzing ? "Analyzing profile..." : "Analyze profile"}</span>
            </button>
          </div>
          {result ? <LiveEvidencePanel liveEvidence={liveEvidence} apiEvidence={apiEvidence} /> : null}
        </section>

        {result ? (
          <>
        <section className="summary-grid">
          <CompatibilityGauge score={result.compatibility} difficulty={result.difficulty} />

          <div className="metric-panel">
            <span className="panel-label">Transferable skills</span>
            <strong>{result.transferable.length}</strong>
            <p>{result.transferable.slice(0, 3).join(", ") || "No direct matches yet"}</p>
          </div>

          <div className="metric-panel">
            <span className="panel-label">Priority gaps</span>
            <strong>{result.missing.length}</strong>
            <p>{result.missing.slice(0, 3).map((skill) => skill.name).join(", ")}</p>
          </div>

          <div className="metric-panel">
            <span className="panel-label">Best adjacent route</span>
            <strong>{result.alternatives[0]?.score ?? 0}%</strong>
            <p>{result.alternatives[0]?.title ?? "No adjacent route found"}</p>
          </div>
        </section>

        <section className="content-grid" id="skills">
          <div className="panel skill-panel">
            <PanelHeading icon={CheckCircle2} title="Transferable skills" subtitle="Skills present in both role profiles." />
            <SkillList skills={result.transferable} tone="positive" empty="No direct transferable skills in this role pair." />
          </div>

          <div className="panel skill-panel">
            <PanelHeading icon={CircleDot} title="Priority gaps" subtitle="Ranked by target-role evidence weight." />
            <div className="gap-list">
              {result.missing.slice(0, 14).map((skill, index) => (
                <div className="gap-row" key={skill.name}>
                  <div className="rank">{index + 1}</div>
                  <div>
                    <strong>{skill.name}</strong>
                    <span>{skill.urgency} priority</span>
                  </div>
                  <meter min="0" max="100" value={skill.demand} aria-label={`${skill.name} demand ${skill.demand}%`} />
                  <b>{skill.demand}%</b>
                </div>
              ))}
            </div>
          </div>

          <div className="panel evidence-panel">
            <PanelHeading icon={ShieldCheck} title="Evidence" subtitle="Facts first, explanation second." />
            <div className="evidence-list">
              {result.evidence.map((item) => (
                <article key={item.label}>
                  <span>{item.label}</span>
                  <p>{item.detail}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="bottom-grid" id="routes">
          <div className="panel graph-panel">
            <PanelHeading icon={Layers3} title="Skill graph" subtitle="Role-to-skill relationships for the selected path." />
            <SkillGraph result={result} />
          </div>

          <div className="panel routes-panel">
            <PanelHeading icon={Route} title="Alternative routes" subtitle="Adjacent paths requiring fewer new skills." />
            <div className="routes-list">
              {result.alternatives.map((route) => (
                <button key={route.id} type="button" className="route-row" onClick={() => setTargetRole(route.id)}>
                  <div>
                    <strong>{route.title}</strong>
                    <span>{route.family}</span>
                  </div>
                  <b>{route.score}%</b>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="panel roadmap-panel" id="roadmap">
          <PanelHeading icon={Brain} title="30/60/90 day learning plan" subtitle="Generated from the highest-priority gaps." />
          <LearningRoadmapMap
            result={result}
            apiEvidence={apiEvidence}
            liveEvidence={liveEvidence}
            progressKey={`pathforge-roadmap-progress:${currentRole || result.current.id}:${targetRole || result.target.id}`}
          />
        </section>

        <SchedulePlanner
          onGenerate={handleGenerateSchedule}
          status={scheduleStatus}
          error={scheduleError}
          hasResources={hasSchedulableResources}
        />

        {schedule ? (
          <ScheduleCalendar
            schedule={schedule}
            progress={scheduleProgress}
            isSaved={Boolean(savedScheduleId)}
            canSave={isLoggedIn}
            saveStatus={saveStatus}
            onExport={handleExportIcs}
            onSave={handleSaveSchedule}
            onMarkDone={setReflectionSession}
          />
        ) : null}

        {schedule && isLoggedIn ? (
          <LinkedInShare
            caption={linkedInCaption}
            sourceCount={linkedInSourceCount}
            status={linkedInStatus}
            shareUrl={shareUrl}
            onCaptionChange={setLinkedInCaption}
            onGenerateCaption={handleGenerateCaption}
            onCreateShare={handleCreateShare}
          />
        ) : null}

        {schedule && !isLoggedIn ? (
          <section className="panel linkedin-share">
            <p className="schedule-hint">Sign in to save your plan, track progress, and share to LinkedIn.</p>
          </section>
        ) : null}
          </>
        ) : (
          <section className="panel empty-state-panel" aria-live="polite">
            <PanelHeading
              icon={Sparkles}
              title={isAnalyzing ? "Analysis running" : "No analysis yet"}
              subtitle={isAnalyzing ? "Building the role score, evidence scan, resources, and market view." : "Choose roles, add optional evidence, then run the profile analysis."}
            />
          </section>
        )}

      </main>
      {reflectionSession ? (
        <ReflectionModal
          session={reflectionSession}
          status={reflectionStatus}
          error={reflectionError}
          onSubmit={handleSubmitReflection}
          onClose={() => {
            setReflectionSession(null);
            setReflectionStatus("idle");
            setReflectionError("");
          }}
        />
      ) : null}
    </div>
  );
}

function AccountPanel({
  open,
  onOpenChange,
  session,
  authMode,
  authForm,
  authStatus,
  authMessage,
  savedRoadmaps,
  adminSummary,
  hasResult,
  onModeChange,
  onFieldChange,
  onSubmit,
  onSignOut,
  onSaveRoadmap,
  onLoadRoadmaps,
  onOpenRoadmap,
  onLoadAdmin,
}) {
  const isLoading = authStatus === "loading";

  return (
    <div className="account-menu">
      <button
        type="button"
        className="account-trigger"
        onClick={() => onOpenChange(!open)}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <ShieldCheck size={16} />
        <span>{session ? session.user.name || "Account" : "Login / Register"}</span>
      </button>

      {open ? (
        <section className="account-popover" aria-label="Account">
          <div className="account-popover-heading">
            <strong>{session ? "Account" : "Optional account"}</strong>
            <p>{session ? "Save and revisit career roadmaps." : "Use the app without logging in. Sign in only to save plans."}</p>
          </div>

          {session ? (
            <div className="account-signed-in">
              <div className="account-user-card">
                <span>{session.user.role === "admin" ? "Admin account" : "User account"}</span>
                <strong>{session.user.name || session.user.email}</strong>
                <p>{session.user.email}</p>
              </div>

              <div className="account-actions">
                <button type="button" className="secondary-button" onClick={onSaveRoadmap} disabled={!hasResult || isLoading}>
                  Save Roadmap
                </button>
                <button type="button" className="secondary-button" onClick={onLoadRoadmaps} disabled={isLoading}>
                  Load Saved
                </button>
                {session.user.role === "admin" ? (
                  <button type="button" className="secondary-button" onClick={onLoadAdmin} disabled={isLoading}>
                    Admin Summary
                  </button>
                ) : null}
                <button type="button" className="ghost-button" onClick={onSignOut}>
                  Sign Out
                </button>
              </div>

              {savedRoadmaps.length ? (
                <div className="saved-roadmap-list">
                  {savedRoadmaps.slice(0, 4).map((roadmap) => (
                    <article key={roadmap.id}>
                      <div>
                        <strong>{roadmap.title}</strong>
                        <span>{new Date(roadmap.created_at).toLocaleDateString()}</span>
                      </div>
                      <button type="button" onClick={() => onOpenRoadmap(roadmap)}>
                        Open
                      </button>
                    </article>
                  ))}
                </div>
              ) : null}

              {adminSummary ? (
                <div className="admin-summary">
                  <span>{adminSummary.users} users</span>
                  <span>{adminSummary.roadmaps} saved roadmaps</span>
                </div>
              ) : null}
            </div>
          ) : (
            <form className="account-form" onSubmit={onSubmit}>
              <div className="account-mode-tabs" role="tablist" aria-label="Account mode">
                <button
                  type="button"
                  role="tab"
                  aria-selected={authMode === "login"}
                  className={authMode === "login" ? "account-mode active" : "account-mode"}
                  onClick={() => onModeChange("login")}
                >
                  Login
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={authMode === "register"}
                  className={authMode === "register" ? "account-mode active" : "account-mode"}
                  onClick={() => onModeChange("register")}
                >
                  Register
                </button>
              </div>

              {authMode === "register" ? (
                <label className="text-field">
                  <span>Name</span>
                  <input
                    name="name"
                    type="text"
                    autoComplete="name"
                    value={authForm.name}
                    onChange={(event) => onFieldChange("name", event.target.value)}
                    placeholder="Ler Jun Wei"
                  />
                </label>
              ) : null}

              <label className="text-field">
                <span>Email</span>
                <input
                  name="email"
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  spellCheck={false}
                  value={authForm.email}
                  onChange={(event) => onFieldChange("email", event.target.value)}
                  placeholder="you@example.com"
                  required
                />
              </label>

              <label className="text-field">
                <span>Password</span>
                <input
                  name="password"
                  type="password"
                  autoComplete={authMode === "register" ? "new-password" : "current-password"}
                  value={authForm.password}
                  onChange={(event) => onFieldChange("password", event.target.value)}
                  placeholder="At least 8 characters"
                  required
                />
              </label>

              <button type="submit" className="secondary-button" disabled={isLoading}>
                {isLoading ? "Working..." : authMode === "register" ? "Create Account" : "Login"}
              </button>
            </form>
          )}

          {authMessage ? <p className="account-message" aria-live="polite">{authMessage}</p> : null}
        </section>
      ) : null}
    </div>
  );
}

function SkillTagInput({ skills, options, onChange }) {
  const [draft, setDraft] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const suggestions = useMemo(() => {
    const query = draft.trim().toLowerCase();
    return options
      .filter((option) => !skills.some((skill) => skill.toLowerCase() === option.toLowerCase()))
      .filter((option) => !query || option.toLowerCase().includes(query));
  }, [draft, options, skills]);

  const commitSkill = (value) => {
    const cleaned = normalizeSkillName(value);
    if (!cleaned) {
      return;
    }

    const existing = skills.some((skill) => skill.toLowerCase() === cleaned.toLowerCase());
    if (existing) {
      setDraft("");
      return;
    }

    const matchedOption = options.find((option) => option.toLowerCase() === cleaned.toLowerCase());
    onChange([...skills, matchedOption || cleaned]);
    setDraft("");
    setIsOpen(false);
    setHighlightedIndex(0);
  };

  const removeSkill = (skillToRemove) => {
    onChange(skills.filter((skill) => skill !== skillToRemove));
  };

  return (
    <div className="skill-picker universal-skills-field">
      <div className="skill-picker-label">
        <span>Your skills</span>
        <small>Choose a known skill or create your own with Enter.</small>
      </div>
      <div className="tag-input-shell">
        <div className="skill-combobox">
          {skills.map((skill) => (
            <span className="selected-skill-tag" key={skill}>
              {skill}
              <button type="button" onClick={() => removeSkill(skill)} aria-label={`Remove ${skill}`}>
                <X size={13} />
              </button>
            </span>
          ))}
          <input
            name="manual-skills"
            autoComplete="off"
            spellCheck={false}
            value={draft}
            onFocus={() => setIsOpen(true)}
            onChange={(event) => {
              setDraft(event.target.value);
              setIsOpen(true);
              setHighlightedIndex(0);
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown" && suggestions.length) {
                event.preventDefault();
                setIsOpen(true);
                setHighlightedIndex((index) => Math.min(index + 1, suggestions.length - 1));
              }

              if (event.key === "ArrowUp" && suggestions.length) {
                event.preventDefault();
                setHighlightedIndex((index) => Math.max(index - 1, 0));
              }

              if (event.key === "Enter" || event.key === ",") {
                event.preventDefault();
                commitSkill(isOpen && suggestions[highlightedIndex] ? suggestions[highlightedIndex] : draft);
              }

              if (event.key === "Escape") {
                setIsOpen(false);
              }

              if (event.key === "Backspace" && !draft && skills.length) {
                onChange(skills.slice(0, -1));
              }
            }}
            onBlur={() => setIsOpen(false)}
            placeholder={skills.length ? "Add another skill..." : "Type a skill or choose one below..."}
          />
        </div>
        {isOpen && suggestions.length ? (
          <div className="tag-suggestion-list" role="listbox" aria-label="Skill suggestions">
            <div className="tag-suggestion-meta">
              {suggestions.length.toLocaleString()} skill{suggestions.length === 1 ? "" : "s"} available
            </div>
            {suggestions.map((skill, index) => (
              <button
                type="button"
                role="option"
                aria-selected={highlightedIndex === index}
                className={highlightedIndex === index ? "tag-suggestion active" : "tag-suggestion"}
                key={skill}
                onMouseDown={(event) => {
                  event.preventDefault();
                  commitSkill(skill);
                }}
                onMouseEnter={() => setHighlightedIndex(index)}
              >
                {skill}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function normalizeSkillName(value) {
  return value.replace(/\s+/g, " ").trim();
}

function LinkTagInput({ links, onChange }) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");

  const commitLink = (value) => {
    const candidates = value
      .split(/[\s,]+/)
      .map((item) => item.trim())
      .filter(Boolean);

    if (!candidates.length) {
      return;
    }

    const nextLinks = [...links];
    let hasError = false;

    candidates.forEach((candidate) => {
      const normalized = normalizeUrl(candidate);
      if (!normalized) {
        hasError = true;
        return;
      }

      if (!nextLinks.some((link) => link.toLowerCase() === normalized.toLowerCase())) {
        nextLinks.push(normalized);
      }
    });

    onChange(nextLinks);
    setDraft("");
    setError(hasError ? "Use a full link like https://linkedin.com/in/name." : "");
  };

  const removeLink = (linkToRemove) => {
    onChange(links.filter((link) => link !== linkToRemove));
  };

  return (
    <div className="link-tag-field">
      <div className="skill-picker-label">
        <span>LinkedIn, portfolio, publications, or extra links</span>
        <small>Paste a link to create a clickable source tag.</small>
      </div>
      <div className="tag-input-shell">
        <div className="link-combobox">
          {links.map((link) => (
            <span className="selected-link-tag" key={link}>
              <a href={link} target="_blank" rel="noreferrer">
                <LinkIcon size={13} />
                {linkTagLabel(link)}
              </a>
              <button type="button" onClick={() => removeLink(link)} aria-label={`Remove ${linkTagLabel(link)}`}>
                <X size={13} />
              </button>
            </span>
          ))}
          <input
            name="portfolio-links"
            type="url"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            value={draft}
            onPaste={(event) => {
              const pastedText = event.clipboardData.getData("text");
              if (pastedText.trim()) {
                window.setTimeout(() => commitLink(pastedText), 0);
              }
            }}
            onChange={(event) => {
              const value = event.target.value;
              if (/\s/.test(value.trim())) {
                commitLink(value);
                return;
              }
              setDraft(value);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === ",") {
                event.preventDefault();
                commitLink(draft);
              }

              if (event.key === "Backspace" && !draft && links.length) {
                onChange(links.slice(0, -1));
              }
            }}
            onBlur={() => commitLink(draft)}
            placeholder={links.length ? "Paste another link..." : "https://www.linkedin.com/in/name"}
          />
        </div>
      </div>
      {error ? <span className="field-error">{error}</span> : null}
    </div>
  );
}

function normalizeUrl(value) {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }

  const withProtocol = /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;

  try {
    const url = new URL(withProtocol);
    if (!url.hostname.includes(".")) {
      return "";
    }
    return url.href;
  } catch {
    return "";
  }
}

function linkTagLabel(link) {
  try {
    const host = new URL(link).hostname.toLowerCase().replace(/^www\./, "");
    const firstPart = host.split(".")[0] || host;
    return firstPart.charAt(0).toUpperCase() + firstPart.slice(1);
  } catch {
    return "Link";
  }
}

function collectProfileSkills(evidence, manualSkills = []) {
  return uniqueStrings([
    ...manualSkills,
    ...(evidence?.resume?.matched_skills ?? []),
    ...(evidence?.manual_skills?.skills ?? []),
    ...(evidence?.manual_skills?.matched_skills ?? []),
    ...(evidence?.repository?.inferred_skills ?? []),
    ...(evidence?.repository?.languages ?? []),
  ]);
}

function sameSkillSet(left = [], right = []) {
  const normalizedLeft = left.map((skill) => skill.toLowerCase()).sort();
  const normalizedRight = right.map((skill) => skill.toLowerCase()).sort();

  return normalizedLeft.length === normalizedRight.length
    && normalizedLeft.every((skill, index) => skill === normalizedRight[index]);
}

function uniqueStrings(values) {
  const seen = new Set();
  const output = [];

  values.forEach((value) => {
    const cleanValue = `${value ?? ""}`.trim();
    const key = cleanValue.toLowerCase();

    if (cleanValue && !seen.has(key)) {
      seen.add(key);
      output.push(cleanValue);
    }
  });

  return output;
}

function LiveEvidencePanel({ liveEvidence, apiEvidence }) {
  const resume = apiEvidence?.resume;
  const repository = apiEvidence?.repository;
  const resources = liveEvidence.resources;
  const market = liveEvidence.market;
  const resourceCategories = (resources?.categories ?? []).filter((category) => category.results?.length);
  const resourceResults = resourceCategories.length
    ? resourceCategories.flatMap((category) => category.results.map((item) => ({ ...item, type_label: category.label })))
    : resources?.results ?? [];
  const jobs = market?.jobs ?? [];
  const resourcesLoading = liveEvidence.status === "loading" && !resources;
  const marketLoading = liveEvidence.status === "loading" && !market;
  const marketSignals = (market?.signals ?? [])
    .filter((signal) => signal.mentions > 0)
    .sort((a, b) => b.mentions - a.mentions)
    .slice(0, 4);
  const shouldShowResume = Boolean(
    resume
      && (
        resume.filename
        || resume.text_character_count > 0
        || resume.matched_skills?.length
      )
  );
  const shouldShowGithub = Boolean(
    repository
      && (
        repository.owner
        || repository.repo
        || repository.repositories?.length
        || repository.languages?.length
        || repository.inferred_skills?.length
      )
  );

  return (
    <div className="live-enrichment" aria-live="polite">
      {shouldShowResume ? (
        <section className="live-section resume-extraction-section">
          <span>Resume extraction</span>
          <strong>{resume.label}</strong>
          <p>{resume.detail}</p>

          <div className="resume-meta">
            <span>{resume.filename || "Pasted text"}</span>
            <span>{resume.text_character_count ?? 0} chars read</span>
          </div>

          {resume.matched_skills?.length ? (
            <div className="extracted-skill-list">
              {resume.matched_skills.map((skill) => (
                <small key={skill}>{skill}</small>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {shouldShowGithub ? (
        <section className="live-section github-section">
          <span>GitHub profile</span>
          <strong>
            {repository.inferred_skills?.length
              ? repository.inferred_skills.join(", ")
              : repository.languages?.length
                ? repository.languages.join(", ")
                : "GitHub link captured"}
          </strong>
          <p>{repository.detail}</p>
          {repository.repositories?.length ? (
            <div className="mini-list">
              {repository.repositories.map((repo) => (
                <span key={repo.url ?? repo.name}>{repo.name}</span>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="live-section resource-section">
        <span>Learning resources</span>
        <strong>
          {resourcesLoading
            ? "Searching resources..."
            : resources
              ? `${resourceResults.length} result${resourceResults.length === 1 ? "" : "s"}`
              : "Not run yet"}
        </strong>
        <p>{resources?.detail ?? "Exa finds books, courses, videos, and project ideas for the highest-priority missing skill."}</p>
        {resourcesLoading ? (
          <ResourceSkeleton />
        ) : resourceCategories.length ? (
          <div className="resource-category-grid">
            {resourceCategories.map((category) => (
              <article className="resource-category-card" key={category.type}>
                <h3>{category.label}</h3>
                <div className="resource-links resource-column-list scroll-list">
                  {category.results.map((item) => (
                    item.url ? (
                      <a href={item.url} key={`${category.type}-${item.url}`} target="_blank" rel="noreferrer">
                        <span>{item.title}</span>
                      </a>
                    ) : (
                      <div className="resource-link-static" key={`${category.type}-${item.title}`}>
                        <span>{item.title}</span>
                      </div>
                    )
                  ))}
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </section>

      <section className="live-section jobs-section">
        <span>Top job postings</span>
        <strong>
          {marketLoading
            ? "Searching jobs..."
            : market
              ? `${jobs.length} posting${jobs.length === 1 ? "" : "s"} found`
              : "Not run yet"}
        </strong>
        <p>{market?.detail ?? "Apify searches current postings and returns roles, companies, links, and required skills."}</p>
        {marketLoading ? (
          <JobSkeleton />
        ) : jobs.length ? (
          <div className="job-list scroll-list">
            {jobs.map((job) => (
              <JobPostingCard job={job} key={`${job.company}-${job.title}-${job.url ?? ""}`} />
            ))}
          </div>
        ) : marketSignals.length ? (
          <div className="mini-list scroll-list">
            {marketSignals.map((signal) => (
              <span key={signal.skill}>
                {signal.skill}: {signal.mentions}
              </span>
            ))}
          </div>
        ) : null}
      </section>

      {liveEvidence.status === "error" ? <p className="live-error">{liveEvidence.error}</p> : null}
    </div>
  );
}

function JobPostingCard({ job }) {
  const content = (
    <>
      <div>
        <strong>{job.title}</strong>
        <span>{job.company} - {job.location}</span>
      </div>
      <p>{job.description}</p>
      {job.skills?.length ? (
        <div className="job-skills">
          {job.skills.map((skill) => (
            <small key={skill}>{skill}</small>
          ))}
        </div>
      ) : null}
      {job.url ? <span className="job-open-label">Open posting</span> : null}
    </>
  );

  if (job.url) {
    return (
      <a className="job-card job-card-link" href={job.url} target="_blank" rel="noreferrer">
        {content}
      </a>
    );
  }

  return <article className="job-card">{content}</article>;
}

function ResourceSkeleton() {
  return (
    <div className="resource-category-grid skeleton-grid" aria-hidden="true">
      {["Books", "Online courses", "Videos", "Projects"].map((label) => (
        <article className="resource-category-card skeleton-card" key={label}>
          <div className="skeleton-line short" />
          <div className="skeleton-stack">
            <div className="skeleton-line" />
            <div className="skeleton-line medium" />
            <div className="skeleton-line" />
          </div>
        </article>
      ))}
    </div>
  );
}

function JobSkeleton() {
  return (
    <div className="job-list scroll-list skeleton-job-list" aria-hidden="true">
      {[0, 1, 2, 3].map((item) => (
        <article className="job-card skeleton-card" key={item}>
          <div className="skeleton-line medium" />
          <div className="skeleton-line short" />
          <div className="skeleton-line" />
          <div className="skeleton-chip-row">
            <span />
            <span />
            <span />
          </div>
        </article>
      ))}
    </div>
  );
}

function RoleSelect({ label, name, value, onChange, disabledId, roles, placeholder }) {
  return (
    <label className={value ? "role-select" : "role-select empty"}>
      <span>{label}</span>
      <select name={name} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="" disabled>
          {placeholder}
        </option>
        {roles.map((role) => (
          <option key={role.id} value={role.id} disabled={role.id === disabledId}>
            {role.sector ? `${role.title} - ${role.sector}` : role.title}
          </option>
        ))}
      </select>
    </label>
  );
}

function CompatibilityGauge({ score, difficulty }) {
  const style = { "--score": score };
  return (
    <div className="compatibility-panel">
      <div className="gauge" style={style} aria-label={`Compatibility ${score}%`}>
        <div>
          <strong>{score}%</strong>
          <span>Compatibility</span>
        </div>
      </div>
      <div>
        <span className="panel-label">Transition difficulty</span>
        <strong>{difficulty}</strong>
        <p>Calculated from skill overlap, role adjacency, and critical missing capabilities.</p>
      </div>
    </div>
  );
}

function PanelHeading({ icon: Icon, title, subtitle }) {
  return (
    <div className="panel-heading">
      <div className="heading-icon">
        <Icon size={18} />
      </div>
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
    </div>
  );
}

function SkillList({ skills, tone, empty }) {
  if (!skills.length) {
    return <p className="empty-copy">{empty}</p>;
  }

  return (
    <div className="skill-list">
      {skills.map((skill) => (
        <span className={`skill-chip ${tone}`} key={skill}>
          {skill}
        </span>
      ))}
    </div>
  );
}

function LearningRoadmapMap({ result, apiEvidence, liveEvidence, progressKey }) {
  const nodes = useMemo(() => buildLearningRoadmapNodes(result), [result]);
  const [progress, setProgress] = useState({});
  const [selectedNodeId, setSelectedNodeId] = useState("");

  useEffect(() => {
    try {
      setProgress(JSON.parse(window.localStorage.getItem(progressKey) || "{}"));
    } catch {
      setProgress({});
    }
  }, [progressKey]);

  useEffect(() => {
    if (!nodes.length) {
      setSelectedNodeId("");
      return;
    }

    const selectedExists = nodes.some((node) => node.id === selectedNodeId);
    if (!selectedExists) {
      setSelectedNodeId(firstOpenRoadmapNode(nodes, progress).id);
    }
  }, [nodes, progress, selectedNodeId]);

  useEffect(() => {
    try {
      window.localStorage.setItem(progressKey, JSON.stringify(progress));
    } catch {
      // Local progress is a convenience layer; the roadmap remains usable if storage is unavailable.
    }
  }, [progress, progressKey]);

  const selectedNode = nodes.find((node) => node.id === selectedNodeId) ?? nodes[0];
  const stats = roadmapProgressStats(nodes, progress);
  const resources = roadmapResourceLinks(liveEvidence);

  const updateNodeStatus = (nodeId, status) => {
    setProgress((current) => {
      const next = { ...current };
      if (status === "todo") {
        delete next[nodeId];
      } else {
        next[nodeId] = status;
      }
      return next;
    });
  };

  const resetProgress = () => setProgress({});

  return (
    <div className="learning-roadmap-shell">
      <div className="roadmap-toolbar">
        <div className="roadmap-progress-meter" aria-label={`${stats.percent}% roadmap complete`}>
          <strong>{stats.percent}%</strong>
          <span>done</span>
          <div>
            <i style={{ width: `${stats.percent}%` }} />
          </div>
        </div>
        <div className="roadmap-stat-strip" aria-label="Roadmap progress summary">
          <span><CheckCircle2 size={14} /> {stats.done} completed</span>
          <span><Clock3 size={14} /> {stats.active} in progress</span>
          <span><SkipForward size={14} /> {stats.skipped} skipped</span>
          <span><CircleDot size={14} /> {stats.total} total</span>
        </div>
        <button type="button" className="roadmap-reset-button" onClick={resetProgress} disabled={!Object.keys(progress).length}>
          <RotateCcw size={15} />
          Reset
        </button>
      </div>

      <div className="learning-roadmap-layout">
        <div className="roadmap-canvas" aria-label={`Learning roadmap for ${result.target.title}`}>
          <div className="roadmap-spine" aria-hidden="true" />
          {result.roadmap.map((phase, phaseIndex) => {
            const phaseNodes = nodes.filter((node) => node.phaseIndex === phaseIndex);
            return (
              <section className="roadmap-lane" key={phase.window} aria-labelledby={`roadmap-phase-${phaseIndex}`}>
                <div className="roadmap-lane-heading">
                  <span>{phase.window}</span>
                  <strong id={`roadmap-phase-${phaseIndex}`}>{phase.theme}</strong>
                </div>
                <div className="roadmap-node-list">
                  {phaseNodes.map((node, nodeIndex) => {
                    const status = progress[node.id] ?? "todo";
                    const isSelected = selectedNode?.id === node.id;
                    return (
                      <button
                        type="button"
                        key={node.id}
                        className={`roadmap-node ${status} ${isSelected ? "selected" : ""}`}
                        onClick={() => setSelectedNodeId(node.id)}
                        aria-pressed={isSelected}
                      >
                        <span className="node-step">{phaseIndex + 1}.{nodeIndex + 1}</span>
                        <span className="node-copy">
                          <strong>{node.title}</strong>
                          <small>{node.relatedSkill}</small>
                        </span>
                        <RoadmapStatusIcon status={status} />
                      </button>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>

        {selectedNode ? (
          <RoadmapDetailPanel
            node={selectedNode}
            status={progress[selectedNode.id] ?? "todo"}
            resources={resources}
            evidence={apiEvidence}
            targetTitle={result.target.title}
            onStatusChange={(status) => updateNodeStatus(selectedNode.id, status)}
          />
        ) : null}
      </div>
    </div>
  );
}

function RoadmapDetailPanel({ node, status, resources, evidence, targetTitle, onStatusChange }) {
  const matchingResources = resources
    .filter((resource) => resourceMatchesNode(resource, node))
    .slice(0, 3);
  const visibleResources = matchingResources.length ? matchingResources : resources.slice(0, 2);
  const evidenceSkills = uniqueStrings([
    ...(evidence?.resume?.matched_skills ?? []),
    ...(evidence?.manual_skills?.matched_skills ?? []),
    ...(evidence?.repository?.inferred_skills ?? []),
  ]).slice(0, 4);

  return (
    <aside className="roadmap-detail-panel" aria-label="Selected roadmap milestone">
      <div className="roadmap-detail-kicker">
        <span>{node.window}</span>
        <RoadmapStatusLabel status={status} />
      </div>
      <h3>{node.title}</h3>
      <p>{node.description}</p>

      <div className="roadmap-detail-meta">
        <span><Flag size={14} /> {node.priority}</span>
        <span><BookOpen size={14} /> {node.relatedSkill}</span>
      </div>

      <div className="roadmap-artifact-box">
        <span>Expected artifact</span>
        <strong>{node.artifact}</strong>
      </div>

      <div className="roadmap-status-actions" aria-label={`Update status for ${node.title}`}>
        <button type="button" className={status === "active" ? "active" : ""} onClick={() => onStatusChange("active")}>
          <Clock3 size={14} />
          Active
        </button>
        <button type="button" className={status === "done" ? "done" : ""} onClick={() => onStatusChange("done")}>
          <CheckCircle2 size={14} />
          Done
        </button>
        <button type="button" className={status === "skipped" ? "skipped" : ""} onClick={() => onStatusChange("skipped")}>
          <SkipForward size={14} />
          Skip
        </button>
        <button type="button" onClick={() => onStatusChange("todo")}>
          <RotateCcw size={14} />
          Todo
        </button>
      </div>

      {visibleResources.length ? (
        <div className="roadmap-detail-section">
          <span>Learning resources</span>
          <div className="roadmap-detail-links">
            {visibleResources.map((resource) => (
              resource.url ? (
                <a href={resource.url} key={resource.url} target="_blank" rel="noreferrer">
                  {resource.title}
                  <ExternalLink size={13} />
                </a>
              ) : (
                <p key={resource.title}>{resource.title}</p>
              )
            ))}
          </div>
        </div>
      ) : null}

      <div className="roadmap-detail-section">
        <span>Evidence angle</span>
        <p>
          {evidenceSkills.length
            ? `${evidenceSkills.join(", ")} can support the ${targetTitle} transition while this milestone closes the next gap.`
            : `Use this milestone to create proof that is easy to explain for ${targetTitle} roles.`}
        </p>
      </div>
    </aside>
  );
}

function RoadmapStatusIcon({ status }) {
  if (status === "done") {
    return <CheckCircle2 size={18} />;
  }

  if (status === "active") {
    return <Clock3 size={18} />;
  }

  if (status === "skipped") {
    return <SkipForward size={18} />;
  }

  return <CircleDot size={18} />;
}

function RoadmapStatusLabel({ status }) {
  const labels = {
    todo: "Todo",
    active: "Active",
    done: "Done",
    skipped: "Skipped",
  };

  return <b className={`roadmap-status-label ${status}`}>{labels[status] ?? labels.todo}</b>;
}

function buildLearningRoadmapNodes(result) {
  const gaps = result.missing ?? [];
  const transferable = result.transferable ?? [];

  return (result.roadmap ?? []).flatMap((phase, phaseIndex) => (
    (phase.tasks ?? []).map((task, taskIndex) => {
      const skillMatch = gaps.find((gap) => task.toLowerCase().includes(gap.name.toLowerCase()));
      const fallbackSkill = gaps[phaseIndex]?.name
        ?? gaps[taskIndex]?.name
        ?? transferable[taskIndex]
        ?? result.target.title;
      const relatedSkill = skillMatch?.name ?? inferRoadmapSkill(task, fallbackSkill);
      const priority = skillMatch
        ? `${skillMatch.urgency} priority - ${skillMatch.demand}% demand`
        : inferRoadmapPriority(task, phase.theme);

      return {
        id: `phase-${phaseIndex}-task-${taskIndex}`,
        phaseIndex,
        taskIndex,
        window: phase.window,
        theme: phase.theme,
        title: taskToRoadmapTitle(task),
        description: task,
        relatedSkill,
        priority,
        artifact: inferRoadmapArtifact(task, relatedSkill, result.target.title),
      };
    })
  ));
}

function firstOpenRoadmapNode(nodes, progress) {
  return nodes.find((node) => progress[node.id] !== "done" && progress[node.id] !== "skipped") ?? nodes[0];
}

function roadmapProgressStats(nodes, progress) {
  const total = nodes.length;
  const done = nodes.filter((node) => progress[node.id] === "done").length;
  const active = nodes.filter((node) => progress[node.id] === "active").length;
  const skipped = nodes.filter((node) => progress[node.id] === "skipped").length;

  return {
    total,
    done,
    active,
    skipped,
    percent: total ? Math.round((done / total) * 100) : 0,
  };
}

function roadmapResourceLinks(liveEvidence) {
  const resources = liveEvidence?.resources;
  const categoryResults = (resources?.categories ?? [])
    .flatMap((category) => (category.results ?? []).map((item) => ({ ...item, typeLabel: category.label })));
  const fallbackResults = resources?.results ?? [];

  return uniqueResourceLinks(categoryResults.length ? categoryResults : fallbackResults);
}

function uniqueResourceLinks(resources) {
  const seen = new Set();
  return resources.filter((resource) => {
    const key = `${resource.url ?? ""}${resource.title ?? ""}`.toLowerCase();
    if (!key || seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function resourceMatchesNode(resource, node) {
  const haystack = `${resource.title ?? ""} ${resource.description ?? ""} ${resource.typeLabel ?? ""}`.toLowerCase();
  return node.relatedSkill
    .toLowerCase()
    .split(/\s+/)
    .filter((part) => part.length > 3)
    .some((part) => haystack.includes(part));
}

function taskToRoadmapTitle(task) {
  return task
    .replace(/\.$/, "")
    .replace(/^Learn /i, "Learn: ")
    .replace(/^Build /i, "Build: ")
    .replace(/^Add /i, "Add: ")
    .replace(/^Ask /i, "Review: ")
    .replace(/^Apply /i, "Apply: ")
    .replace(/^Refresh /i, "Iterate: ");
}

function inferRoadmapSkill(task, fallbackSkill) {
  const lowerTask = task.toLowerCase();

  if (lowerTask.includes("map current skills")) {
    return "Transferable skill map";
  }

  if (lowerTask.includes("write-up") || lowerTask.includes("case study")) {
    return "Evidence narrative";
  }

  if (lowerTask.includes("tests") || lowerTask.includes("documentation")) {
    return "Portfolio quality";
  }

  if (lowerTask.includes("practitioners") || lowerTask.includes("feedback")) {
    return "Role feedback";
  }

  if (lowerTask.includes("apply") || lowerTask.includes("postings")) {
    return "Market validation";
  }

  return fallbackSkill;
}

function inferRoadmapPriority(task, theme) {
  const lowerTask = task.toLowerCase();

  if (lowerTask.includes("portfolio") || lowerTask.includes("case study")) {
    return "Portfolio proof";
  }

  if (lowerTask.includes("apply") || lowerTask.includes("postings")) {
    return "Market signal";
  }

  if (lowerTask.includes("review") || lowerTask.includes("feedback")) {
    return "External validation";
  }

  return `${theme} milestone`;
}

function inferRoadmapArtifact(task, relatedSkill, targetTitle) {
  const lowerTask = task.toLowerCase();

  if (lowerTask.includes("notebook") || lowerTask.includes("mini-project")) {
    return `${relatedSkill} mini-project`;
  }

  if (lowerTask.includes("map current skills")) {
    return "Skill evidence matrix";
  }

  if (lowerTask.includes("write-up")) {
    return "Published transition write-up";
  }

  if (lowerTask.includes("portfolio") || lowerTask.includes("case study")) {
    return `${targetTitle} case study`;
  }

  if (lowerTask.includes("tests") || lowerTask.includes("documentation")) {
    return "Tested, documented project repo";
  }

  if (lowerTask.includes("practitioners")) {
    return "Practitioner review notes";
  }

  if (lowerTask.includes("apply") || lowerTask.includes("postings")) {
    return "Tracked application and keyword log";
  }

  return `${relatedSkill} proof point`;
}

function SkillGraph({ result }) {
  const transferables = result.transferable.slice(0, 5);
  const gaps = result.missing.slice(0, 5);

  return (
    <div className="skill-map" role="img" aria-label={`Skill path from ${result.current.title} to ${result.target.title}`}>
      <article className="role-card current">
        <span>Current</span>
        <strong>{result.current.title}</strong>
        <p>{result.transferable.length} skills transfer</p>
      </article>

      <div className="bridge-column" aria-hidden="true">
        <span>Transfer Bridge</span>
        <div className="bridge-line" />
      </div>

      <article className="role-card target">
        <span>Target</span>
        <strong>{result.target.title}</strong>
        <p>{result.missing.length} priority gaps</p>
      </article>

      <div className="map-band transfer-band">
        <span>Already useful</span>
        <div>
          {transferables.map((skill) => (
            <b key={skill}>{skill}</b>
          ))}
        </div>
      </div>

      <div className="map-band gap-band">
        <span>Build next</span>
        <div>
          {gaps.map((skill) => (
            <b key={skill.name}>
              {skill.name}
              <small>{skill.demand}%</small>
            </b>
          ))}
        </div>
      </div>
    </div>
  );
}

export default App;
