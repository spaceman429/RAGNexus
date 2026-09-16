import type { AuthMeData, AuthFeatures, RetrieveProfile } from "@/types/api";

export const PLAN_LABELS: Record<string, string> = {
  free: "免费",
  standard: "标准",
  pro: "专业",
};

export const PROFILE_OPTIONS: {
  value: RetrieveProfile;
  label: string;
  description: string;
}[] = [
  { value: "speed", label: "追求速度", description: "vector，最快" },
  { value: "balanced", label: "均衡", description: "hybrid，默认推荐" },
  { value: "quality", label: "追求质量", description: "hybrid + rerank + rewrite" },
  { value: "custom", label: "自定义", description: "展开高级参数" },
];

/** 与后端 retrieve_presets.py 保持一致，供调试台 tooltip 展示 */
export const PROFILE_PRESET_PARAMS: {
  label: string;
  profile: RetrieveProfile;
  params: string[];
}[] = [
  {
    label: "追求速度",
    profile: "speed",
    params: [
      "检索模式：vector",
      "top_k：3",
      "rerank：关",
      "query 改写：关",
    ],
  },
  {
    label: "均衡",
    profile: "balanced",
    params: [
      "检索模式：hybrid",
      "vector_top_k / bm25_top_k：10",
      "top_k：5",
      "rerank：关",
      "query 改写：关",
    ],
  },
  {
    label: "追求质量",
    profile: "quality",
    params: [
      "检索模式：hybrid",
      "vector_top_k / bm25_top_k：20",
      "top_k：8",
      "rerank：开",
      "query 改写：开（rewrite）",
    ],
  },
  {
    label: "自定义",
    profile: "custom",
    params: ["自行配置"],
  },
];

export function getPlanLabel(plan: string) {
  return PLAN_LABELS[plan] ?? plan;
}

const PLAN_BADGE_CLASS: Record<string, string> = {
  free: "border-slate-200 bg-slate-100 text-slate-700",
  standard: "border-sky-200 bg-sky-50 text-sky-800",
  pro: "border-amber-200 bg-amber-50 text-amber-900",
};

export function getPlanBadgeClassName(plan: string) {
  return PLAN_BADGE_CLASS[plan] ?? "border-border bg-muted text-muted-foreground";
}

export function getDefaultProfile(features: AuthFeatures): RetrieveProfile {
  if (features.allowed_profiles.includes("balanced")) {
    return "balanced";
  }
  if (features.allowed_profiles.includes("speed")) {
    return "speed";
  }
  return features.allowed_profiles[0] as RetrieveProfile;
}

export function isProfileAllowed(features: AuthFeatures, profile: RetrieveProfile) {
  return features.allowed_profiles.includes(profile);
}

export function getProfileDisabledTooltip(plan: string, profile: RetrieveProfile): string {
  const planLabel = getPlanLabel(plan);
  if (profile === "quality") {
    return `当前为${planLabel}套餐，不支持「追求质量」。请升级专业套餐，或选用均衡 / 自定义。`;
  }
  if (profile === "balanced") {
    return `当前为${planLabel}套餐，不支持「均衡」。请选用追求速度。`;
  }
  if (profile === "custom") {
    return `当前为${planLabel}套餐，不支持「自定义」。请选用追求速度。`;
  }
  return `当前为${planLabel}套餐，不支持该检索预设。`;
}

export function formatDailyRetrieveUsage(usage: AuthMeData["usage"], limits: AuthMeData["limits"]) {
  return `今日检索 ${usage.retrieve_daily} / ${limits.retrieve_daily}`;
}
