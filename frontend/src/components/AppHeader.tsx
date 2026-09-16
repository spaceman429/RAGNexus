import { Link, useLocation } from "react-router-dom";

import { cn } from "@/lib/utils";

interface NavLink {
  label: string;
  to: string;
}

function getNavLinks(pathname: string): NavLink[] {
  switch (pathname) {
    case "/knowledge-bases":
      return [
        { label: "知识库上传", to: "/" },
        { label: "检索调试", to: "/retrieve" },
      ];
    case "/retrieve":
      return [
        { label: "知识库上传", to: "/" },
        { label: "知识库列表", to: "/knowledge-bases" },
      ];
    default:
      return [
        { label: "知识库列表", to: "/knowledge-bases" },
        { label: "检索调试", to: "/retrieve" },
      ];
  }
}

export function AppHeader() {
  const { pathname } = useLocation();
  const navLinks = getNavLinks(pathname);

  return (
    <header className="flex flex-col gap-4 border-b border-border pb-5 sm:flex-row sm:items-center sm:justify-between">
      <Link to="/" className="text-2xl font-semibold tracking-normal hover:opacity-80">
        RAG 知识文件管理
      </Link>
      <nav className="flex flex-wrap gap-2">
        {navLinks.map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className={cn(
              "inline-flex h-10 items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-muted",
              pathname === link.to && "bg-muted",
            )}
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
