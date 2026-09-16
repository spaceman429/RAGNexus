import { useQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  Copy,
  Loader2,
  Pencil,
  RotateCcw,
  Search,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { AppHeader } from "@/components/AppHeader";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DocumentStatusBadge } from "@/components/DocumentStatusBadge";
import { EditKnowledgeBaseDialog } from "@/components/EditKnowledgeBaseDialog";
import { PlanBadge } from "@/components/PlanBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { fetchAuthMe } from "@/services/authService";
import { deleteDocument, reindexDocument } from "@/services/documentService";
import {
  deleteKnowledgeBase,
  fetchTree,
} from "@/services/knowledgeBaseService";
import type { DocumentTreeItem, KnowledgeBaseTreeItem } from "@/types/api";
import { formatDailyRetrieveUsage } from "@/utils/tenantPlan";

const DOCUMENT_STATUS_PROCESSING = 3;

type ConfirmTarget =
  | { type: "kb"; kbId: string; name: string }
  | { type: "doc"; documentId: string; title: string };

function formatDate(value: string) {
  return new Date(value).toLocaleString("zh-CN");
}

function buildKbQuery(kbId: string) {
  return `?kb_id=${encodeURIComponent(kbId)}`;
}

async function copyText(text: string) {
  await navigator.clipboard.writeText(text);
}

