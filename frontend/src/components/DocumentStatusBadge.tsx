import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const STATUS_MAP: Record<number, { label: string; className: string }> = {
  1: { label: "成功", className: "bg-emerald-100 text-emerald-800 hover:bg-emerald-100" },
  2: { label: "失败", className: "bg-red-100 text-red-800 hover:bg-red-100" },
  3: { label: "索引中", className: "bg-amber-100 text-amber-900 hover:bg-amber-100" },
};

interface DocumentStatusBadgeProps {
  status: number;
  className?: string;
}

export function DocumentStatusBadge({ status, className }: DocumentStatusBadgeProps) {
  const config = STATUS_MAP[status] ?? { label: `状态${status}`, className: "" };
  return (
    <Badge className={cn("whitespace-nowrap", config.className, className)}>
      {config.label}
    </Badge>
  );
}
