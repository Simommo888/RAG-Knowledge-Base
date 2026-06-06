import * as React from "react";

import { cn } from "@/lib/utils";

type BadgeVariant = "default" | "secondary" | "success" | "warning" | "outline";

const variants: Record<BadgeVariant, string> = {
  default: "bg-primary text-primary-foreground",
  secondary: "bg-muted text-muted-foreground",
  success: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  warning: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  outline: "border border-border bg-background text-foreground"
};

export function Badge({
  className,
  variant = "secondary",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }) {
  return (
    <span
      className={cn(
        "inline-flex min-h-6 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}
