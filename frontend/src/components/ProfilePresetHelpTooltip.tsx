import { HelpCircle } from "lucide-react";

import { PROFILE_PRESET_PARAMS } from "@/utils/tenantPlan";

export function ProfilePresetHelpTooltip() {
  return (
    <span className="group/profile-help relative inline-flex shrink-0 align-middle">
      <HelpCircle
        className="h-4 w-4 cursor-help text-muted-foreground/60 hover:text-muted-foreground"
        aria-label="各检索 profile 对应的后端 preset 参数"
      />
      <span
        role="tooltip"
        className="pointer-events-none absolute left-0 top-full z-30 mt-2 hidden w-[22rem] rounded-md border border-border bg-background px-3 py-2.5 text-left shadow-lg group-hover/profile-help:block sm:left-1/2 sm:w-80 sm:-translate-x-1/2"
      >
        <p className="mb-2 text-xs font-medium text-foreground">各 profile 展开参数（后端 preset）</p>
        <div className="space-y-2.5">
          {PROFILE_PRESET_PARAMS.map((item) => (
            <div key={item.profile}>
              <p className="text-xs font-medium text-foreground">{item.label}</p>
              <ul className="mt-0.5 space-y-0.5 text-[11px] leading-relaxed text-muted-foreground">
                {item.params.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-2 border-t border-border pt-2 text-[10px] leading-relaxed text-muted-foreground">
          选前三档时由后端自动展开；未传 profile 时默认「均衡」。实际生效还受套餐 plan 与 .env 总闸约束。
        </p>
      </span>
    </span>
  );
}
