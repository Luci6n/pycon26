const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8010";

export async function fetchRolesFromApi() {
  return fetchJson("/api/datasets/roles?limit=2500");
}

export async function fetchAnalysisFromApi(currentRoleId, targetRoleId, profileSkills = []) {
  return fetchJson("/api/datasets/analyze", {
    method: "POST",
    body: JSON.stringify({
      current_role: currentRoleId,
      target_role: targetRoleId,
      profile_skills: profileSkills,
    }),
  });
}

export async function fetchEvidenceFromApi({
  targetRoleId,
  resumeName,
  resumeText,
  manualSkills = [],
  githubUrl,
  portfolioLinks,
  fetchRepository = false,
}) {
  const normalizedPortfolioLinks = Array.isArray(portfolioLinks)
    ? portfolioLinks
    : portfolioLinks
      .split(/\s+/)
      .map((link) => link.trim())
      .filter(Boolean);

  return fetchJson("/api/evidence", {
    method: "POST",
    body: JSON.stringify({
      target_role_id: targetRoleId,
      resume_name: resumeName || null,
      resume_text: resumeText || null,
      manual_skills: manualSkills,
      github_url: githubUrl || null,
      portfolio_links: normalizedPortfolioLinks,
      market_scan_enabled: true,
      fetch_repository: fetchRepository,
    }),
  });
}

export async function fetchResourceEnrichment({ skill, targetRole, numResults = 4 }) {
  return fetchJson("/api/enrich/resources", {
    method: "POST",
    body: JSON.stringify({
      skill,
      target_role: targetRole,
      num_results: numResults,
    }),
  });
}

export async function fetchMarketEnrichment({ targetRole, skills, country = "Singapore" }) {
  return fetchJson("/api/enrich/market", {
    method: "POST",
    body: JSON.stringify({
      target_role: targetRole,
      skills,
      country,
    }),
  });
}

export async function extractResumeFromApi(file) {
  const contentBase64 = await fileToBase64(file);

  return fetchJson("/api/resume/extract", {
    method: "POST",
    body: JSON.stringify({
      filename: file.name,
      content_base64: contentBase64,
    }),
  });
}

export async function registerUser({ email, password, name }) {
  return fetchJson("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, name }),
  });
}

export async function loginUser({ email, password }) {
  return fetchJson("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function fetchCurrentUser(token) {
  return fetchJson("/api/auth/me", { token });
}

export async function saveRoadmap(token, roadmap) {
  return fetchJson("/api/roadmaps", {
    method: "POST",
    token,
    body: JSON.stringify(roadmap),
  });
}

export async function fetchSavedRoadmaps(token) {
  return fetchJson("/api/roadmaps", { token });
}

export async function fetchAdminUsers(token) {
  return fetchJson("/api/admin/users", { token });
}

export async function fetchAdminRoadmaps(token) {
  return fetchJson("/api/admin/roadmaps", { token });
}

async function fetchJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
      ...(options.headers ?? {}),
    },
    ...withoutClientOptions(options),
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return response.json();
}

function withoutClientOptions(options) {
  const { token, headers, ...fetchOptions } = options;
  return fetchOptions;
}

async function fileToBase64(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const chunkSize = 0x8000;
  let binary = "";

  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }

  return window.btoa(binary);
}
