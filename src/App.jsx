import {
  ArrowLeftRight,
  Brain,
  CheckCircle2,
  CircleDot,
  GitBranch,
  Layers3,
  Link as LinkIcon,
  Upload,
  Route,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { roles } from "./data/roles.js";
import {
  extractResumeFromApi,
  fetchAnalysisFromApi,
  fetchAdminRoadmaps,
  fetchAdminUsers,
  fetchEvidenceFromApi,
  fetchMarketEnrichment,
  fetchResourceEnrichment,
  fetchRolesFromApi,
  fetchSavedRoadmaps,
  loginUser,
  registerUser,
  saveRoadmap,
} from "./utils/api.js";
import { analyzeTransition } from "./utils/analysis.js";

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
          <div className="roadmap">
            {result.roadmap.map((phase) => (
              <article key={phase.window} className="roadmap-phase">
                <div>
                  <span>{phase.window}</span>
                  <strong>{phase.theme}</strong>
                </div>
                <ul>
                  {phase.tasks.map((task) => (
                    <li key={task}>{task}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>
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
