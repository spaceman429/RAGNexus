import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Clock3, FileUp, FolderUp, Loader2, XCircle } from "lucide-react";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { AppHeader } from "@/components/AppHeader";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useUploadDocuments } from "@/hooks/useUploadDocuments";
import { cn } from "@/lib/utils";
import { createKnowledgeBase } from "@/services/knowledgeBaseService";
import type { KnowledgeBaseData } from "@/types/api";
import { filterHiddenOrSystemFiles, getRelativePath, type IgnoredFile } from "@/utils/file";

const createKnowledgeBaseSchema = z.object({
  name: z.string().min(1, "请输入知识库名称"),
  description: z.string().optional(),
});

const uploadSchema = z.object({
  kb_id: z.string().min(1, "请输入 kb_id"),
});

type CreateKnowledgeBaseForm = z.infer<typeof createKnowledgeBaseSchema>;
type UploadForm = z.infer<typeof uploadSchema>;

export function KnowledgeUploadPage() {
  const [searchParams] = useSearchParams();
  const queryKbId = searchParams.get("kb_id") ?? "";
  const [createdKnowledgeBase, setCreatedKnowledgeBase] = useState<KnowledgeBaseData | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [ignoredFiles, setIgnoredFiles] = useState<IgnoredFile[]>([]);
  const { currentFile, isUploading, results, uploadSequentially, resetUploadState } =
    useUploadDocuments();

  const createForm = useForm<CreateKnowledgeBaseForm>({
    resolver: zodResolver(createKnowledgeBaseSchema),
    defaultValues: {
      name: "",
      description: "",
    },
  });

  const uploadForm = useForm<UploadForm>({
    resolver: zodResolver(uploadSchema),
    defaultValues: {
      kb_id: queryKbId,
    },
  });

  useEffect(() => {
    if (queryKbId) {
      uploadForm.setValue("kb_id", queryKbId);
    }
  }, [queryKbId, uploadForm]);

  const createMutation = useMutation({
    mutationFn: createKnowledgeBase,
    onSuccess: (data) => {
      setCreatedKnowledgeBase(data);
      uploadForm.setValue("kb_id", data.kb_id);
      setSelectedFiles([]);
      setIgnoredFiles([]);
      uploadForm.clearErrors("root");
      resetUploadState();
    },
  });

  const summary = useMemo(() => {
    const submitted = results.filter(
      (item) => item.status === "submitted" || item.status === "success",
    ).length;
    const failed = results.filter((item) => item.status === "failed").length;
    return { submitted, failed, total: results.length };
  }, [results]);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files || []);
    const { accepted, ignored } = filterHiddenOrSystemFiles(files);
    setSelectedFiles(accepted);
    setIgnoredFiles(ignored);
    if (accepted.length > 0) {
      uploadForm.clearErrors("root");
    }
    event.target.value = "";
  }

  async function handleUpload(values: UploadForm) {
    if (selectedFiles.length === 0) {
      uploadForm.setError("root", { message: "请选择文件或文件夹" });
      return;
    }
    await uploadSequentially({
      kbId: values.kb_id,
      files: selectedFiles,
    });
  }

  return (
    <main className="min-h-screen px-6 py-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <AppHeader />
        <p className="max-w-3xl text-sm text-muted-foreground">
          创建知识库后上传本地文本文件或文件夹。提交后任务进入后台索引，可在
          <Link to="/knowledge-bases" className="mx-1 text-primary underline-offset-4 hover:underline">
            知识库列表
          </Link>
          查看进度。
        </p>

        <section className="grid gap-6 lg:grid-cols-[420px_minmax(0,1fr)]">
          <Card>
            <CardHeader>
              <CardTitle>创建知识库</CardTitle>
            </CardHeader>
            <CardContent>
              <form
                className="flex flex-col gap-4"
                onSubmit={createForm.handleSubmit((values) => createMutation.mutate(values))}
              >
                <FieldError message={createMutation.error?.message} />
                <div className="space-y-2">
                  <Label htmlFor="kb-name">知识库名称</Label>
                  <Input
                    id="kb-name"
                    placeholder="例如：退款政策知识库"
                    {...createForm.register("name")}
                  />
                  <FieldError message={createForm.formState.errors.name?.message} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="kb-description">描述</Label>
                  <Textarea
                    id="kb-description"
                    placeholder="可选"
                    {...createForm.register("description")}
                  />
                </div>
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  创建
                </Button>
              </form>

              {createdKnowledgeBase ? (
                <div className="mt-5 rounded-md border border-border bg-muted/40 p-4 text-sm">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="font-medium">已创建</span>
                    <Badge>{createdKnowledgeBase.tenant_id}</Badge>
                  </div>
                  <div className="space-y-1 text-muted-foreground">
                    <p>{createdKnowledgeBase.name}</p>
                    <p className="break-all font-mono text-xs">{createdKnowledgeBase.kb_id}</p>
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>上传文档</CardTitle>
            </CardHeader>
            <CardContent>
              <form className="flex flex-col gap-5" onSubmit={uploadForm.handleSubmit(handleUpload)}>
                <div className="space-y-2">
                  <Label htmlFor="upload-kb">kb_id</Label>
                  <Input
                    id="upload-kb"
                    placeholder="创建知识库后会自动填入"
                    {...uploadForm.register("kb_id")}
                  />
                  <FieldError message={uploadForm.formState.errors.kb_id?.message} />
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <FilePicker
                    id="file-picker"
                    icon={<FileUp className="h-5 w-5" />}
                    title="选择文件"
                    description="支持 .txt、.md，可多选"
                    onChange={handleFileChange}
                  />
                  <FilePicker
                    id="folder-picker"
                    icon={<FolderUp className="h-5 w-5" />}
                    title="选择文件夹"
                    description="按文件顺序逐个提交"
                    onChange={handleFileChange}
                    directory
                  />
                </div>

                {selectedFiles.length > 0 ? (
                  <div className="rounded-md border border-border p-3 text-sm">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="font-medium">待上传文件</span>
                      <Badge>{selectedFiles.length} 个</Badge>
                    </div>
                    <div className="max-h-28 space-y-1 overflow-auto text-xs text-muted-foreground">
                      {selectedFiles.slice(0, 20).map((file) => (
                        <div key={getRelativePath(file)} className="truncate">
                          {getRelativePath(file)}
                        </div>
                      ))}
                      {selectedFiles.length > 20 ? <div>还有 {selectedFiles.length - 20} 个...</div> : null}
                    </div>
                  </div>
                ) : null}

                {ignoredFiles.length > 0 ? (
                  <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <span className="font-medium">已自动忽略隐藏或系统文件</span>
                      <Badge className="bg-amber-200 text-amber-950 hover:bg-amber-200">
                        {ignoredFiles.length} 个
                      </Badge>
                    </div>
                    <div className="max-h-24 space-y-1 overflow-auto text-xs">
                      {ignoredFiles.slice(0, 10).map((file) => (
                        <div key={file.relativePath} className="truncate">
                          {file.relativePath}
                        </div>
                      ))}
                      {ignoredFiles.length > 10 ? <div>还有 {ignoredFiles.length - 10} 个...</div> : null}
                    </div>
                  </div>
                ) : null}

                <FieldError message={uploadForm.formState.errors.root?.message} />

                <div className="flex items-center gap-3">
                  <Button type="submit" disabled={isUploading}>
                    {isUploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    开始上传
                  </Button>
                  {currentFile ? (
                    <span className="truncate text-sm text-muted-foreground">正在处理：{currentFile}</span>
                  ) : null}
                </div>
              </form>
            </CardContent>
          </Card>
        </section>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4">
            <CardTitle>上传结果</CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              <Badge>已提交 {summary.submitted}</Badge>
              <Badge className={summary.failed > 0 ? "bg-destructive text-destructive-foreground" : ""}>
                失败 {summary.failed}
              </Badge>
              {summary.submitted > 0 ? (
                <Link
                  to="/knowledge-bases"
                  className="text-sm text-primary underline-offset-4 hover:underline"
                >
                  去列表查看进度
                </Link>
              ) : null}
            </div>
          </CardHeader>
          <CardContent>
            {results.length === 0 ? (
              <div className="rounded-md border border-dashed border-border py-10 text-center text-sm text-muted-foreground">
                暂无上传结果
              </div>
            ) : (
              <div className="overflow-hidden rounded-md border border-border">
                <table className="w-full text-left text-sm">
                  <thead className="bg-muted text-xs text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 font-medium">状态</th>
                      <th className="px-3 py-2 font-medium">文件</th>
                      <th className="px-3 py-2 font-medium">document_id</th>
                      <th className="px-3 py-2 font-medium">chunk</th>
                      <th className="px-3 py-2 font-medium">信息</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((result) => (
                      <tr key={result.relativePath} className="border-t border-border">
                        <td className="px-3 py-2">
                          {result.status === "failed" ? (
                            <XCircle className="h-4 w-4 text-destructive" />
                          ) : result.status === "submitted" ? (
                            <Clock3 className="h-4 w-4 text-amber-600" />
                          ) : (
                            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                          )}
                        </td>
                        <td className="max-w-[320px] truncate px-3 py-2">{result.relativePath}</td>
                        <td className="max-w-[260px] truncate px-3 py-2 font-mono text-xs">
                          {result.documentId || "-"}
                        </td>
                        <td className="px-3 py-2">{result.chunkCount ?? "-"}</td>
                        <td
                          className={cn(
                            "max-w-[340px] truncate px-3 py-2",
                            result.status === "failed" ? "text-destructive" : "text-muted-foreground",
                          )}
                        >
                          {result.message ||
                            (result.status === "submitted" ? "已提交，正在后台索引" : "完成")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}

function FieldError({ message }: { message?: string }) {
  if (!message) {
    return null;
  }
  return <p className="text-sm text-destructive">{message}</p>;
}

interface FilePickerProps {
  id: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  directory?: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}

function FilePicker({ id, icon, title, description, directory, onChange }: FilePickerProps) {
  const directoryProps = directory ? ({ webkitdirectory: "", directory: "" } as Record<string, string>) : {};

  return (
    <label
      htmlFor={id}
      className="flex cursor-pointer items-center gap-3 rounded-md border border-dashed border-border p-4 transition-colors hover:bg-muted/60"
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-md bg-muted text-muted-foreground">
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-medium">{title}</span>
        <span className="block text-xs text-muted-foreground">{description}</span>
      </span>
      <input
        id={id}
        type="file"
        multiple
        accept=".txt,.md,.pdf,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="sr-only"
        onChange={onChange}
        {...directoryProps}
      />
    </label>
  );
}
