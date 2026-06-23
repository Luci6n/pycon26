import { roles } from "../data/roles.js";

const defaultWeight = 50;

export function getRole(roleId) {
  return roles.find((role) => role.id === roleId) ?? roles[0];
}

export function analyzeTransition(currentId, targetId, profileSkills = []) {
  const current = getRole(currentId);
  const target = getRole(targetId);
  const targetWeights = target.required ?? Object.fromEntries(target.skills.map((skill) => [skill, defaultWeight]));
  const targetSkills = Object.keys(targetWeights);
  const profile = buildProfileContext(current, target, profileSkills);
  const augmentedCurrent = { ...current, skills: profile.augmentedSkills };
  const currentSkills = new Set(augmentedCurrent.skills);

  const transferable = targetSkills
    .filter((skill) => currentSkills.has(skill))
    .sort((a, b) => targetWeights[b] - targetWeights[a]);

  const missing = targetSkills
    .filter((skill) => !currentSkills.has(skill))
    .map((skill) => ({
      name: skill,
      demand: targetWeights[skill],
      urgency: targetWeights[skill] >= 85 ? "Critical" : targetWeights[skill] >= 70 ? "High" : "Medium",
    }))
    .sort((a, b) => b.demand - a.demand);

  const totalWeight = targetSkills.reduce((sum, skill) => sum + targetWeights[skill], 0);
  const overlapWeight = transferable.reduce((sum, skill) => sum + targetWeights[skill], 0);
  const rawOverlap = overlapWeight / totalWeight;
  const bridgeScore = transitionBridgeScore(current.family, target.family);
  const compatibility = clamp(Math.round(15 + rawOverlap * 65 + bridgeScore * 0.35), 5, 96);
  const difficulty = compatibility >= 75 ? "Low" : compatibility >= 55 ? "Medium" : "High";

  const alternatives = roles
    .filter((role) => role.id !== current.id && role.id !== target.id && role.required)
    .map((role) => {
      const result = analyzePair(augmentedCurrent, role);
      return {
        id: role.id,
        title: role.title,
        family: role.family,
        score: result.compatibility,
        missingCount: result.missingCount,
      };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);

  const topGaps = missing.slice(0, 4);

  return {
    current,
    target,
    profile: profile.summary,
    transferable,
    missing,
    compatibility,
    difficulty,
    alternatives,
    roadmap: buildRoadmap(topGaps, target.title),
    evidence: buildEvidence(target, transferable, missing, compatibility, profile.summary),
  };
}

function buildProfileContext(current, target, profileSkills = []) {
  const cleanSkills = unique(
    profileSkills
      .map((skill) => skill.trim())
      .filter(Boolean)
  );
  const currentSkills = new Set(current.skills);
  const targetLookup = new Map(target.skills.map((skill) => [skill.toLowerCase(), skill]));
  const matchedSkills = unique(
    cleanSkills
      .map((skill) => targetLookup.get(skill.toLowerCase()))
      .filter(Boolean)
  );
  const addedTransferableSkills = matchedSkills.filter((skill) => !currentSkills.has(skill));
  const augmentedSkills = unique([...current.skills, ...cleanSkills, ...matchedSkills]);

  return {
    augmentedSkills,
    summary: {
      input_skills: cleanSkills,
      matched_skills: matchedSkills,
      added_transferable_skills: addedTransferableSkills,
      source_count: cleanSkills.length,
      used_in_scoring: addedTransferableSkills.length > 0,
    },
  };
}

function unique(values) {
  return [...new Set(values)];
}

function analyzePair(current, target) {
  const currentSkills = new Set(current.skills);
  const weights = target.required ?? Object.fromEntries(target.skills.map((skill) => [skill, defaultWeight]));
  const skills = Object.keys(weights);
  const total = skills.reduce((sum, skill) => sum + weights[skill], 0);
  const overlap = skills.filter((skill) => currentSkills.has(skill)).reduce((sum, skill) => sum + weights[skill], 0);

  const rawOverlap = overlap / total;
  const bridgeScore = transitionBridgeScore(current.family, target.family);

  return {
    compatibility: clamp(Math.round(15 + rawOverlap * 65 + bridgeScore * 0.35), 5, 96),
    missingCount: skills.filter((skill) => !currentSkills.has(skill)).length,
  };
}

function transitionBridgeScore(currentFamily, targetFamily) {
  if (currentFamily === targetFamily) return 100;

  const pair = [currentFamily, targetFamily].sort().join(" -> ");
  const bridgeScores = {
    "Artificial Intelligence -> Software Engineering": 100,
    "Data -> Software Engineering": 88,
    "Artificial Intelligence -> Data": 86,
    "Business Operations -> Product": 82,
    "Creative -> Product": 72,
    "Creative -> Software Engineering": 55,
    "Creative -> Data": 48,
    "Engineering -> Software Engineering": 66,
    "Artificial Intelligence -> Engineering": 70,
    "Engineering -> Sustainability": 62,
    "Data -> Sustainability": 76,
    "Law -> Business Operations": 68,
    "Law -> Data": 48,
    "Law -> Product": 52,
    "Early Career -> Data": 62,
    "Early Career -> Product": 56,
    "Early Career -> Creative": 54,
    "Early Career -> Law": 50,
    "Early Career -> Engineering": 50,
    "Early Career -> Sustainability": 58,
  };

  return bridgeScores[pair] ?? 35;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function buildEvidence(target, transferable, missing, compatibility, profile = null) {
  const strongestTransfer = transferable[0] ?? "no direct skill";
  const topGap = missing[0];
  const secondGap = missing[1];
  const profileMatches = profile?.added_transferable_skills ?? [];

  return [
    {
      label: "Dataset overlap",
      detail: `${compatibility}% transition readiness combines exact skill overlap with role-family adjacency for ${target.title}.`,
    },
    {
      label: "Transfer signal",
      detail: profileMatches.length
        ? `${profileMatches.slice(0, 3).join(", ")} moved from gap to transferable because it was found in the user's resume, typed skills, or GitHub evidence.`
        : `${strongestTransfer} is counted as a transferable skill because it appears in both role profiles.`,
    },
    topGap
      ? {
          label: "Priority gap",
          detail: `${topGap.name} is recommended first because it appears in ${topGap.demand}% of target-role evidence in this demo subset.`,
        }
      : {
          label: "Priority gap",
          detail: "No major missing target-role skills were found in the curated role profile.",
        },
    secondGap
      ? {
          label: "Roadmap logic",
          detail: `${secondGap.name} is sequenced after the top gap to build toward a realistic ${target.title} portfolio.`,
        }
      : {
          label: "Roadmap logic",
          detail: "The roadmap focuses on validating existing strengths through a portfolio project.",
        },
  ];
}

function buildRoadmap(gaps, targetTitle) {
  const first = gaps[0]?.name ?? "target-role fundamentals";
  const second = gaps[1]?.name ?? "portfolio evidence";
  const third = gaps[2]?.name ?? "interview readiness";

  return [
    {
      window: "30 days",
      theme: "Foundation",
      tasks: [
        `Learn ${first} with a focused notebook or mini-project.`,
        "Map current skills to target-role requirements and collect proof points.",
        "Publish one short technical write-up explaining the transition logic.",
      ],
    },
    {
      window: "60 days",
      theme: "Portfolio",
      tasks: [
        `Build a ${targetTitle} portfolio project using ${second}.`,
        "Add tests, documentation, and a clear problem statement.",
        "Ask two practitioners to review the project for role relevance.",
      ],
    },
    {
      window: "90 days",
      theme: "Market test",
      tasks: [
        `Add ${third} to the project and prepare a role-specific case study.`,
        "Apply to transition-friendly roles and track skill keywords from postings.",
        "Refresh the roadmap using interview feedback and missing-skill evidence.",
      ],
    },
  ];
}
