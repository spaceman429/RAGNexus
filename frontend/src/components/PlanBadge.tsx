import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { getPlanBadgeClassName, getPlanLabel } from "@/utils/tenantPlan";

interface PlanBadgeProps {
  plan: string;
  className?: string;
  showCode?: boolean;
}

export function PlanBadge({ plan, className, showCode = false }: PlanBadgeProps) {
  return (
    <Badge
      className={cn(
        "border px-2.5 py-1 text-sm font-medium",
        getPlanBadgeClassName(plan),
        className,
      )}
    >
      {getPlanLabel(plan)}
      {showCode ? `（${plan}）` : null}
    </Badge>
  );
}