function truncateText(text: string, maxLength = 80) {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}...`;
}

export function KnowledgeFileTreePage() {
  const [keyword, setKeyword] = useState("");
  const [searchKeyword, setSearchKeyword] = useState("");
  const [expandedKbs, setExpandedKbs] = useState<Set<string>>(new Set());
  const [editingKb, setEditingKb] = useState<KnowledgeBaseTreeItem | null>(null);
  const [confirmTarget, setConfirmTarget] = useState<ConfirmTarget | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: tenantInfo } = useQuery({
    queryKey: ["authMe"],
    queryFn: fetchAuthMe,
  });

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["knowledgeBaseTree", searchKeyword],
    queryFn: () => fetchTree(searchKeyword || undefined),
    refetchInterval: (query) => {
      const kbs = query.state.data?.flatMap((tenant) => tenant.knowledge_bases) ?? [];
      const processing = kbs.some((kb) =>
        kb.documents.some((doc) => doc.status === DOCUMENT_STATUS_PROCESSING),
      );
      return processing ? 3000 : false;
    },
  });

  const knowledgeBases = useMemo(
    () => data?.flatMap((tenant) => tenant.knowledge_bases) ?? [],
    [data],
  );

  const hasProcessingDocuments = useMemo(
    () =>
      knowledgeBases.some((kb) =>
        kb.documents.some((doc) => doc.status === DOCUMENT_STATUS_PROCESSING),
      ),
    [knowledgeBases],
  );

  function handleSearch() {
    setSearchKeyword(keyword.trim());
  }

  function toggleKb(kbId: string) {
    setExpandedKbs((prev) => {
      const next = new Set(prev);
      if (next.has(kbId)) {
        next.delete(kbId);
      } else {
        next.add(kbId);
      }
      return next;
    });
  }

  async function handleConfirmAction() {
    if (!confirmTarget) {
      return;
    }

    setActionLoading(true);
    setActionError(null);
    try {
      if (confirmTarget.type === "kb") {
        await deleteKnowledgeBase(confirmTarget.kbId);
      } else {
        await deleteDocument(confirmTarget.documentId);
      }
      setConfirmTarget(null);
      await refetch();
    } catch (actionErr) {
      setActionError(actionErr instanceof Error ? actionErr.message : "操作失败");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReindex(documentId: string) {
    setActionError(null);
    try {
      await reindexDocument(documentId);
      await refetch();
    } catch (reindexErr) {
      setActionError(reindexErr instanceof Error ? reindexErr.message : "重试失败");
    }
  }

  return (
    <main className="min-h-screen px-6 py-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <AppHeader />

        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
            <CardTitle>知识库列表</CardTitle>
            {tenantInfo ? (
              <div className="flex flex-col items-end gap-2 text-base sm:flex-row sm:items-center sm:gap-6">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-base text-muted-foreground">当前租户名称：</span>
                  <Badge className="px-2.5 py-1 text-sm font-medium text-foreground">
                    {tenantInfo.tenant_name}
                  </Badge>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-base text-muted-foreground">当前租户ID：</span>
                  <Badge className="px-2.5 py-1 font-mono text-sm font-medium text-foreground">
                    {tenantInfo.tenant_id}
                  </Badge>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-base text-muted-foreground">套餐：</span>
                  <PlanBadge plan={tenantInfo.plan} />
                </div>
                <span className="text-sm text-muted-foreground">
                  {formatDailyRetrieveUsage(tenantInfo.usage, tenantInfo.limits)}
                </span>
              </div>
            ) : null}
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {hasProcessingDocuments ? (
              <p className="text-sm text-amber-700">有文档正在索引，列表会自动刷新…</p>
            ) : null}
            {actionError ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                {actionError}
              </div>
            ) : null}

            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="pl-9"
                  placeholder="搜索知识库名称（模糊匹配）"
                  value={keyword}
                  onChange={(event) => setKeyword(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      handleSearch();
                    }
                  }}
                />
              </div>
              <Button type="button" onClick={handleSearch} disabled={isFetching}>
                {isFetching ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                搜索
              </Button>
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                加载中...
              </div>
            ) : error ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
                {(error as Error).message}
                <Button variant="ghost" className="ml-2 h-8 px-2" onClick={() => refetch()}>
                  重试
                </Button>
              </div>
            ) : knowledgeBases.length === 0 ? (
              <div className="rounded-md border border-dashed border-border py-16 text-center text-sm text-muted-foreground">
                暂无数据
              </div>
            ) : (
              <div className="overflow-hidden rounded-md border border-border">
                <table className="w-full table-fixed text-left text-sm">
                  <colgroup>
                    <col className="w-[22%]" />
                    <col className="w-24" />
                    <col className="w-[20%]" />
                    <col className="w-16" />
                    <col className="w-36" />
                    <col />
                  </colgroup>
                  <thead className="bg-muted text-xs text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 font-medium">名称</th>
                      <th className="whitespace-nowrap px-3 py-2 font-medium">状态</th>
                      <th className="px-3 py-2 font-medium">kb_id/document_id</th>
                      <th className="px-3 py-2 font-medium">分块数</th>
                      <th className="px-3 py-2 font-medium">创建时间</th>
                      <th className="px-3 py-2 font-medium">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {knowledgeBases.map((kb) => (
                      <KnowledgeBaseRows
                        key={kb.kb_id}
                        kb={kb}
                        expanded={expandedKbs.has(kb.kb_id)}
                        onToggle={() => toggleKb(kb.kb_id)}
                        onEdit={() => setEditingKb(kb)}
                        onDelete={() =>
                          setConfirmTarget({ type: "kb", kbId: kb.kb_id, name: kb.name })
                        }
                        onDeleteDocument={(doc) =>
                          setConfirmTarget({
                            type: "doc",
                            documentId: doc.document_id,
                            title: doc.title,
                          })
                        }
                        onReindex={handleReindex}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <EditKnowledgeBaseDialog
        kb={editingKb}
        onClose={() => setEditingKb(null)}
        onSaved={() => {
          void refetch();
        }}
      />

      <ConfirmDialog
        open={confirmTarget !== null}
        title={confirmTarget?.type === "kb" ? "删除知识库" : "删除文档"}
        description={
          confirmTarget?.type === "kb"
            ? `将删除知识库「${confirmTarget.name}」及其全部文档，不可恢复。`
            : `将删除文档「${confirmTarget?.title ?? ""}」，不可恢复。`
        }
        confirmLabel="删除"
        loading={actionLoading}
        onCancel={() => setConfirmTarget(null)}
        onConfirm={() => {
          void handleConfirmAction();
        }}
      />
    </main>
  );
}

interface KnowledgeBaseRowsProps {
  kb: KnowledgeBaseTreeItem;
  expanded: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onDeleteDocument: (doc: DocumentTreeItem) => void;
  onReindex: (documentId: string) => void;
}

function KnowledgeBaseRows({
  kb,
  expanded,
  onToggle,
  onEdit,
  onDelete,
  onDeleteDocument,
  onReindex,
}: KnowledgeBaseRowsProps) {
  const query = buildKbQuery(kb.kb_id);

  return (
    <>
      <tr className="border-t border-border">
        <td className="max-w-0 px-3 py-2">
          <button type="button" className="flex max-w-full items-center gap-2" onClick={onToggle}>
            {expanded ? (
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
            )}
            <span className="truncate font-medium">{kb.name}</span>
          </button>
          {kb.description ? (
            <p className="mt-1 truncate pl-6 text-xs text-muted-foreground">{kb.description}</p>
          ) : null}
        </td>
        <td className="whitespace-nowrap px-3 py-2">—</td>
        <td className="max-w-[280px] truncate px-3 py-2 font-mono text-xs">{kb.kb_id}</td>
        <td className="px-3 py-2">{kb.documents.length}</td>
        <td className="px-3 py-2 text-muted-foreground">{formatDate(kb.created_at)}</td>
        <td className="px-3 py-2">
          <div className="flex flex-wrap gap-1">
            <Button variant="ghost" className="h-8 px-2" type="button" onClick={onEdit}>
              <Pencil className="mr-1 h-3.5 w-3.5" />
              编辑
            </Button>
            <Button variant="ghost" className="h-8 px-2 text-destructive" type="button" onClick={onDelete}>
              <Trash2 className="mr-1 h-3.5 w-3.5" />
              删除
            </Button>
            <Button
              variant="ghost"
              className="h-8 px-2"
              type="button"
              onClick={() => copyText(kb.kb_id)}
            >
              <Copy className="mr-1 h-3.5 w-3.5" />
              复制
            </Button>
            <Link
              to={`/${query}`}
              className="inline-flex h-8 items-center rounded-md px-2 text-sm hover:bg-muted"
            >
              去上传
            </Link>
            <Link
              to={`/retrieve${query}`}
              className="inline-flex h-8 items-center rounded-md px-2 text-sm hover:bg-muted"
            >
              去检索
            </Link>
          </div>
        </td>
      </tr>
      {expanded
        ? kb.documents.map((doc) => (
            <tr key={doc.document_id} className="border-t border-border bg-muted/10">
              <td className="max-w-0 px-3 py-2 pl-10">
                <div className="truncate" title={doc.title}>
                  {doc.title}
                </div>
                {doc.error_message ? (
                  <p className="mt-1 truncate text-xs text-destructive" title={doc.error_message}>
                    {truncateText(doc.error_message)}
                  </p>
                ) : null}
              </td>
              <td className="whitespace-nowrap px-3 py-2">
                <DocumentStatusBadge status={doc.status} />
              </td>
              <td className="max-w-[280px] truncate px-3 py-2 font-mono text-xs">
                {kb.kb_id}/{doc.document_id}
              </td>
              <td className="px-3 py-2">{doc.chunk_count}</td>
              <td className="px-3 py-2 text-muted-foreground">{formatDate(doc.created_at)}</td>
              <td className="px-3 py-2">
                <div className="flex flex-wrap gap-1">
                  {doc.status === 2 ? (
                    <Button
                      variant="ghost"
                      className="h-8 px-2"
                      type="button"
                      onClick={() => onReindex(doc.document_id)}
                    >
                      <RotateCcw className="mr-1 h-3.5 w-3.5" />
                      重试
                    </Button>
                  ) : null}
                  {doc.status !== DOCUMENT_STATUS_PROCESSING ? (
                    <Button
                      variant="ghost"
                      className="h-8 px-2 text-destructive"
                      type="button"
                      onClick={() => onDeleteDocument(doc)}
                    >
                      <Trash2 className="mr-1 h-3.5 w-3.5" />
                      删除
                    </Button>
                  ) : null}
                </div>
              </td>
            </tr>
          ))
        : null}
    </>
  );
}
